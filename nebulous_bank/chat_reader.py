"""Leitura e interpretação do chat."""
import re
from dataclasses import dataclass
from typing import Optional

from .game_interface import GameInterface
from .logger import get_logger

log = get_logger("chat_reader")

_CMD = re.compile(r"^!(saldo|apostar|sacar)(?:\s+(\S+))?\s*$", re.IGNORECASE)
_DIGITS = re.compile(r"^\d{1,9}$")


@dataclass(frozen=True)
class ParsedCommand:
    name: str                 # saldo | apostar | sacar
    amount: Optional[int]     # None se ausente/inválido (para apostar/sacar)
    valid: bool


def parse_command(text: str) -> Optional[ParsedCommand]:
    m = _CMD.match(text.strip())
    if not m:
        return None
    name, arg = m.group(1).lower(), m.group(2)
    if name == "saldo":
        return ParsedCommand(name, None, arg is None)
    if arg is not None and _DIGITS.match(arg):
        return ParsedCommand(name, int(arg), True)
    return ParsedCommand(name, None, False)


class ChatReader:
    def __init__(self, game: GameInterface, handler, bot_name: str):
        self.game, self.handler, self.bot_name = game, handler, bot_name.lower()

    def poll(self) -> int:
        n = 0
        for msg in self.game.read_new_chat():
            if msg.author_name.lower() == self.bot_name:
                continue  # ignora as próprias mensagens
            cmd = parse_command(msg.text)
            if cmd is None:
                continue
            n += 1
            try:
                self.handler.handle(msg, cmd)
            except Exception:
                log.exception("Erro ao tratar comando uid=%s", msg.uid)
        return n
