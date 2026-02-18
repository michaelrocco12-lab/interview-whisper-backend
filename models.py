from pydantic import BaseModel
from enum import Enum
from typing import Optional

class SubscriptionTier(str, Enum):
    FREE = "free"
    STARTER = "starter"
    PRO = "pro"
    ELITE = "elite"

class User(BaseModel):
    id: str
    email: str
    tier: SubscriptionTier = SubscriptionTier.FREE
    stripe_customer_id: Optional[str] = None
    stripe_subscription_id: Optional[str] = None

class SessionCreate(BaseModel):
    job_title: Optional[str] = None
    company: Optional[str] = None
    job_description_id: Optional[str] = None
    session_type: str = "live"

class SuggestionRequest(BaseModel):
    session_id: str
    question: str
    resume_text: Optional[str] = None
    job_description: Optional[str] = None
    guidelines: Optional[str] = None