"""Gerenciamento de saldos. Única camada que altera `players.balance`."""
from typing import List, Optional

from .database import Database
from .logger import get_logger

log = get_logger("economy")


class EconomyError(Exception): ...
class InsufficientBalance(EconomyError): ...
class PlayerNotFound(EconomyError): ...
class InvalidAmount(EconomyError): ...


def ensure_player(conn, player_id: int, username: str) -> None:
    conn.execute(
        "INSERT INTO players(player_id, username) VALUES(?, ?) "
        "ON CONFLICT(player_id) DO UPDATE SET username = excluded.username",
        (player_id, username),
    )


def apply_delta(conn, player_id: int, delta: int, tx_type: str, ref: Optional[str] = None) -> int:
    """Altera o saldo dentro de uma transação já aberta e grava no livro-razão."""
    row = conn.execute("SELECT balance FROM players WHERE player_id = ?", (player_id,)).fetchone()
    if row is None:
        raise PlayerNotFound(player_id)
    new_balance = row["balance"] + delta
    if new_balance < 0:
        raise InsufficientBalance(f"saldo {row['balance']} < {-delta}")
    conn.execute("UPDATE players SET balance = ? WHERE player_id = ?", (new_balance, player_id))
    conn.execute(
        "INSERT INTO transactions(player_id, type, amount, balance_after, ref) VALUES(?,?,?,?,?)",
        (player_id, tx_type, delta, new_balance, ref),
    )
    return new_balance


class Economy:
    def __init__(self, db: Database):
        self.db = db

    def get_balance(self, player_id: int) -> Optional[int]:
        row = self.db.query_one("SELECT balance FROM players WHERE player_id = ?", (player_id,))
        return None if row is None else row["balance"]

    def find_ids_by_name(self, name: str) -> List[int]:
        rows = self.db.query_all(
            "SELECT player_id FROM players WHERE username = ? COLLATE NOCASE", (name,)
        )
        return [r["player_id"] for r in rows]

    def process_deposit(self, notification_key: str, player_id: int, username: str, amount: int) -> Optional[int]:
        """Credita um depósito UMA única vez. Retorna novo saldo, ou None se duplicado."""
        if amount <= 0:
            raise InvalidAmount(amount)
        with self.db.transaction() as conn:
            cur = conn.execute(
                "INSERT OR IGNORE INTO processed_notifications(key) VALUES(?)", (notification_key,)
            )
            if cur.rowcount == 0:
                log.warning("Notificação duplicada ignorada: %s", notification_key)
                return None
            ensure_player(conn, player_id, username)
            balance = apply_delta(conn, player_id, amount, "deposit", ref=notification_key)
        log.info("Depósito: id=%s nome=%s +%s => %s", player_id, username, amount, balance)
        return balance
