"""Saques: reserva atômica -> envio de presente -> confirmação/estorno.

Estados: pending -> sending -> completed | failed (estornado) | needs_review.
Se o resultado do envio for desconhecido (UNKNOWN) ou o programa cair durante
o envio, o saldo NÃO é estornado automaticamente (evita pagar duas vezes);
o saque fica em `needs_review` para conferência manual.
"""
from dataclasses import dataclass

from .database import Database
from .economy import InvalidAmount, apply_delta
from .game_interface import GameInterface, GiftResult
from .logger import get_logger

log = get_logger("withdrawal")

WITHDRAW_MIN = 1000
WITHDRAW_MAX = 50000
FEE_BOT = 500
FEE_GAME = 100

PENDING, SENDING, COMPLETED, FAILED, NEEDS_REVIEW = "pending", "sending", "completed", "failed", "needs_review"


@dataclass(frozen=True)
class Withdrawal:
    id: int
    player_id: int
    amount: int
    fee_bot: int
    fee_game: int
    net: int


class WithdrawalService:
    def __init__(self, db: Database, game: GameInterface):
        self.db = db
        self.game = game

    def request(self, player_id: int, amount: int) -> Withdrawal:
        if not isinstance(amount, int) or not (WITHDRAW_MIN <= amount <= WITHDRAW_MAX):
            raise InvalidAmount(f"saque deve estar entre {WITHDRAW_MIN} e {WITHDRAW_MAX}")
        net = amount - FEE_BOT - FEE_GAME
        with self.db.transaction() as conn:
            wid = conn.execute(
                "INSERT INTO withdrawals(player_id, amount, fee_bot, fee_game, net, status) VALUES(?,?,?,?,?,?)",
                (player_id, amount, FEE_BOT, FEE_GAME, net, PENDING),
            ).lastrowid
            apply_delta(conn, player_id, -amount, "withdrawal_reserve", ref=f"withdrawal:{wid}")
        log.info("Saque #%s reservado id=%s valor=%s líquido=%s", wid, player_id, amount, net)
        return Withdrawal(wid, player_id, amount, FEE_BOT, FEE_GAME, net)

    def _set_status(self, conn, wid: int, status: str) -> None:
        conn.execute(
            "UPDATE withdrawals SET status = ?, updated_at = strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id = ?",
            (status, wid),
        )

    def execute(self, wid: int) -> str:
        with self.db.transaction() as conn:
            row = conn.execute("SELECT * FROM withdrawals WHERE id = ?", (wid,)).fetchone()
            if row is None or row["status"] != PENDING:
                return row["status"] if row else FAILED
            self._set_status(conn, wid, SENDING)  # persistido ANTES de tocar o jogo
        try:
            result = self.game.send_gift(row["player_id"], row["net"])
        except Exception:
            log.exception("Erro ao enviar presente do saque #%s", wid)
            result = GiftResult.UNKNOWN

        with self.db.transaction() as conn:
            if result is GiftResult.SENT:
                self._set_status(conn, wid, COMPLETED)
                status = COMPLETED
            elif result is GiftResult.FAILED:
                apply_delta(conn, row["player_id"], row["amount"], "withdrawal_refund", ref=f"withdrawal:{wid}")
                self._set_status(conn, wid, FAILED)
                status = FAILED
            else:
                self._set_status(conn, wid, NEEDS_REVIEW)
                status = NEEDS_REVIEW
        log.info("Saque #%s => %s", wid, status)
        return status

    def recover_interrupted(self) -> int:
        """Na inicialização: saques em 'sending' viram 'needs_review' (não estorna sozinho)."""
        with self.db.transaction() as conn:
            cur = conn.execute(
                "UPDATE withdrawals SET status = ?, updated_at = strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE status = ?",
                (NEEDS_REVIEW, SENDING),
            )
        if cur.rowcount:
            log.error("%s saque(s) interrompido(s) marcados para revisão manual", cur.rowcount)
        return cur.rowcount
