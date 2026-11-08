"""Registro de atividades e erros (console + arquivo rotativo)."""
import logging
import os
from logging.handlers import RotatingFileHandler

_FMT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"


def setup_logger(path: str = "logs/bot.log", level: int = logging.INFO) -> logging.Logger:
    log = logging.getLogger("nebulous_bank")
    if log.handlers:
        return log
    log.setLevel(level)
    sh = logging.StreamHandler()
    sh.setFormatter(logging.Formatter(_FMT))
    log.addHandler(sh)
    if path:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        fh = RotatingFileHandler(path, maxBytes=2_000_000, backupCount=5, encoding="utf-8")
        fh.setFormatter(logging.Formatter(_FMT))
        log.addHandler(fh)
    return log


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"nebulous_bank.{name}")
