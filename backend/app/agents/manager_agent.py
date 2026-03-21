import chainlit as cl
from semantic_kernel import Kernel
from semantic_kernel.agents import ChatCompletionAgent, ChatHistoryAgentThread
from semantic_kernel.connectors.ai.chat_completion_client_base import ChatCompletionClientBase
from semantic_kernel.connectors.ai.open_ai import OpenAIChatPromptExecutionSettings
from app.agents.base_agent import Agent
from app.agents.business_profiler_agent import BusinessProfilerAgent
from app.agents.competitor_analysis_agent import CompetitorAnalysisAgent
from app.agents.trend_analysis_agent import TrendAnalysisAgent
from app.agents.content_generator_agent import ContentGeneratorAgent
from app.agents.scheduler_agent import SchedulerAgent
from app.schemas.business_context import BusinessContext
from app.schemas.manager_decision import ManagerDecision
from app.schemas.user_request import UserRequest
from app.orchestrator.intent_classifier import IntentClassifier
from app.orchestrator.router import Router
from app.orchestrator.route_types import RouteType, IntentType
from app.db.business_profiler_queries import BusinessProfilerQueries
from pathlib import Path

# Retreiving Manager instructions from app/prompts/manager.txt
with open("app/prompts/manager.txt", "r") as f:
    MANAGER_INSTRUCTIONS = f.read()


class ManagerAgent(Agent):
    def __init__(self, kernel):
        super().__init__(kernel=kernel, name="manager_agent")

        # Instantitating all agents
        self.business_profiler_agent = BusinessProfilerAgent(kernel)
        self.competitor_analysis_agent = CompetitorAnalysisAgent(kernel)
        self.trend_analysis_agent = TrendAnalysisAgent(kernel)
        self.content_generator_agent = ContentGeneratorAgent(kernel)
        self.scheduler_agent = SchedulerAgent(kernel)

        # Instantiating routes and intents
        self.intent_classifier = IntentClassifier()
        self.router = Router()
        self.business_profiler_queries = BusinessProfilerQueries()

        # Instantiating Manager
        self.agent = ChatCompletionAgent(
            service = kernel.get_service(type=ChatCompletionClientBase),
            name = "Manager_Agent",
            instructions = MANAGER_INSTRUCTIONS
        )

    async def run(self, user_request, business_context, thread, pending_route=None):

        # Try to figure out user intent, this function is wrapped in a chainlit step to show thought process on chainlit
        async with cl.Step(name = "Understanding your request...", type="step") as step:
            intent = await self.intent_classifier.classify(user_request.user_prompt)
            step.output = f"Intent detected: {intent}"

        # After identifying intent match intent with correct route, this function is wrapped in a chainlit step to show thought process on chainlit
        async with cl.Step(name = "Planning Route...", type="step") as step:
            route, target_agent, reason, pipeline_end_at = self.router.determine_route(intent, business_context)
            step.output = f"Route determined: {route} \nReason: {reason}"

        # Debugging
        print(f"\n\n=== LLM MESSAGE ===\n{user_request.user_prompt}\n")

        # Adding system message to memory thread with pipeline state
        thread._chat_history.add_system_message(
            f"Current pipeline state:\n"
            f"- has_hashtags: {business_context.has_hashtags}\n"
            f"- has_top_posts: {business_context.has_top_posts}\n"
            f"- has_trend_summary: {business_context.has_trend_summary}\n"
            f"- has_content_plan: {business_context.has_content_plan}\n"
            f"- pending_route: {pending_route or 'None'}\n"
        )
        
        # Adding user message to memory thread
        thread._chat_history.add_user_message(user_request.user_prompt)

        # Calling the Manager Agent LLM
        response = await self.agent.get_response(
            message = user_request.user_prompt,
            thread = thread,
            settings = OpenAIChatPromptExecutionSettings()  # Replace with OpenAIChatPromptExecutionSettings(function_choice_behavior=FunctionChoiceBehavior.Auto()) when manager tools implemented
        ) 

        # Debugging
        print(f"\n\n=== LLM RESPONSE ===\n{response.content}\n")

        fallback_msg = "I am not sure how to help you with that, could you please provide some more information?"

        return ManagerDecision(
            intent=intent,
            route=route,
            target_agent=target_agent,
            reason=reason,
            pipeline_end_at=pipeline_end_at,
            manager_response=str(response.content) if response.content else fallback_msg
        )
    
    async def execute_route(self, route, pipeline_end_at, context):
        if route == RouteType.FULL_PIPELINE:
            profiler_agent_result = await self.business_profiler_agent.run(context = context)
            competitor_analysis_agent_result = await self.competitor_analysis_agent.run(
                context = context,
                primary_hashtags = profiler_agent_result.primary_hashtags,
                secondary_hashtags = profiler_agent_result.secondary_hashtags,
                location_keywords = profiler_agent_result.location_keywords,
                exclude_accounts=profiler_agent_result.exclude_accounts
            )
            trend_analysis_agent_results = await self.trend_analysis_agent.run(context = context)
            if pipeline_end_at == "analyze_photo":
                await self.content_generator_agent.run(context = context, trend_summary = trend_analysis_agent_results.summary, analyze_photo = True)
            elif pipeline_end_at == "generate_image":
                await self.content_generator_agent.run(context = context, trend_summary = trend_analysis_agent_results.summary, generate_image = True)
            else:
                await self.content_generator_agent.run(context = context, trend_summary = trend_analysis_agent_results.summary)

        elif route == RouteType.SKIP_TO_COMPETITOR_ANALYSIS:
            hashtags = await self.business_profiler_queries.get_hashtags(context.business_id)
            competitor_analysis_agent_result = await self.competitor_analysis_agent.run(
                context = context,
                primary_hashtags = profiler_agent_result.primary_hashtags,
                secondary_hashtags = profiler_agent_result.secondary_hashtags,
                location_keywords = profiler_agent_result.location_keywords,
                exclude_accounts=profiler_agent_result.exclude_accounts
            )
            trend_analysis_agent_results = await self.trend_analysis_agent.run(context = context)
            if pipeline_end_at == "analyze_photo":
                await self.content_generator_agent.run(context = context, trend_summary = trend_analysis_agent_results.summary, analyze_photo = True)
            elif pipeline_end_at == "generate_image":
                await self.content_generator_agent.run(context = context, trend_summary = trend_analysis_agent_results.summary, generate_image = True)
            else:
                await self.content_generator_agent.run(context = context, trend_summary = trend_analysis_agent_results.summary)
        
        elif route == RouteType.SKIP_TO_TREND_ANALYSIS:
            trend_analysis_agent_results = await self.trend_analysis_agent.run(context = context)
            if pipeline_end_at == "analyze_photo":
                await self.content_generator_agent.run(context = context, trend_summary = trend_analysis_agent_results.summary, analyze_photo = True)
            elif pipeline_end_at == "generate_image":
                await self.content_generator_agent.run(context = context, trend_summary = trend_analysis_agent_results.summary, generate_image = True)
            else:
                await self.content_generator_agent.run(context = context, trend_summary = trend_analysis_agent_results.summary)
        
        elif route == RouteType.SKIP_TO_CONTENT_GENERATOR:
            trend_summary = await self.business_profiler_queries.get_trend_summary(context.business_id)
            await self.content_generator_agent.run(context=context, trend_summary=trend_summary)

        elif route == RouteType.PROFILER_AND_COMPETITOR_ONLY:
            profiler_agent_result = await self.business_profiler_agent.run(context = context)
            competitor_analysis_agent_result = await self.competitor_analysis_agent.run(
                context = context,
                primary_hashtags = profiler_agent_result.primary_hashtags,
                secondary_hashtags = profiler_agent_result.secondary_hashtags,
                location_keywords = profiler_agent_result.location_keywords,
                exclude_accounts=profiler_agent_result.exclude_accounts
            )





    

