"""Execução dos comandos e montagem das respostas do chat."""
import threading
from collections import defaultdict
from typing import Callable, Optional

from .chat_reader import ParsedCommand
from .database import Database
from .economy import Economy, InsufficientBalance, InvalidAmount, PlayerNotFound
from .gambling import BET_MAX, BET_MIN, Gambling
from .game_interface import ChatMessage
from .logger import get_logger
from .withdrawal import (COMPLETED, FAILED, FEE_BOT, FEE_GAME, WITHDRAW_MAX, WITHDRAW_MIN,
                         WithdrawalService)

log = get_logger("command_handler")


class CommandHandler:
    def __init__(self, db: Database, economy: Economy, gambling: Gambling,
                 withdrawals: WithdrawalService, reply: Callable[[str], None]):
        self.db, self.economy, self.gambling, self.withdrawals, self.reply = db, economy, gambling, withdrawals, reply
        self._locks = defaultdict(threading.Lock)
        self._guard = threading.Lock()

    def _player_lock(self, pid: int) -> threading.Lock:
        with self._guard:
            return self._locks[pid]

    def _resolve_id(self, msg: ChatMessage) -> Optional[int]:
        if msg.author_id is not None:
            return msg.author_id
        ids = self.economy.find_ids_by_name(msg.author_name)
        if len(ids) == 1:
            return ids[0]
        if len(ids) > 1:
            return -1  # ambíguo
        return None

    def handle(self, msg: ChatMessage, cmd: ParsedCommand) -> None:
        # Marca o comando como processado ANTES de executar: no máximo uma execução.
        with self.db.transaction() as conn:
            if conn.execute("INSERT OR IGNORE INTO processed_commands(key) VALUES(?)",
                            (f"chat:{msg.uid}",)).rowcount == 0:
                log.warning("Comando duplicado ignorado: %s", msg.uid)
                return
        who = f"@{msg.author_name}"
        if not cmd.valid:
            usage = {"saldo": "!saldo", "apostar": f"!apostar [valor] ({BET_MIN}-{BET_MAX})",
                     "sacar": f"!sacar [valor] ({WITHDRAW_MIN}-{WITHDRAW_MAX})"}[cmd.name]
            self.reply(f"{who} Comando inválido. Uso: {usage}")
            return
        pid = self._resolve_id(msg)
        if pid == -1:
            self.reply(f"{who} Seu nome corresponde a mais de uma conta; não foi possível identificá-lo.")
            return
        if pid is None:
            self.reply(f"{who} Você ainda não possui saldo. Envie Plasma para começar!")
            return
        with self._player_lock(pid):  # um comando por jogador por vez
            getattr(self, f"_{cmd.name}")(who, pid, cmd.amount)

    def _saldo(self, who, pid, _):
        bal = self.economy.get_balance(pid)
        if bal is None:
            self.reply(f"{who} Você ainda não possui saldo. Envie Plasma para começar!")
        else:
            self.reply(f"{who} Seu saldo atual é de {bal} Plasma.")

    def _apostar(self, who, pid, amount):
        try:
            r = self.gambling.place_bet(pid, amount)
        except InvalidAmount:
            self.reply(f"{who} Valor inválido. Aposta mínima: {BET_MIN}, máxima: {BET_MAX} Plasma.")
        except (InsufficientBalance, PlayerNotFound):
            self.reply(f"{who} Saldo insuficiente. Seu saldo: {self.economy.get_balance(pid) or 0} Plasma.")
        else:
            if r.won:
                self.reply(f"{who} Você venceu! 🎲")
                self.reply(f"Seu dado: {r.player_roll} | Dado da banca: {r.bank_roll}")
                self.reply(f"Aposta: {r.amount} Plasma")
                self.reply(f"Prêmio: {r.payout} Plasma")
            else:
                self.reply(f"{who} Você perdeu!")
                self.reply(f"Seu dado: {r.player_roll} | Dado da banca: {r.bank_roll}")
                self.reply(f"Você perdeu {r.amount} Plasma.")

    def _sacar(self, who, pid, amount):
        try:
            w = self.withdrawals.request(pid, amount)
        except InvalidAmount:
            self.reply(f"{who} Valor inválido. Saque mínimo: {WITHDRAW_MIN}, máximo: {WITHDRAW_MAX} Plasma.")
            return
        except (InsufficientBalance, PlayerNotFound):
            self.reply(f"{who} Saldo insuficiente. Seu saldo: {self.economy.get_balance(pid) or 0} Plasma.")
            return
        self.reply(f"{who} Solicitação de saque recebida!")
        self.reply(f"Valor solicitado: {w.amount} Plasma")
        self.reply(f"Taxa do bot: {FEE_BOT} Plasma")
        self.reply(f"Taxa do jogo: {FEE_GAME} Plasma")
        self.reply(f"Valor líquido que você receberá: {w.net} Plasma.")
        status = self.withdrawals.execute(w.id)
        if status == COMPLETED:
            self.reply(f"{who} Saque realizado com sucesso! Você recebeu {w.net} Plasma.")
        elif status == FAILED:
            self.reply(f"{who} Não foi possível concluir o saque. O valor foi devolvido ao seu saldo.")
        else:
            self.reply(f"{who} Seu saque está em verificação manual. Aguarde a confirmação.")
