from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from supabase import create_client, Client
from models import User, SubscriptionTier, SessionCreate, SuggestionRequest
import os
from dotenv import load_dotenv
import stripe
import groq
from usage_service import check_user_limits, track_usage
from resume_parser import parse_resume
from datetime import datetime

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

supabase: Client = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY")
)

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
groq_client = groq.Groq(api_key=os.getenv("GROQ_API_KEY"))

async def get_current_user(authorization: str = Header(None)) -> User:
    if not authorization:
        raise HTTPException(status_code=401, detail="No authorization header")
    token = authorization.replace("Bearer ", "")
    try:
        response = supabase.auth.get_user(token)
        user_data = supabase.table("users").select("*").eq("id", response.user.id).single().execute()
        return User(**user_data.data)
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid token")

@app.get("/")
def root():
    return {"status": "ok", "message": "Interview Whisper API"}

@app.get("/api/usage")
async def get_usage(user: User = Depends(get_current_user)):
    return await check_user_limits(user, supabase)

@app.post("/api/sessions")
async def create_session(data: SessionCreate, user: User = Depends(get_current_user)):
    limits = await check_user_limits(user, supabase)
    if not limits["can_start"]:
        raise HTTPException(status_code=403, detail="Usage limit reached")
    session = supabase.table("sessions").insert({
        "user_id": user.id,
        "job_title": data.job_title,
        "company": data.company,
        "job_description_id": data.job_description_id,
        "session_type": data.session_type,
        "started_at": datetime.utcnow().isoformat(),
        "status": "active"
    }).execute()
    return session.data[0]

@app.post("/api/suggest")
async def get_suggestion(data: SuggestionRequest, user: User = Depends(get_current_user)):
    prompt = f"""You are an expert interview coach helping someone answer interview questions.
    
Question: {data.question}
{f'Resume: {data.resume_text[:500]}' if data.resume_text else ''}
{f'Job Description: {data.job_description[:300]}' if data.job_description else ''}
{f'Guidelines: {data.guidelines}' if data.guidelines else ''}

Provide a concise, confident answer suggestion using the STAR method where appropriate. 
Keep it under 200 words and make it natural to speak aloud."""

    response = groq_client.chat.completions.create(
        model="llama3-8b-8192",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=300
    )
    suggestion = response.choices[0].message.content
    supabase.table("session_suggestions").insert({
        "session_id": data.session_id,
        "question": data.question,
        "suggestion": suggestion
    }).execute()
    return {"suggestion": suggestion}

@app.post("/api/sessions/{session_id}/end")
async def end_session(session_id: str, user: User = Depends(get_current_user)):
    supabase.table("sessions").update({
        "status": "completed",
        "ended_at": datetime.utcnow().isoformat()
    }).eq("id", session_id).eq("user_id", user.id).execute()
    return {"status": "completed"}

@app.get("/api/sessions")
async def get_sessions(user: User = Depends(get_current_user)):
    response = supabase.table("sessions").select("*").eq("user_id", user.id).order("started_at", desc=True).execute()
    return response.data

@app.post("/api/stripe/webhook")
async def stripe_webhook(request: dict):
    # Handle subscription updates
    event_type = request.get("type")
    if event_type in ["customer.subscription.created", "customer.subscription.updated"]:
        subscription = request["data"]["object"]
        customer_id = subscription["customer"]
        status = subscription["status"]
        price_id = subscription["items"]["data"][0]["price"]["id"]
        tier = "free"
        if price_id == os.getenv("STRIPE_STARTER_PRICE_ID"):
            tier = "starter"
        elif price_id == os.getenv("STRIPE_PRO_PRICE_ID"):
            tier = "pro"
        elif price_id == os.getenv("STRIPE_ELITE_PRICE_ID"):
            tier = "elite"
        if status == "active":
            supabase.table("users").update({"tier": tier}).eq("stripe_customer_id", customer_id).execute()
    elif request.get("type") == "customer.subscription.deleted":
        customer_id = request["data"]["object"]["customer"]
        supabase.table("users").update({"tier": "free"}).eq("stripe_customer_id", customer_id).execute()
    return {"status": "ok"}

@app.post("/create-checkout-session")
async def create_checkout_session(data: dict, user: User = Depends(get_current_user)):
    user_data = supabase.table("users").select("stripe_customer_id").eq("id", user.id).single().execute()
    customer_id = user_data.data.get("stripe_customer_id")
    if not customer_id:
        customer = stripe.Customer.create(email=user.email, metadata={"supabase_user_id": user.id})
        customer_id = customer.id
        supabase.table("users").update({"stripe_customer_id": customer_id}).eq("id", user.id).execute()
    session = stripe.checkout.Session.create(
        customer=customer_id,
        line_items=[{"price": data["priceId"], "quantity": 1}],
        mode="subscription",
        success_url=data["successUrl"],
        cancel_url=data["cancelUrl"]
    )
    return {"sessionId": session.id}