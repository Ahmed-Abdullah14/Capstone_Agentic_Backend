import os
import asyncio
import requests
import json
from datetime import datetime, timezone
from app.agents.base_agent import Agent
from app.db.business_profiler_queries import get_due_scheduled_posts, mark_post_as_published, log_publish_attempt
from app.config import FACEBOOK_ACCESS_TOKEN, IG_ACCOUNT_ID, FB_API_VERSION

class SchedulerAgent(Agent):
    def __init__(self, kernel):
        super().__init__(kernel=kernel, name="scheduler_agent")
        self.fb_access_token = FACEBOOK_ACCESS_TOKEN
        self.ig_account_id = IG_ACCOUNT_ID
        self.fb_api_version = FB_API_VERSION

    async def run(self):
        print(f"[{datetime.now()}] SchedulerAgent running...")
        try:
            now_iso = datetime.now(timezone.utc).isoformat()
            due_posts = get_due_scheduled_posts(now_iso)
            
            if not due_posts:
                print("No due posts found.")
                return

            print(f"Found {len(due_posts)} posts to process.")

            for item in due_posts:
                try:
                    await self._process_post(item)
                except Exception as e:
                    print(f"Error processing post {item.get('id')}: {e}")
                    try:
                        log_publish_attempt(item.get('id'), False, str(e))
                    except Exception as log_err:
                        print(f"Failed to log attempt for {item.get('id')}: {log_err}")

        except Exception as e:
            print(f"Scheduler failed to get due posts: {e}")

    async def _process_post(self, item):
        post_id = item.get("id")
        print(f"Processing post ID: {post_id}")
        
        media = item.get("media", {})
        if isinstance(media, str):
            try:
                media = json.loads(media)
            except Exception:
                pass
                
        video_url = media.get("reel_video_url") or media.get("video_url") or media.get("url")
        if not video_url:
            raise ValueError(f"Missing video URL in media JSON for post {post_id}")

        caption = item.get("caption", "")

        if not self.fb_access_token:
            raise ValueError("FACEBOOK_ACCESS_TOKEN is missing. Cannot publish reel.")

        container_url = f"https://graph.facebook.com/{self.fb_api_version}/{self.ig_account_id}/media"
        container_payload = {
            "media_type": "REELS",
            "video_url": video_url,
            "caption": caption,
            "access_token": self.fb_access_token
        }
        print("Creating Reel container...")
        container_res = await asyncio.to_thread(requests.post, container_url, params=container_payload)
        
        if not container_res.ok:
            raise Exception(f"Failed to create Reel container: {container_res.text}")
            
        container_data = container_res.json()
        creation_id = container_data.get("id")
        if not creation_id:
            raise Exception(f"No creation_id returned: {container_data}")

        print(f"Container created ({creation_id}). Waiting 60 seconds for processing...")
        await asyncio.sleep(60)

        publish_url = f"https://graph.facebook.com/{self.fb_api_version}/{self.ig_account_id}/media_publish"
        publish_payload = {
            "creation_id": creation_id,
            "access_token": self.fb_access_token
        }
        print("Publishing Reel...")
        publish_res = await asyncio.to_thread(requests.post, publish_url, params=publish_payload)

        if not publish_res.ok:
            raise Exception(f"Failed to publish Reel: {publish_res.text}")
            
        publish_data = publish_res.json()
        print(f"Reel published successfully! IG Media ID: {publish_data.get('id')}")

        try:
            mark_post_as_published(post_id)
            print(f"Post {post_id} marked as 'posted'.")
        except Exception as e:
            print(f"Failed to update post status for {post_id}: {e}")
            
        try:    
            log_publish_attempt(post_id, True, "Published successfully")
        except Exception as e:
            print(f"Failed to log success for {post_id}: {e}")



if __name__ == "__main__":
    from dotenv import load_dotenv  # type: ignore
    load_dotenv(".env.local")

    async def main():
        print("Initializing Scheduler Agent (Terminal Mode)...")
        agent = SchedulerAgent(kernel=None)
        await agent.run()
        print("Agent run complete!")

    asyncio.run(main())