# Banco virtual de Plasma – Nebulous.io

Núcleo em Python 3.9+ (somente biblioteca padrão), testado. **A integração real com o jogo não está
incluída** (ver `FEASIBILITY.md`); existe um `SimulatedGame` apenas para desenvolvimento.

```
python -m unittest discover -s tests -v
python -m nebulous_bank.main --simulate
```

## Módulos (`nebulous_bank/`)
- `main` – inicialização, laço (e-mails → chat) e recuperação de saques interrompidos
- `chat_reader` – interpreta `!saldo`, `!apostar N`, `!sacar N`
- `email_reader` – interpreta `Nome(ID) sent you a gift of N plasma!` e credita
- `command_handler` – executa comandos, dedupe, trava por jogador, respostas
- `economy` – único ponto que altera saldo + livro-razão (`transactions`)
- `gambling` – d10 vs d10, `secrets.SystemRandom`, empate = banca
- `withdrawal` – reserva → envio → completed / failed (estorno) / needs_review
- `database` – SQLite (WAL), transações `BEGIN IMMEDIATE`, `CHECK(balance >= 0)`
- `logger` – console + arquivo rotativo
- `game_interface` – contrato com o jogo; `simulated_game` – só testes

## Decisões de segurança
- Comando e e-mail são marcados como processados **antes/na mesma transação** do efeito (no máximo uma vez).
- Débito, sorteio, prêmio e registro da aposta são uma única transação.
- Saque em `sending` após queda ou resultado `UNKNOWN` → `needs_review`, nunca estorno automático.
- Histórico de depósitos/apostas/saques: tabelas `transactions`, `bets`, `withdrawals`.
