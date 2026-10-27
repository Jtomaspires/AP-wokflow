O envio no Approve já existe. Com `NYLAS_SEND_ENABLED=true`, `NYLAS_API_KEY` e `NYLAS_GRANT_ID`, o processo da API faz `messages/send` para `draft.to_email`. Sem túnel, a receção é `python scripts/poll_nylas.py`, que publica em `POST /webhook/mock`.

O resto desta página é só o webhook, se quiseres push em vez do poller. O segredo do webhook continua a ser obrigatório nesse caminho. A API key e o grant já servem o envio.

**1. Sobe a API na porta 8000** (e o worker, o Postgres e o Redis). A Nylas só grava o webhook se o GET do challenge responder.

**2. Noutro terminal:**

```powershell
ngrok http 8000
```

**3. No painel da Nylas**, na mesma app do Gmail, cria um webhook novo e deixa o `/events` da outra app como está.

- URL: `https://<o-host-do-ngrok>/webhook/nylas`
- Trigger: só `message.created`
- O segredo que a Nylas mostra é deste URL. O `WEBHOOK_SECRET` do `/events` não serve.

**4. No `.env`**, não no `.env.dev`:

```text
NYLAS_WEBHOOK_SECRET=<segredo deste webhook>
NYLAS_API_URI=https://api.us.nylas.com
SENDER_DOMAIN_WHITELIST=acme-supplies.com,group-subsidiary.com,p2p-branch.com,company.com,vendor.com,gmail.com
```

O domínio extra é o de quem escreve **para** a caixa. O default de `SENDER_DOMAIN_WHITELIST` já inclui `gmail.com`. Se o `.env` substitui a lista e não traz esse domínio, um teste enviado do Gmail fica em quarentena. Se o remetente for outro domínio, mete esse também.

`NYLAS_API_KEY` e `NYLAS_GRANT_ID` já são lidos no Approve quando `NYLAS_SEND_ENABLED=true`. O webhook só precisa do segredo.

**5. Reinicia a API e o worker.** Sem isso o processo continua sem o segredo.

**6. Confirma** que a Nylas guardou o webhook. Isso só acontece depois de `GET /webhook/nylas?challenge=...` devolver o challenge. Envia um email para a caixa ligada. No `http://localhost:5173` deve aparecer um ticket com esse assunto e remetente. O mesmo email outra vez não cria um segundo ticket.

O ngrok tem de ficar aberto. Se o URL mudar, o webhook na Nylas tem de ser actualizado e o segredo novo copiado para o `.env`.