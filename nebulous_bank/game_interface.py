"""Fronteira entre o núcleo do banco e o jogo Nebulous.io.

O Nebulous.io NÃO oferece API pública. Ler o chat, ler o e-mail e enviar
presentes só é possível por automação de interface (ver FEASIBILITY.md).
Esse código fica fora do núcleo: quem integrar implementa `GameInterface`.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional


@dataclass(frozen=True)
class ChatMessage:
    uid: str                      # identificador ÚNICO e estável da mensagem (dedupe)
    author_name: str
    text: str
    author_id: Optional[int] = None  # use se a integração conseguir o ID real do autor


@dataclass(frozen=True)
class MailMessage:
    uid: str                      # identificador único e estável do e-mail (dedupe)
    text: str


class GiftResult(Enum):
    SENT = "sent"        # confirmado que o presente saiu
    FAILED = "failed"    # confirmado que NÃO saiu (pode estornar)
    UNKNOWN = "unknown"  # não dá para saber (NÃO estornar: revisão manual)


class GameInterface(ABC):
    @abstractmethod
    def read_new_chat(self) -> List[ChatMessage]: ...

    @abstractmethod
    def send_chat(self, text: str) -> None: ...

    @abstractmethod
    def read_new_mail(self) -> List[MailMessage]: ...

    @abstractmethod
    def send_gift(self, player_id: int, plasma: int) -> GiftResult: ...
