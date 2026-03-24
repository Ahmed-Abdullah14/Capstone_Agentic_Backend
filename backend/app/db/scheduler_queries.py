from app.db.supabase_client import supabase

def get_due_scheduled_posts(now_iso: str):
    response = supabase.table("calendar_posts") \
        .select("*") \
        .eq("status", "scheduled") \
        .lte("scheduled_at", now_iso) \
        .execute()
    return response.data

def mark_post_as_published(post_id: str):
    supabase.table("calendar_posts") \
        .update({"status": "published"}) \
        .eq("id", post_id) \
        .execute()

def log_publish_attempt(post_id: str, succeeded: bool, message: str = ""):
    data = {
        "calendar_post_id": post_id,
        "succeeded": succeeded
    }
    if message:
        data["response"] = {"message": message}
    supabase.table("publish_attempts").insert(data).execute()
