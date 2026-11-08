# Análise de viabilidade técnica – Nebulous.io (Android)

## Premissa
Não há API pública documentada do Nebulous.io para chat, e-mail interno ou envio de presentes.
Nada abaixo foi implementado como "funcionando": é o que é **possível em tese** e o que o núcleo
espera de quem integrar (`game_interface.GameInterface`).

## O que é realmente possível

| Necessidade | Mecanismo possível | Dependências / limites |
|---|---|---|
| Ler chat | Captura de tela (MediaProjection no Android, ou `adb exec-out screencap` / emulador) + OCR | O jogo é Unity/OpenGL: a árvore de acessibilidade do Android normalmente **não expõe o texto**. OCR é sujeito a erros (nomes com símbolos, 0/O, 1/l). |
| Ler e-mails | Mesma técnica: abrir a caixa de entrada por toques e ler por OCR | Precisa de um `uid` estável por e-mail (ex.: data/hora + posição + hash). Sem isso, não dá para deduplicar com segurança. |
| Enviar mensagem no chat | Injeção de toques/teclado (AccessibilityService `dispatchGesture`, `adb input`, uiautomator) | Calibração por resolução; quebra a cada atualização de interface. |
| Enviar presente | Idem: navegar menus, digitar ID e quantidade, confirmar | Confirmar o sucesso (`SENT`) também depende de ler a tela. |
| API/rede do jogo | Interceptar/reproduzir protocolo | **Não recomendado**: engenharia reversa, TLS, alto risco de banimento. |

## Pontos críticos
1. **Identidade (maior risco).** O chat provavelmente mostra só o *nome*; o e-mail traz nome **e** ID.
   Associar nome→ID só é seguro se o nome for único. Nomes podem ser trocados/duplicados, então alguém
   pode se passar por outro jogador e apostar o saldo dele. Mitigações: usar `ChatMessage.author_id` se a
   integração conseguir o ID real (perfil do autor); caso contrário, o núcleo bloqueia nomes ambíguos,
   mas **não resolve** personificação por troca de nome. Considere um código de verificação por presente.
2. **Resultado do envio incerto.** Automação de UI pode falhar sem avisar. Por isso `GiftResult` tem
   `UNKNOWN`: nesse caso o saldo **não é estornado** (evita pagar duas vezes) e o saque vai para
   `needs_review`. O requisito "estornar se falhar" só vale quando a falha é *confirmada*.
3. **Dedupe.** Depende de `uid` confiável de mensagens/e-mails vindo da integração.
4. **Termos de uso.** Automatizar o cliente costuma violar os termos de jogos online e pode causar
   banimento da conta do bot (com o saldo dos jogadores dentro). Verifique os termos antes de operar.
5. **Aposta com moeda que pode ter valor real.** Se Plasma é comprado com dinheiro, isso pode cair em
   regras de jogos de azar/apostas da sua jurisdição. Avalie antes de operar com terceiros.
6. **Vantagem da banca.** Pela regra (empate vai para a banca) o jogador vence em 45% das rodadas
   e recebe 2x: retorno esperado = 90% da aposta (banca com 10% de vantagem). Mostre isso aos jogadores.
7. **Execução serial.** Há uma única tela/dispositivo: o laço principal é sequencial de propósito.

## Contrato para a integração
Implemente `GameInterface`: `read_new_chat`, `send_chat`, `read_new_mail`, `send_gift -> GiftResult`.
Rode: `python -m nebulous_bank.main --adapter pacote.modulo:Classe --bot-name SeuBot`.
