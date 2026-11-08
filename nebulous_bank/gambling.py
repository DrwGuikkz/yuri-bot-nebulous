"""Jogo de dados contra a banca (d10 x d10). Empate = banca vence."""
import secrets
from dataclasses import dataclass

from .database import Database
from .economy import InvalidAmount, apply_delta
from .logger import get_logger

log = get_logger("gambling")

BET_MIN = 1000
BET_MAX = 50000
SIDES = 10


@dataclass(frozen=True)
class BetResult:
    bet_id: int
    won: bool
    player_roll: int
    bank_roll: int
    amount: int
    payout: int      # total devolvido ao jogador (2x a aposta se ganhou, senão 0)
    balance: int


class Gambling:
    def __init__(self, db: Database, rng=None):
        self.db = db
        self._rng = rng or secrets.SystemRandom()  # CSPRNG do sistema operacional

    def _roll(self) -> int:
        return self._rng.randint(1, SIDES)

    def place_bet(self, player_id: int, amount: int) -> BetResult:
        if not isinstance(amount, int) or not (BET_MIN <= amount <= BET_MAX):
            raise InvalidAmount(f"aposta deve estar entre {BET_MIN} e {BET_MAX}")
        # Tudo em UMA transação: débito, sorteio, prêmio e registro.
        with self.db.transaction() as conn:
            balance = apply_delta(conn, player_id, -amount, "bet_stake")  # valida saldo
            p, b = self._roll(), self._roll()
            won = p > b
            payout = amount * 2 if won else 0
            bet_id = conn.execute(
                "INSERT INTO bets(player_id, amount, player_roll, bank_roll, won, payout) VALUES(?,?,?,?,?,?)",
                (player_id, amount, p, b, int(won), payout),
            ).lastrowid
            if won:
                balance = apply_delta(conn, player_id, payout, "bet_win", ref=f"bet:{bet_id}")
        log.info("Aposta #%s id=%s valor=%s dados=%s/%s %s", bet_id, player_id, amount, p, b, "WIN" if won else "LOSS")
        return BetResult(bet_id, won, p, b, amount, payout, balance)
