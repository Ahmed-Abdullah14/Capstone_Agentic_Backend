from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Optional

from app.config import SUPABASE_KEY, SUPABASE_URL
from app.db.supabase_client import supabase
from app.schemas.agent_results import BusinessProfilerResult, TrendSummary
from app.schemas.business_context import BusinessContext, check_utc

logger = logging.getLogger(__name__)


def _db_configured() -> bool:
    return bool(SUPABASE_URL and SUPABASE_KEY)


def _parse_uuid(value: str) -> Optional[uuid.UUID]:
    try:
        return uuid.UUID(str(value))
    except (ValueError, AttributeError):
        return None


def _parse_dt(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return check_utc(value)
    if isinstance(value, str):
        return check_utc(datetime.fromisoformat(value.replace("Z", "+00:00")))
    return None


def _format_location(city: Optional[str], country: Optional[str]) -> Optional[str]:
    parts = [p.strip() for p in (city or "", country or "") if p and str(p).strip()]
    return ", ".join(parts) if parts else None


def _dev_business_context(user_id: str, business_id: str) -> BusinessContext:
    """When Supabase is not configured or IDs are not UUIDs (e.g. local placeholders)."""
    return BusinessContext(
        user_id=user_id,
        business_id=business_id,
        business_name="Downtown Calgary Cafe",
        business_type="Local Cafe Shop",
        location="Calgary, Alberta",
        target_customers="Students and young professionals",
        instagram_handle="downtown_cafe",
    )


def _profiler_result_from_profile(business_id: str, profile: dict[str, Any] | None) -> BusinessProfilerResult:
    p = profile or {}
    return BusinessProfilerResult(
        business_id=business_id,
        primary_hashtags=list(p.get("primary_hashtags") or []),
        secondary_hashtags=list(p.get("secondary_hashtags") or []),
        location_keywords=list(p.get("location_keywords") or []),
        exclude_accounts=list(p.get("exclude_accounts") or []),
        ideal_follower_min=int(p.get("ideal_follower_min") or 0),
        ideal_follower_max=int(p.get("ideal_follower_max") or 1_000_000),
    )


def _has_profiler_hashtags(profile: dict[str, Any] | None) -> bool:
    p = profile or {}
    return bool(p.get("primary_hashtags") or [])


def _parse_hashtags_last_updated(profile: dict[str, Any] | None) -> Optional[datetime]:
    raw = (profile or {}).get("hashtags_last_updated")
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw
    if isinstance(raw, str):
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    return None


class BusinessProfilerQueries:
    """Supabase queries for businesses, pipeline state, competitors, posts, trends, and scheduling."""

    def _ensure_org_membership(self, user_id: str, org_id: str) -> None:
        uid = _parse_uuid(user_id)
        if uid is None:
            return
        r = (
            supabase.table("org_members")
            .select("user_id")
            .eq("org_id", org_id)
            .eq("user_id", str(uid))
            .limit(1)
            .execute()
        )
        if not (r.data or []):
            raise PermissionError("User is not a member of this business organization")

    def _fetch_business_row(self, business_id: str) -> dict[str, Any]:
        r = supabase.table("businesses").select("*").eq("id", business_id).limit(1).execute()
        rows = r.data or []
        if not rows:
            raise LookupError(f"No business found for id={business_id}")
        return rows[0]

    def _max_post_updated_at(self, business_id: str) -> Optional[datetime]:
        r = (
            supabase.table("posts")
            .select("updated_at")
            .eq("business_id", business_id)
            .order("updated_at", desc=True)
            .limit(1)
            .execute()
        )
        rows = r.data or []
        if not rows:
            return None
        return _parse_dt(rows[0].get("updated_at"))

    def _max_trend_summary_at(self, business_id: str) -> Optional[datetime]:
        r = (
            supabase.table("trend_summaries")
            .select("updated_at")
            .eq("business_id", business_id)
            .order("updated_at", desc=True)
            .limit(1)
            .execute()
        )
        rows = r.data or []
        if not rows:
            return None
        return _parse_dt(rows[0].get("updated_at"))

    def _exists_where(
        self, table: str, business_id: str, extra: Optional[dict[str, Any]] = None
    ) -> bool:
        q = supabase.table(table).select("id").eq("business_id", business_id).limit(1)
        if extra:
            for k, v in extra.items():
                q = q.eq(k, v)
        r = q.execute()
        return bool(r.data)

    def get_business_context(self, user_id: str, business_id: str) -> BusinessContext:
        if not _db_configured() or _parse_uuid(business_id) is None:
            logger.debug("Using dev BusinessContext (no DB or non-UUID business_id)")
            return _dev_business_context(user_id, business_id)

        row = self._fetch_business_row(business_id)
        self._ensure_org_membership(user_id, row["org_id"])

        profile = row.get("profile_json") or {}
        if isinstance(profile, str):
            profile = json.loads(profile)
        if not isinstance(profile, dict):
            profile = {}

        posts_last = self._max_post_updated_at(business_id)
        trends_last = self._max_trend_summary_at(business_id)

        has_top_posts = self._exists_where(
            "posts", business_id, extra={"is_selected": True}
        ) or self._exists_where("posts", business_id)

        has_trend = self._exists_where("trend_summaries", business_id)
        has_plan = self._exists_where("content_ideas", business_id) or self._exists_where(
            "content_calendars", business_id
        )
        scheduled = (
            supabase.table("scheduled_posts")
            .select("id")
            .eq("business_id", business_id)
            .in_("status", ["scheduled", "published"])
            .limit(1)
            .execute()
        )
        has_scheduled = bool(scheduled.data)

        return BusinessContext(
            user_id=user_id,
            business_id=business_id,
            business_name=row.get("name"),
            business_type=row.get("business_type"),
            location=_format_location(row.get("city"), row.get("country")),
            target_customers=row.get("ideal_customer"),
            instagram_handle=row.get("instagram_handle"),
            website=row.get("website_url"),
            has_hashtags=_has_profiler_hashtags(profile),
            has_top_posts=has_top_posts,
            has_trend_summary=has_trend,
            has_content_plan=has_plan,
            has_scheduled_posts=has_scheduled,
            hashtags_last_updated=_parse_hashtags_last_updated(profile),
            posts_last_scraped=posts_last,
            trends_last_updated=trends_last,
        )

    def get_scheduled_posts(self, day: date, business_id: str) -> list[dict[str, Any]]:
        if not _db_configured() or _parse_uuid(business_id) is None:
            return []
        start = datetime.combine(day, time.min, tzinfo=timezone.utc)
        end = start + timedelta(days=1)
        r = (
            supabase.table("scheduled_posts")
            .select("*")
            .eq("business_id", business_id)
            .gte("scheduled_at", start.isoformat())
            .lt("scheduled_at", end.isoformat())
            .order("scheduled_at")
            .execute()
        )
        return list(r.data or [])

    def get_all_scheduled_posts(self, business_id: str) -> list[dict[str, Any]]:
        if not _db_configured() or _parse_uuid(business_id) is None:
            return []
        now_iso = datetime.now(timezone.utc).isoformat()
        r = (
            supabase.table("scheduled_posts")
            .select("*")
            .eq("business_id", business_id)
            .gte("scheduled_at", now_iso)
            .order("scheduled_at")
            .execute()
        )
        return list(r.data or [])

    def cancel_scheduled_post(self, post_id: str) -> None:
        if not _db_configured() or _parse_uuid(post_id) is None:
            return
        supabase.table("scheduled_posts").delete().eq("id", post_id).execute()

    def schedule_post(
        self,
        business_id: str,
        scheduled_at: datetime,
        caption: Optional[str] = None,
        media: Optional[dict[str, Any]] = None,
        content_idea_id: Optional[str] = None,
        status: str = "scheduled",
    ) -> dict[str, Any]:
        if not _db_configured() or _parse_uuid(business_id) is None:
            raise RuntimeError("Supabase not configured or invalid business_id")
        payload: dict[str, Any] = {
            "business_id": business_id,
            "scheduled_at": check_utc(scheduled_at).isoformat(),
            "caption": caption,
            "media": media or {},
            "status": status,
        }
        if content_idea_id and _parse_uuid(content_idea_id):
            payload["content_idea_id"] = content_idea_id
        r = supabase.table("scheduled_posts").insert(payload).execute()
        rows = r.data or []
        if not rows:
            raise RuntimeError("schedule_post insert returned no row")
        return rows[0]

    def get_competitor_list(self, business_id: str) -> list[dict[str, Any]]:
        if not _db_configured() or _parse_uuid(business_id) is None:
            return []
        r = (
            supabase.table("competitors")
            .select("*")
            .eq("business_id", business_id)
            .eq("is_active", True)
            .order("username")
            .execute()
        )
        return list(r.data or [])

    def get_competitor_posts(
        self, business_id: str, *, selected_only: bool = False, limit: int = 500
    ) -> list[dict[str, Any]]:
        if not _db_configured() or _parse_uuid(business_id) is None:
            return []
        q = supabase.table("posts").select("*").eq("business_id", business_id)
        if selected_only:
            q = q.eq("is_selected", True)
        r = q.order("posted_at", desc=True).limit(limit).execute()
        return list(r.data or [])

    def _get_hashtags_sync(self, business_id: str) -> BusinessProfilerResult:
        if not _db_configured() or _parse_uuid(business_id) is None:
            return _profiler_result_from_profile(business_id, {})
        row = self._fetch_business_row(business_id)
        profile = row.get("profile_json") or {}
        if isinstance(profile, str):
            profile = json.loads(profile)
        if not isinstance(profile, dict):
            profile = {}
        return _profiler_result_from_profile(business_id, profile)

    async def get_hashtags(self, business_id: str) -> BusinessProfilerResult:
        return await asyncio.to_thread(self._get_hashtags_sync, business_id)

    def _get_trend_summary_sync(self, business_id: str) -> Optional[TrendSummary]:
        if not _db_configured() or _parse_uuid(business_id) is None:
            return None
        r = (
            supabase.table("trend_summaries")
            .select("*")
            .eq("business_id", business_id)
            .order("updated_at", desc=True)
            .limit(1)
            .execute()
        )
        rows = r.data or []
        if not rows:
            return None
        row = rows[0]
        raw_summary = row.get("summary") or {}
        if isinstance(raw_summary, str):
            raw_summary = json.loads(raw_summary)
        data = dict(raw_summary) if isinstance(raw_summary, dict) else {}
        if "created_at" not in data and row.get("created_at"):
            data["created_at"] = row["created_at"]
        return TrendSummary.model_validate(data)

    async def get_trend_summary(self, business_id: str) -> Optional[TrendSummary]:
        return await asyncio.to_thread(self._get_trend_summary_sync, business_id)
