# Operator guide

How to work a ticket in the console. The graph has already classified the email and matched it against the lab invoices. You decide whether a reply goes out.

Open `http://localhost:5173`, not `127.0.0.1:5173`. The session cookie is tied to `localhost`.

## Daily workflow

1. Sign in. The header shows your display name. The review stores your operator id (`op_joao`), not that name.
2. The **Awaiting human** tile is the queue. Click it if another tile is selected.
3. Open a ticket. Read **Email** and **Invoice** before the draft.
4. Read **Draft**. That text is the reply unless you change it in the dialog. An edit is what Approve stores and sends.
5. **Approve & send** when the draft is right and the invoice match is one invoice.
6. **Escalate** when you would not send that text, or when there is no draft.

Approve stays disabled when the ticket has no draft, or when the API badge is red. Escalate stays disabled while that badge is red. With the API up, Escalate still works when there is no draft.

## When to escalate

- There is no draft. That is the VAT case, a ref that exists in two SAP tables, and a payment marked paid with no clearing document.
- The amount in the email does not match the invoice.
- The supplier is new or unknown.
- The draft is addressed to `ap-owner@company.com` and you are not the person who should answer the approval owner.
- The invoice tab warns that SAP shows paid and there is no clearing document. Do not confirm payment.

## What happens after you choose

**Approve** stores your operator id on the review and marks the ticket resolved only after a mock send or a successful Nylas send. With `NYLAS_SEND_ENABLED` plus the API key and grant, it sends `draft.to_email` through Nylas. That address is the supplier only when the draft target is `sender`. A not-found invoice goes to `invoicing@company.com`. With the flag off, nothing is delivered and the ticket still resolves. If the flag is on and the key or grant is missing, or Nylas returns an error, the ticket stays `awaiting_human` and no review row is written.

**Escalate** marks the ticket escalated and stores your operator id. Nothing is sent.

## Questions

Ask the person who created the operator account with `scripts/seed_operator.py`.
