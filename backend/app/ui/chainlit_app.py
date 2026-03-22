import chainlit as cl
from app.config import APP_NAME
from semantic_kernel.contents import ChatHistory
from semantic_kernel.agents import ChatHistoryAgentThread
from app.kernel_config import kernel_init
from app.agents.manager_agent import ManagerAgent
from app.schemas.business_context import BusinessContext
from app.schemas.user_request import UserRequest
from app.db.business_profiler_queries import BusinessProfilerQueries
from app.orchestrator.route_types import RouteType, IntentType



kernel = kernel_init()
manager = ManagerAgent(kernel)
business_profiler_queries = BusinessProfilerQueries()

IMMEDIATE_ROUTES = [
    RouteType.FETCH_EXISTING_COMPETITORS,
    RouteType.ANALYZE_PHOTO,
    RouteType.GENERATE_POST_IMAGE,
]

@cl.on_chat_start
async def on_chat_start():
    
    thread = ChatHistoryAgentThread(chat_history=ChatHistory())
    cl.user_session.set("thread", thread)

    user_id = "user_123"
    business_id = "business_123"

    cl.user_session.set("user_id", user_id)
    cl.user_session.set("business_id", business_id)
    cl.user_session.set("pending_route", None)
    cl.user_session.set("pending_pipeline_end_at", None)
    
    context = business_profiler_queries.get_business_context(user_id, business_id)
    cl.user_session.set("context", context)

    await cl.Message(content = (
        f"Welcome to {APP_NAME}.\n\n"
        "I'm your AI assistant. I can help you create engaging social media content, schedule posts, analyze trends, and manage your social media strategy.\n\n"
        "Your business profile has been set up. Whenever you're ready, let me know would you like to work on today?"
    )).send()
    
@cl.on_message
async def on_message(message: cl.Message):
    thread = cl.user_session.get("thread")
    user_id = cl.user_session.get("user_id")
    business_id = cl.user_session.get("business_id")
    context = cl.user_session.get("context")
    pending_route = cl.user_session.get("pending_route")
    pending_pipeline_end_at = cl.user_session.get("pending_pipeline_end_at")

    user_input = message.content

    if context is None:
        context = business_profiler_queries.get_business_context(user_id, business_id)
        cl.user_session.set("context", context)

    request = UserRequest(
        user_id=user_id,
        business_id=business_id,
        user_prompt=user_input
    )

    try:
        manager_decision = await manager.run(
            user_request=request,
            business_context=context,
            thread=thread,
            pending_route=pending_route
        )

        
        if manager_decision.route not in [RouteType.UNKNOWN] and manager_decision.intent not in [IntentType.CONFIRM, IntentType.CANCEL]:
            cl.user_session.set("pending_route", manager_decision.route)
            cl.user_session.set("pending_pipeline_end_at", manager_decision.pipeline_end_at)


        async with cl.Step(name="Current Session State:", type="step") as step:
            step.output = (
                f"Pending route: {cl.user_session.get('pending_route') or 'None'}\n"
                f"Pending pipeline end at: {cl.user_session.get('pending_pipeline_end_at') or 'None'}"
            )

        await cl.Message(content = manager_decision.manager_response).send()


        if manager_decision.route in IMMEDIATE_ROUTES:
            async with cl.Step(name="Running pipeline...", type="run") as step:
                await manager.execute_route(
                    route=manager_decision.route,
                    pipeline_end_at=manager_decision.pipeline_end_at,
                    context=context
                )
                step.output = "Complete"
            cl.user_session.set("pending_route", None)
            cl.user_session.set("pending_pipeline_end_at", None)


        elif manager_decision.intent == IntentType.CONFIRM and pending_route:
            async with cl.Step(name="Running pipeline...", type="run") as step:
                await manager.execute_route(
                    route=pending_route,
                    pipeline_end_at=pending_pipeline_end_at,
                    context=context
                )
                step.output = "Complete"
            cl.user_session.set("pending_route", None)
            cl.user_session.set("pending_pipeline_end_at", None)

        elif manager_decision.intent == IntentType.CANCEL:
            cl.user_session.set("pending_route", None)
            cl.user_session.set("pending_pipeline_end_at", None)
            
        context = business_profiler_queries.get_business_context(user_id, business_id)
        cl.user_session.set("context", context)

    except Exception as e:
        await cl.Message(content = "Something went wrong").send()
        raise e