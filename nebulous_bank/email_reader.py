"""Leitura das notificações de presente e crédito de depósitos."""
import re
from dataclasses import dataclass
from typing import Optional

from .economy import Economy
from .game_interface import GameInterface
from .logger import get_logger

log = get_logger("email_reader")

# Ex.: "Darwin(4231582) sent you a gift of 10000 plasma!"  (padrão estrito)
_GIFT = re.compile(r"^(?P<name>.+)\((?P<id>\d{1,12})\) sent you a gift of (?P<amount>\d{1,12}) plasma!$")


@dataclass(frozen=True)
class Gift:
    name: str
    player_id: int
    amount: int


def parse_gift(text: str) -> Optional[Gift]:
    m = _GIFT.match(text.strip())
    if not m:
        return None
    amount = int(m.group("amount"))
    if amount <= 0:
        return None
    return Gift(m.group("name").strip(), int(m.group("id")), amount)


class EmailReader:
    def __init__(self, game: GameInterface, economy: Economy):
        self.game, self.economy = game, economy

    def poll(self) -> int:
        credited = 0
        for mail in self.game.read_new_mail():
            gift = parse_gift(mail.text)
            if gift is None:
                log.warning("E-mail fora do padrão, ignorado (uid=%s)", mail.uid)
                continue
            try:
                if self.economy.process_deposit(f"mail:{mail.uid}", gift.player_id, gift.name, gift.amount) is not None:
                    credited += 1
            except Exception:
                log.exception("Falha ao processar e-mail uid=%s", mail.uid)
        return credited
