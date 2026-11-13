import os, json, time, base64
import httpx
from openai import OpenAI
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

load_dotenv()
PP = "https://api-m.sandbox.paypal.com"
CID, SECRET = os.environ["PAYPAL_CLIENT_ID"], os.environ["PAYPAL_CLIENT_SECRET"]
MODEL = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")
llm = OpenAI(base_url=os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1"), api_key=os.environ["LLM_API_KEY"])
app = FastAPI(title="PayInvoice AI")
_tok = {"v": None, "exp": 0}


def token() -> str:
    if _tok["v"] and time.time() < _tok["exp"]:
        return _tok["v"]
    r = httpx.post(f"{PP}/v1/oauth2/token", data={"grant_type": "client_credentials"}, auth=(CID, SECRET))
    r.raise_for_status()
    d = r.json()
    _tok.update(v=d["access_token"], exp=time.time() + d["expires_in"] - 60)
    return _tok["v"]


def pp(method, path, **kw):
    r = httpx.request(method, PP + path, headers={"Authorization": f"Bearer {token()}", "Content-Type": "application/json"}, timeout=30, **kw)
    if r.status_code >= 400:
        raise HTTPException(r.status_code, r.text)
    return r.json() if r.content else {}


INVOICE_TOOL = {"type": "function", "function": {
    "name": "create_invoice_draft",
    "description": "Extract invoice details from the user's request.",
    "parameters": {
        "type": "object",
        "properties": {
            "client_name": {"type": "string"},
            "client_email": {"type": "string"},
            "currency": {"type": "string", "description": "ISO code, default USD"},
            "due_in_days": {"type": "integer"},
            "items": {"type": "array", "items": {"type": "object", "properties": {
                "description": {"type": "string"}, "quantity": {"type": "number"}, "unit_price": {"type": "number"}},
                "required": ["description", "quantity", "unit_price"]}},
            "note": {"type": "string", "description": "Short friendly note to the client"},
        },
        "required": ["client_name", "client_email", "items"],
    },
}}


class Parse(BaseModel):
    text: str


@app.post("/api/parse")
def parse(p: Parse):
    r = llm.chat.completions.create(
        model=MODEL, max_tokens=1000, tools=[INVOICE_TOOL],
        tool_choice={"type": "function", "function": {"name": "create_invoice_draft"}},
        messages=[{"role": "user", "content": p.text}],
    )
    calls = r.choices[0].message.tool_calls
    if not calls:
        raise HTTPException(422, "Could not parse an invoice from that text")
    return json.loads(calls[0].function.arguments)


class Draft(BaseModel):
    client_name: str
    client_email: str
    currency: str = "USD"
    due_in_days: int = 14
    items: list[dict]
    note: str = ""


@app.post("/api/invoices")
def create(d: Draft):
    merchant = os.environ["PAYPAL_MERCHANT_EMAIL"]
    due = time.strftime("%Y-%m-%d", time.gmtime(time.time() + d.due_in_days * 86400))
    body = {
        "detail": {"currency_code": d.currency, "note": d.note, "payment_term": {"due_date": due}},
        "invoicer": {"name": {"business_name": "PayInvoice AI Demo"}, "email_address": merchant},
        "primary_recipients": [{"billing_info": {"name": {"given_name": d.client_name}, "email_address": d.client_email}}],
        "items": [{"name": i["description"], "quantity": str(i["quantity"]),
                   "unit_amount": {"currency_code": d.currency, "value": f'{float(i["unit_price"]):.2f}'}} for i in d.items],
    }
    created = pp("POST", "/v2/invoicing/invoices", json=body)
    inv_id = created["href"].rsplit("/", 1)[-1]
    pp("POST", f"/v2/invoicing/invoices/{inv_id}/send", json={"send_to_recipient": True})
    return {"id": inv_id}


@app.get("/api/invoices")
def list_invoices():
    data = pp("GET", "/v2/invoicing/invoices?page=1&page_size=20&total_required=true")
    out = []
    for i in data.get("items", []):
        amt = i.get("amount", {})
        out.append({
            "id": i["id"], "number": i["detail"].get("invoice_number"), "status": i.get("status"),
            "due": i["detail"].get("payment_term", {}).get("due_date"),
            "recipient": (i.get("primary_recipients") or [{}])[0].get("billing_info", {}).get("email_address"),
            "amount": f'{amt.get("value", "?")} {amt.get("currency_code", "")}',
        })
    return out


@app.post("/api/invoices/{inv_id}/reminder")
def reminder(inv_id: str):
    i = pp("GET", f"/v2/invoicing/invoices/{inv_id}")
    r = llm.chat.completions.create(
        model=MODEL, max_tokens=400,
        messages=[{"role": "user", "content":
                   "Write a short, polite, friendly payment reminder email (subject + body) for this unpaid invoice. "
                   f"Do not invent facts.\n{json.dumps({'number': i['detail'].get('invoice_number'), 'status': i.get('status'), 'due': i['detail'].get('payment_term', {}).get('due_date'), 'amount': i.get('amount')})}"}],
    )
    return {"draft": r.choices[0].message.content}


@app.post("/api/invoices/{inv_id}/send-reminder")
def send_reminder(inv_id: str):
    pp("POST", f"/v2/invoicing/invoices/{inv_id}/remind", json={"send_to_recipient": True, "subject": "Friendly payment reminder"})
    return {"ok": True}


@app.get("/")
def index():
    return FileResponse("static/index.html")


app.mount("/static", StaticFiles(directory="static"), name="static")
