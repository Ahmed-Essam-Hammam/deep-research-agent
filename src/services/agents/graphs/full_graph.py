"""Full Multi-Agent Research System

This module integrates all components of the research system:
- User clarification and scoping
- Research brief generation
- Multi-agent research coordination
- Final report generation

The system orchestrates the complete research workflow from initial user
input through final report delivery.
"""

from langgraph.graph import END, START, StateGraph

from src.dependencies.injection import get_app_settings
from src.models.agents_states.state_scope import AgentInputState, AgentState
from src.prompts.prompts import (
    clarify_with_user_instructions,
    final_report_generation_prompt,
    transform_messages_into_research_topic_prompt,
)
from src.services.agents.graphs.researcher_graph import (
    llm_provider,
    model,
    search_result_pipe_obj,
)
from src.services.agents.graphs.supervisor_graph import supervisor_agent
from src.services.agents.nodes.scope_agent import ScopeAgent

settings = get_app_settings()

writer_model = llm_provider.get_chat_model(
    model=settings.default_llm_model,
    temperature=0.0,
    max_tokens=2000,
)


async def final_report_generation_node(state: AgentState):
    return await search_result_pipe_obj.final_report_generation(
        writer_model=writer_model,
        final_report_generation_prompt=final_report_generation_prompt,
        state=state,
    )


scope_agent_obj = ScopeAgent(
    model=model,
    clarify_with_user_instructions=clarify_with_user_instructions,
    transform_messages_into_research_topic_prompt=transform_messages_into_research_topic_prompt,
    search_result_pipe=search_result_pipe_obj,
)


# ===== GRAPH CONSTRUCTION =====
# Build the overall workflow
deep_researcher_builder = StateGraph(AgentState, input_schema=AgentInputState)

# Add workflow nodes
deep_researcher_builder.add_node("clarify_with_user", scope_agent_obj.clarify_with_user)
deep_researcher_builder.add_node(
    "write_research_brief", scope_agent_obj.write_research_brief
)
deep_researcher_builder.add_node("supervisor_subgraph", supervisor_agent)
deep_researcher_builder.add_node(
    "final_report_generation", final_report_generation_node
)

# Add workflow edges
deep_researcher_builder.add_edge(START, "clarify_with_user")
deep_researcher_builder.add_edge("write_research_brief", "supervisor_subgraph")
deep_researcher_builder.add_edge("supervisor_subgraph", "final_report_generation")
deep_researcher_builder.add_edge("final_report_generation", END)

# Compile the full workflow
agent = deep_researcher_builder.compile()
