# PayInvoice AI

Type an invoice request in plain English. An LLM (tool calling, free tier via Groq or Gemini) turns it into structured data, you confirm, and the PayPal Invoicing API (sandbox) creates and sends it. A dashboard tracks status, and the LLM drafts polite reminders for unpaid invoices.

## How PayPal and AI are used
- **PayPal:** OAuth, `POST /v2/invoicing/invoices`, `/send`, list invoices, `/remind` (sandbox).
- **AI:** Any OpenAI-compatible LLM (default: Groq Llama 3.3 70B, free). Forced tool call extracts invoice fields; a second call writes reminder emails.

## Run locally
1. Create sandbox REST app and a sandbox Business account at developer.paypal.com. Use the business account's email as `PAYPAL_MERCHANT_EMAIL`.
2. `cp .env.example .env` and fill in values.
3. `pip install -r requirements.txt && uvicorn main:app --reload`
4. Open http://localhost:8000. Use a sandbox Personal account email as the invoice recipient, then log in at sandbox.paypal.com to pay it.

## Deploy
Push to GitHub, create a Render Blueprint from `render.yaml`, add the env vars from .env.example.

## License
MIT
