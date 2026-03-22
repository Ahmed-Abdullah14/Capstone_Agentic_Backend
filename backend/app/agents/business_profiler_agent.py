import json
from openai import AsyncOpenAI
from app.agents.base_agent import Agent
from app.schemas.business_context import BusinessContext
from app.schemas.agent_results import BusinessProfilerResult
from app.config import OPENROUTER_API_KEY, OPENROUTER_BASE_URL, PROFILER_MODEL


class BusinessProfilerAgent(Agent):
    def __init__(self, kernel):
        super().__init__(kernel=kernel, name="business_profiler_agent")
        self._client = AsyncOpenAI(
            api_key=OPENROUTER_API_KEY,
            base_url=OPENROUTER_BASE_URL,
        )

    async def run(self, context: BusinessContext) -> BusinessProfilerResult:

        system_prompt = (
            "You are an Instagram growth strategist for local businesses.\n"
            "Given a business profile, generate hashtags and search parameters to find local competitors on Instagram.\n\n"
            "Return ONLY valid JSON with this exact structure:\n"
            "{\n"
            '  "primary_hashtags": ["list of 4-6 hyper-local/niche hashtags specific to the city and business type"],\n'
            '  "secondary_hashtags": ["list of 4-6 broader industry hashtags that are not location-specific"],\n'
            '  "location_keywords": ["list of 2-4 location-based search terms"],\n'
            '  "exclude_accounts": ["list of 2-4 large chain/franchise accounts to filter out"],\n'
            '  "ideal_follower_min": 500,\n'
            '  "ideal_follower_max": 30000\n'
            "}\n\n"
            "Guidelines:\n"
            "- Primary hashtags should combine the city/area with the business type (e.g. yyccoffee, calgarycafes)\n"
            "- Secondary hashtags should be broader industry terms (e.g. latteart, specialtycoffee)\n"
            "- Exclude accounts should be large national/international chains that would skew competitor analysis\n"
            "- Follower range should target local businesses, not large brands (min: 500, max: 30000)\n"
            "- Location keywords should help identify businesses in the same area\n"
            "- Return ONLY the JSON object, no markdown, no explanation"
        )

        user_prompt = (
            f"Business Name: {context.business_name}\n"
            f"Business Type: {context.business_type}\n"
            f"Location: {context.location}\n"
            f"Target Customers: {context.target_customers}\n"
            f"Instagram Handle: {context.instagram_handle or 'N/A'}"
        )

        response = await self._client.chat.completions.create(
            model=PROFILER_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.0,
        )

        raw = response.choices[0].message.content.strip()

        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1]
            raw = raw.rsplit("```", 1)[0]

        data = json.loads(raw)

        return BusinessProfilerResult(
            business_id=context.business_id,
            primary_hashtags=data["primary_hashtags"],
            secondary_hashtags=data["secondary_hashtags"],
            location_keywords=data["location_keywords"],
            exclude_accounts=data["exclude_accounts"],
            ideal_follower_min=data.get("ideal_follower_min", 500),
            ideal_follower_max=data.get("ideal_follower_max", 30000),
        )
