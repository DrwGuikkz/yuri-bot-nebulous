"""Inicialização e laço principal.

Uso:
  python -m nebulous_bank.main --simulate
  python -m nebulous_bank.main --adapter meu_pacote.meu_modulo:MinhaIntegracao --bot-name MeuBot
"""
import argparse
import importlib
import sys
import threading

from .chat_reader import ChatReader
from .command_handler import CommandHandler
from .database import Database
from .economy import Economy
from .email_reader import EmailReader
from .gambling import Gambling
from .game_interface import GameInterface
from .logger import setup_logger
from .withdrawal import WithdrawalService


def build(game: GameInterface, db_path: str, bot_name: str):
    db = Database(db_path)
    economy = Economy(db)
    withdrawals = WithdrawalService(db, game)
    withdrawals.recover_interrupted()
    handler = CommandHandler(db, economy, Gambling(db), withdrawals, game.send_chat)
    return db, EmailReader(game, economy), ChatReader(game, handler, bot_name)


def run(game, db_path="bank.db", bot_name="Bot", interval=2.0, stop: threading.Event = None):
    log = setup_logger()
    db, emails, chat = build(game, db_path, bot_name)
    stop = stop or threading.Event()
    log.info("Bot iniciado")
    while not stop.is_set():
        try:
            emails.poll()   # depósitos primeiro
            chat.poll()
        except Exception:
            log.exception("Erro no ciclo principal")
        stop.wait(interval)
    db.close()


def _demo():
    from .simulated_game import SimulatedGame
    g = SimulatedGame()
    g.push_mail("Darwin(4231582) sent you a gift of 20000 plasma!")
    g.push_chat("Darwin", "!saldo")
    g.push_chat("Darwin", "!apostar 5000")
    g.push_chat("Darwin", "!sacar 10000")
    stop = threading.Event()
    t = threading.Thread(target=run, args=(g, ":memory:", "Bot", 0.1, stop))
    t.start(); stop.wait(0.5); stop.set(); t.join()
    print("\n--- chat do bot (simulado) ---")
    print("\n".join(g.chat_out))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--simulate", action="store_true", help="demo com jogo simulado")
    ap.add_argument("--adapter", help="pacote.modulo:Classe que implementa GameInterface")
    ap.add_argument("--db", default="bank.db")
    ap.add_argument("--bot-name", default="Bot")
    ap.add_argument("--interval", type=float, default=2.0)
    a = ap.parse_args(argv)
    if a.simulate:
        return _demo()
    if not a.adapter:
        print("Nenhuma integração com o jogo configurada.\nImplemente nebulous_bank.game_interface.GameInterface "
              "e passe --adapter (veja FEASIBILITY.md).", file=sys.stderr)
        sys.exit(2)
    mod, cls = a.adapter.split(":")
    run(getattr(importlib.import_module(mod), cls)(), a.db, a.bot_name, a.interval)


if __name__ == "__main__":
    main()
