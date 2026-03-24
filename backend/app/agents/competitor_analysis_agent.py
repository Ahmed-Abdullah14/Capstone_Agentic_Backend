import asyncio
import os
from typing import Any

import requests
from app.agents.base_agent import Agent
from app.schemas.agent_results import CompetitorAnalysisResult
from app.schemas.business_context import BusinessContext

class CompetitorAnalysisAgent(Agent):
    def __init__(self, kernel):
        super().__init__(kernel=kernel, name="competitor_analysis_agent")

    async def run(self,context: BusinessContext,primary_hashtags: list[str],secondary_hashtags: list[str],location_keywords: list[str],exclude_accounts: list[str],business_niche: str | None = None,ideal_follower_min: int = 500,ideal_follower_max: int = 30000,) -> CompetitorAnalysisResult:

        payload = {
            "business_id": context.business_id,
            "business_niche": business_niche or context.business_type,
            "location": context.location,
            "location_keywords": location_keywords,
            "primary_hashtags": primary_hashtags,
            "secondary_hashtags": secondary_hashtags,
            "exclude_accounts": exclude_accounts,
            "ideal_competitor_follower_range": {
                "min": ideal_follower_min,
                "max": ideal_follower_max,
            },
        }

        def _post_webhook() -> Any:
            response = requests.post("https://flow.lumeniq.cloud/webhook-test/811e1327-00c3-48e7-ba04-dcabeabe25a7", json=payload, timeout=120)
            response.raise_for_status()
            return response.json()


        def _to_bool(value: Any) -> bool:
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                return value.strip().lower() == "true"
            return bool(value)

        try:
            raw_response = await asyncio.to_thread(_post_webhook)
            result = raw_response

            # Return results from n8n workflow to Manager Agent
            return CompetitorAnalysisResult(
                business_id=context.business_id,
                success=_to_bool(result.get("success", False)),
                competitor_count=int(result.get("competitor_count", 0)),
                post_count=int(result.get("total_posts", result.get("post_count", 0))),
                message=str(result.get("message", "Competitor analysis completed.")),
            )
        except Exception as e:
            return CompetitorAnalysisResult(
                business_id=context.business_id,
                success=False,
                competitor_count=0,
                post_count=0,
                message=f"Competitor analysis failed: {e}",
            )


if __name__ == "__main__":
    from semantic_kernel import Kernel

    async def main():

        agent = CompetitorAnalysisAgent(Kernel())
        context = BusinessContext(
            user_id="mock-user",
            business_id="54eb934a-83b3-4ca4-9caf-8b3575e5d3ff",
            business_type="local specialty coffee shop",
            location="Toronto, Ontario",
        )

        result = await agent.run(
            context=context,
            primary_hashtags=["torontocoffee", "torontocafes", "torontobrunch"],
            secondary_hashtags=["latteart", "specialtycoffee"],
            location_keywords=["Toronto", "yyz", "Ontario"],
            exclude_accounts=["starbucks", "timhortons", "mcdonaldscanada"],
            business_niche="local specialty coffee shop",
            ideal_follower_min=500,
            ideal_follower_max=30000,
        )

        print(result.model_dump())

    asyncio.run(main())