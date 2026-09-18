"""Research Agent Implementation.

This module implements a research agent that can perform iterative web searches
and synthesis to answer complex research questions.
"""

from pydantic import BaseModel, Field
from typing_extensions import Literal

from langgraph.graph import StateGraph, START, END


from src.dependencies.injection import get_app_settings
from src.services.agents.tools.tools import tavily_search, think_tool
from src.providers.llm import get_llm_provider
from src.pipes.search_result_pipes import SearchResultPipe
from src.models.agents_states.state_research import ResearcherState, ResearcherOutputState
from src.services.agents.nodes.research_agent import ResearchAgent
from src.prompts.prompts import (research_agent_prompt,
                             compress_research_system_prompt,
                             compress_research_human_message,
                             summarize_webpage_prompt)



settings = get_app_settings()


# Set up tools and model binding
tools = [tavily_search, think_tool]
tools_by_name = {tool.name: tool for tool in tools}

llm_provider = get_llm_provider(settings.default_llm_provider)


model = llm_provider.get_chat_model(
    model=settings.default_llm_model,
    temperature=0.0,
    max_tokens=1000,
)
model_with_tools = model.bind_tools(tools)


summarization_model = llm_provider.get_chat_model(
    model=settings.default_llm_model,
    temperature=0.0,
    max_tokens=1000,
)

compress_model = llm_provider.get_chat_model(
    model=settings.default_llm_model,
    temperature=0.0,
    max_tokens=1000,
)





search_result_pipe_obj = SearchResultPipe(llm_provider=llm_provider,
                                     summarize_webpage_prompt=summarize_webpage_prompt)




research_agent_obj = ResearchAgent(model_with_tools=model_with_tools,
                                   tools_by_name=tools_by_name,
                                   compress_model=compress_model,
                                   research_agent_prompt=research_agent_prompt,
                                   compress_research_system_prompt=compress_research_system_prompt,
                                   compress_research_human_message=compress_research_human_message,
                                   search_result_pipe=search_result_pipe_obj)




# ===== GRAPH CONSTRUCTION =====

# Build the agent workflow
agent_builder = StateGraph(ResearcherState, output_schema=ResearcherOutputState)

# Add nodes to the graph
agent_builder.add_node("llm_call", research_agent_obj.llm_call)
agent_builder.add_node("tool_node", research_agent_obj.tool_node)
agent_builder.add_node("compress_research", research_agent_obj.compress_research)

# Add edges to connect nodes
agent_builder.add_edge(START, "llm_call")
agent_builder.add_conditional_edges(
    "llm_call",
    research_agent_obj.should_continue,
    {
        "tool_node": "tool_node", # Continue research loop
        "compress_research": "compress_research", # Provide final answer
    },
)
agent_builder.add_edge("tool_node", "llm_call") # Loop back for more research
agent_builder.add_edge("compress_research", END)

# Compile the agent
researcher_agent = agent_builder.compile()