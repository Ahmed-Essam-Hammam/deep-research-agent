from langgraph.graph import START, StateGraph

from src.dependencies.injection import get_app_settings
from src.models.agents_states.state_multi_agent_supervisor import (
    ConductResearch,
    ResearchComplete,
    SupervisorState,
)
from src.prompts.prompts import lead_researcher_prompt
from src.services.agents.graphs.researcher_graph import (
    llm_provider,
    researcher_agent,
    search_result_pipe_obj,
)
from src.services.agents.nodes.multi_agent import MultiAgent
from src.services.agents.tools.tools import think_tool

settings = get_app_settings()

max_concurrent_researchers = settings.max_concurrent_researchers
max_researcher_iterations = settings.max_researcher_iterations
supervisor_tools = [think_tool, ConductResearch, ResearchComplete]

supervisor_model = llm_provider.get_chat_model(
    model=settings.default_llm_model,
    temperature=0.0,
    max_tokens=1000,
)
supervisor_model_with_tools = supervisor_model.bind_tools(supervisor_tools)


multi_agent_obj = MultiAgent(
    max_concurrent_researchers=max_concurrent_researchers,
    max_researcher_iterations=max_researcher_iterations,
    supervisor_model_with_tools=supervisor_model_with_tools,
    researcher_agent=researcher_agent,
    search_result_pipe=search_result_pipe_obj,
    lead_researcher_prompt=lead_researcher_prompt,
)


# ===== GRAPH CONSTRUCTION =====

# Build supervisor graph
supervisor_builder = StateGraph(SupervisorState)
supervisor_builder.add_node("supervisor", multi_agent_obj.supervisor)
supervisor_builder.add_node("supervisor_tools", multi_agent_obj.supervisor_tools)
supervisor_builder.add_edge(START, "supervisor")
supervisor_agent = supervisor_builder.compile()
