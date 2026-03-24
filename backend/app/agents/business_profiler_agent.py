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

        # validation
        if not all([context.business_name, context.business_type, context.location, context.target_customers]):
            raise ValueError("Business context is missing required fields (business_name, business_type, location, target_customers)")

        system_prompt = (
            "You are an Instagram growth strategist for local businesses.\n"
            "Given a business profile, generate hashtags and search parameters to find local competitors on Instagram.\n\n"
            "If the business provides an Instagram handle, search their Instagram profile to understand their current brand voice, "
            "visual style, posting patterns, and the type of content they share. Use this to tailor your recommendations.\n\n"
            "If the business provides a website URL, search their website to understand their brand tone, business colors, "
            "services/products offered, and overall brand identity. Use this to make your hashtag and keyword recommendations "
            "more aligned with their actual brand.\n\n"
            "Return ONLY valid JSON with this exact structure:\n"
            "{\n"
            '  "primary_hashtags": ["list of 3 hyper-local/niche hashtags specific to the city and business type"],\n'
            '  "secondary_hashtags": ["list of 2 broader industry hashtags that are not location-specific"],\n'
            '  "location_keywords": ["list of 2-4 location-based search terms"],\n'
            '  "exclude_accounts": ["list of 2-4 large chain/franchise accounts to filter out"],\n'
            '  "ideal_follower_min": 500,\n'
            '  "ideal_follower_max": 30000,\n'
            '  "brand_voice": "short description of the brand tone/voice based on their Instagram and website (e.g. casual and friendly, professional and polished)",\n'
            '  "brand_colors": ["list of brand colors or color themes observed from their website/Instagram"],\n'
            '  "content_style": "short description of the visual content style observed (e.g. lifestyle photography, flat lays, behind-the-scenes)"\n'
            "}\n\n"
            "Guidelines:\n"
            "- Primary hashtags should combine the city/area with the business type (e.g. yyccoffee, calgarycafes)\n"
            "- Secondary hashtags should be broader industry terms (e.g. latteart, specialtycoffee)\n"
            "- If an Instagram handle is provided, look at their profile to understand what content resonates with their audience "
            "and suggest hashtags that align with their existing brand voice and content style\n"
            "- If a website is provided, analyze the brand tone, colors, and offerings to recommend hashtags that match their identity\n"
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
            f"Instagram Handle: {context.instagram_handle or 'Not provided'}\n"
            f"Website: {context.website or 'Not provided'}"
        )

        # Call LLM to generate hashtags and search parameters
        try:
            response = await self._client.chat.completions.create(
                model=PROFILER_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.0,
            )
        except Exception as e:
            raise RuntimeError(f"Business Profiler LLM call failed: {e}")

        raw = response.choices[0].message.content
        if not raw:
            raise RuntimeError("Business Profiler received empty response from LLM")

        raw = raw.strip()

        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1]
            raw = raw.rsplit("```", 1)[0]

        # Parse JSON response
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Business Profiler failed to parse LLM response as JSON: {e}\nRaw response: {raw}")

        # Validate required fields in LLM response
        required_fields = ["primary_hashtags", "secondary_hashtags", "location_keywords", "exclude_accounts"]
        missing = [f for f in required_fields if f not in data]
        if missing:
            raise RuntimeError(f"Business Profiler LLM response missing required fields: {missing}")

        return BusinessProfilerResult(
            business_id=context.business_id,
            primary_hashtags=data["primary_hashtags"],
            secondary_hashtags=data["secondary_hashtags"],
            location_keywords=data["location_keywords"],
            exclude_accounts=data["exclude_accounts"],
            ideal_follower_min=data.get("ideal_follower_min", 500),
            ideal_follower_max=data.get("ideal_follower_max", 30000),
            brand_voice=data.get("brand_voice"),
            brand_colors=data.get("brand_colors"),
            content_style=data.get("content_style"),
        )
