import hashlib
import hmac
import json
import os

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr


load_dotenv()

PAYSTACK_SECRET_KEY = os.getenv("PAYSTACK_SECRET_KEY")

if not PAYSTACK_SECRET_KEY:
    raise RuntimeError("PAYSTACK_SECRET_KEY is missing")


app = FastAPI(
    title="Paystack Webhook Demo",
    description="Simple FastAPI + Paystack webhook learning project",
    version="1.0.0",
)


# --------------------------------------------------
# HOME
# --------------------------------------------------

@app.get("/")
async def home():
    return {
        "status": True,
        "message": "Paystack webhook demo is running",
        "webhook_url": "/webhooks/paystack",
        "docs": "/docs",
    }


# --------------------------------------------------
# HEALTH CHECK
# --------------------------------------------------

@app.get("/health")
async def health():
    return {
        "status": "healthy"
    }


# --------------------------------------------------
# PAYMENT REQUEST
# --------------------------------------------------

class PaymentRequest(BaseModel):
    email: EmailStr
    amount: int


# --------------------------------------------------
# INITIALIZE PAYSTACK PAYMENT
# --------------------------------------------------

@app.post("/payments/initialize")
async def initialize_payment(payment: PaymentRequest):

    # Paystack expects the amount in kobo.
    # Example:
    # ₦100 = 10,000 kobo
    amount_in_kobo = payment.amount * 100

    payload = {
        "email": payment.email,
        "amount": amount_in_kobo,
    }

    headers = {
        "Authorization": f"Bearer {PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json",
    }

    try:

        async with httpx.AsyncClient(timeout=30) as client:

            response = await client.post(
                "https://api.paystack.co/transaction/initialize",
                json=payload,
                headers=headers,
            )

    except httpx.RequestError as error:

        raise HTTPException(
            status_code=500,
            detail=f"Could not connect to Paystack: {error}",
        )

    if response.status_code != 200:

        raise HTTPException(
            status_code=response.status_code,
            detail=response.text,
        )

    return response.json()


# --------------------------------------------------
# PAYSTACK WEBHOOK
# --------------------------------------------------

@app.post("/webhooks/paystack")
async def paystack_webhook(request: Request):

    # ----------------------------------------------
    # 1. Get the raw request body
    # ----------------------------------------------

    body = await request.body()

    # ----------------------------------------------
    # 2. Get Paystack signature
    # ----------------------------------------------

    signature = request.headers.get(
        "x-paystack-signature"
    )

    if not signature:

        raise HTTPException(
            status_code=400,
            detail="Missing Paystack signature",
        )

    # ----------------------------------------------
    # 3. Generate our own signature
    # ----------------------------------------------

    expected_signature = hmac.new(
        PAYSTACK_SECRET_KEY.encode("utf-8"),
        body,
        hashlib.sha512,
    ).hexdigest()

    # ----------------------------------------------
    # 4. Compare signatures
    # ----------------------------------------------

    if not hmac.compare_digest(
        expected_signature,
        signature,
    ):

        raise HTTPException(
            status_code=401,
            detail="Invalid Paystack signature",
        )

    # ----------------------------------------------
    # 5. Convert JSON to Python dictionary
    # ----------------------------------------------

    try:

        event = json.loads(body)

    except json.JSONDecodeError:

        raise HTTPException(
            status_code=400,
            detail="Invalid JSON payload",
        )

    # ----------------------------------------------
    # 6. Extract important information
    # ----------------------------------------------

    event_name = event.get("event")

    data = event.get("data", {})

    reference = data.get("reference")
    amount = data.get("amount")
    currency = data.get("currency")
    status = data.get("status")

    customer = data.get("customer", {})

    email = customer.get("email")

    # ----------------------------------------------
    # 7. Print webhook information
    # ----------------------------------------------

    print("")
    print("====================================")
    print("      PAYSTACK WEBHOOK RECEIVED")
    print("====================================")

    print(f"Event:     {event_name}")
    print(f"Reference: {reference}")
    print(f"Amount:    {amount}")
    print(f"Currency:  {currency}")
    print(f"Status:    {status}")
    print(f"Email:     {email}")

    print("====================================")
    print("FULL PAYLOAD:")
    print("====================================")

    print(
        json.dumps(
            event,
            indent=2
        )
    )

    print("====================================")
    print("")

    # ----------------------------------------------
    # 8. Handle successful payment
    # ----------------------------------------------

    if event_name == "charge.success":

        print(
            f"Payment successful: {reference}"
        )

    # ----------------------------------------------
    # 9. Tell Paystack we received the webhook
    # ----------------------------------------------

    return JSONResponse(
        status_code=200,
        content={
            "status": True,
            "message": "Webhook received successfully",
            "event": event_name,
            "reference": reference,
        },
    )
