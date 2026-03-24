import asyncio
from semantic_kernel import Kernel
from app.agents.business_profiler_agent import BusinessProfilerAgent
from app.schemas.business_context import BusinessContext


async def main():
    kernel = Kernel()
    agent = BusinessProfilerAgent(kernel=kernel)

    print("Enter business details to profile:\n")
    business_name = input("Business Name: ").strip()
    business_type = input("Business Type: ").strip()
    location = input("Location (city, province/state, country): ").strip()
    target_customers = input("Target Customers: ").strip()
    instagram_handle = input("Instagram Handle (optional): ").strip() or None

    context = BusinessContext(
        user_id="test-user-001",
        business_id="test-biz-001",
        business_name=business_name,
        business_type=business_type,
        location=location,
        target_customers=target_customers,
        instagram_handle=instagram_handle,
    )

    print("Running Business Profiler Agent...")
    print(f"  Business: {context.business_name}")
    print(f"  Location: {context.location}")
    print()

    result = await agent.run(context=context)

    print("=== Results ===")
    print(f"Primary Hashtags:   {result.primary_hashtags}")
    print(f"Secondary Hashtags: {result.secondary_hashtags}")
    print(f"Location Keywords:  {result.location_keywords}")
    print(f"Exclude Accounts:   {result.exclude_accounts}")
    print(f"Follower Range:     {result.ideal_follower_min} – {result.ideal_follower_max}")


if __name__ == "__main__":
    asyncio.run(main())
