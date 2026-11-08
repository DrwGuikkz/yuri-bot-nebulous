"""Armazenamento persistente (SQLite) com transações atômicas.

Toda alteração de saldo acontece dentro de `Database.transaction()`, que usa
BEGIN IMMEDIATE (trava de escrita) + lock de processo. Saldo negativo é
impedido também pelo CHECK(balance >= 0) no próprio banco.
"""
import sqlite3
import threading
from contextlib import contextmanager

_TS = "strftime('%Y-%m-%dT%H:%M:%fZ','now')"

SCHEMA = f"""
CREATE TABLE IF NOT EXISTS players(
    player_id  INTEGER PRIMARY KEY,
    username   TEXT NOT NULL,
    balance    INTEGER NOT NULL DEFAULT 0 CHECK(balance >= 0),
    created_at TEXT NOT NULL DEFAULT ({_TS})
);
CREATE INDEX IF NOT EXISTS idx_players_username ON players(username COLLATE NOCASE);

-- Livro-razão: toda movimentação (depósito, aposta, saque, estorno).
CREATE TABLE IF NOT EXISTS transactions(
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id     INTEGER NOT NULL REFERENCES players(player_id),
    type          TEXT NOT NULL,
    amount        INTEGER NOT NULL,
    balance_after INTEGER NOT NULL,
    ref           TEXT,
    created_at    TEXT NOT NULL DEFAULT ({_TS})
);
CREATE INDEX IF NOT EXISTS idx_tx_player ON transactions(player_id, id);

CREATE TABLE IF NOT EXISTS processed_notifications(
    key TEXT PRIMARY KEY, created_at TEXT NOT NULL DEFAULT ({_TS})
);
CREATE TABLE IF NOT EXISTS processed_commands(
    key TEXT PRIMARY KEY, created_at TEXT NOT NULL DEFAULT ({_TS})
);

CREATE TABLE IF NOT EXISTS bets(
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id   INTEGER NOT NULL REFERENCES players(player_id),
    amount      INTEGER NOT NULL,
    player_roll INTEGER NOT NULL,
    bank_roll   INTEGER NOT NULL,
    won         INTEGER NOT NULL,
    payout      INTEGER NOT NULL,
    created_at  TEXT NOT NULL DEFAULT ({_TS})
);

CREATE TABLE IF NOT EXISTS withdrawals(
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id  INTEGER NOT NULL REFERENCES players(player_id),
    amount     INTEGER NOT NULL,
    fee_bot    INTEGER NOT NULL,
    fee_game   INTEGER NOT NULL,
    net        INTEGER NOT NULL,
    status     TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT ({_TS}),
    updated_at TEXT NOT NULL DEFAULT ({_TS})
);
"""


class Database:
    def __init__(self, path: str = "bank.db"):
        self.path = path
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=FULL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.executescript(SCHEMA)

    @contextmanager
    def transaction(self):
        """Transação atômica: commit se sair normalmente, rollback se houver exceção."""
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                yield self._conn
            except BaseException:
                self._conn.execute("ROLLBACK")
                raise
            else:
                self._conn.execute("COMMIT")

    def query_one(self, sql: str, params=()):
        with self._lock:
            return self._conn.execute(sql, params).fetchone()

    def query_all(self, sql: str, params=()):
        with self._lock:
            return self._conn.execute(sql, params).fetchall()

    def close(self):
        with self._lock:
            self._conn.close()
