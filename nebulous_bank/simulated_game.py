"""Jogo SIMULADO em memória, só para desenvolvimento e testes.
NÃO conversa com o Nebulous.io real."""
from collections import deque
from typing import List

from .game_interface import ChatMessage, GameInterface, GiftResult, MailMessage


class SimulatedGame(GameInterface):
    def __init__(self):
        self.chat_in, self.mail_in = deque(), deque()
        self.chat_out: List[str] = []
        self.gifts_sent = []
        self.gift_result = GiftResult.SENT
        self._n = 0

    def push_chat(self, author, text, author_id=None, uid=None):
        self._n += 1
        self.chat_in.append(ChatMessage(uid or f"c{self._n}", author, text, author_id))

    def push_mail(self, text, uid=None):
        self._n += 1
        self.mail_in.append(MailMessage(uid or f"m{self._n}", text))

    def read_new_chat(self):
        out = list(self.chat_in); self.chat_in.clear(); return out

    def read_new_mail(self):
        out = list(self.mail_in); self.mail_in.clear(); return out

    def send_chat(self, text):
        self.chat_out.append(text)

    def send_gift(self, player_id, plasma):
        if self.gift_result is GiftResult.SENT:
            self.gifts_sent.append((player_id, plasma))
        return self.gift_result
