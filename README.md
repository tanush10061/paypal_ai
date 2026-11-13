# PayInvoice AI

Type an invoice request in plain English. Claude (tool calling) turns it into structured data, you confirm, and the PayPal Invoicing API (sandbox) creates and sends it. A dashboard tracks status, and Claude drafts polite reminders for unpaid invoices, which PayPal's remind endpoint can send.

## How PayPal and AI are used
- **PayPal:** OAuth, `POST /v2/invoicing/invoices`, `/send`, list invoices, `/remind` (sandbox).
- **AI:** Claude via the Anthropic API. Forced tool call extracts invoice fields; a second call writes reminder emails.

## Run locally
1. Create sandbox REST app and a sandbox Business account at developer.paypal.com. Use the business account's email as `PAYPAL_MERCHANT_EMAIL`.
2. `cp .env.example .env` and fill in values.
3. `pip install -r requirements.txt && uvicorn main:app --reload`
4. Open http://localhost:8000. Use a sandbox Personal account email as the invoice recipient, then log in at sandbox.paypal.com to pay it.

## Deploy
Push to GitHub, create a Render Blueprint from `render.yaml`, add the four env vars.

## License
MIT
