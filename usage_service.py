from datetime import datetime, timedelta
from supabase import Client
from models import User, SubscriptionTier
import logging

logger = logging.getLogger(__name__)

TIER_LIMITS = {
    SubscriptionTier.FREE: {"sessions": 3, "minutes": 90, "tokens": 50000},
    SubscriptionTier.STARTER: {"sessions": 999, "minutes": 9999, "tokens": 1000000},
    SubscriptionTier.PRO: {"sessions": 999, "minutes": 9999, "tokens": 5000000},
    SubscriptionTier.ELITE: {"sessions": 999, "minutes": 9999, "tokens": 10000000},
}

async def check_user_limits(user: User, supabase: Client) -> dict:
    now = datetime.utcnow()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    response = supabase.table("usage_tracking").select("*").eq(
        "user_id", user.id
    ).gte("date", month_start.isoformat()).execute()
    usage_data = response.data if response.data else []
    sessions_used = len(set(u.get("session_id") for u in usage_data if u.get("session_id")))
    minutes_used = sum(u.get("minutes", 0) for u in usage_data)
    tokens_used = sum(u.get("tokens_used", 0) for u in usage_data)
    limits = TIER_LIMITS[user.tier]
    return {
        "can_start": (
            sessions_used < limits["sessions"] and
            minutes_used < limits["minutes"] and
            tokens_used < limits["tokens"]
        ),
        "sessions_used": sessions_used,
        "sessions_limit": limits["sessions"],
        "minutes_used": minutes_used,
        "minutes_limit": limits["minutes"],
        "tokens_used": tokens_used,
        "tokens_limit": limits["tokens"],
        "tier": user.tier.value,
        "reset_date": (month_start + timedelta(days=32)).replace(day=1).isoformat()
    }

async def track_usage(user_id: str, session_id: str, minutes: int, tokens: int, supabase: Client):
    try:
        supabase.table("usage_tracking").insert({
            "user_id": user_id,
            "session_id": session_id,
            "date": datetime.utcnow().isoformat(),
            "minutes": minutes,
            "tokens_used": tokens
        }).execute()
    except Exception as e:
        logger.error(f"Failed to track usage: {e}")