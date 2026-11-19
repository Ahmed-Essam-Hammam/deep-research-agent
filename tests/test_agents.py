from unittest.mock import MagicMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.graph import END
from pydantic import ValidationError

from src.models.agents_states.state_scope import ClarifyWithUser, ResearchQuestion
from src.pipes.search_result_pipes import SearchResultPipe
from src.services.agents.nodes.multi_agent import MultiAgent
from src.services.agents.nodes.research_agent import ResearchAgent
from src.services.agents.nodes.scope_agent import ScopeAgent
from src.services.agents.tools.tools import think_tool

# ===== Structured-output schemas =====


def test_clarify_with_user_requires_all_three_fields():
    with pytest.raises(ValidationError):
        ClarifyWithUser(need_clarification=True)


# ===== ScopeAgent =====


def _scope_agent(structured_response):
    structured_model = MagicMock()
    structured_model.invoke.return_value = structured_response
    model = MagicMock()
    model.with_structured_output.return_value = structured_model

    pipe = MagicMock(spec=SearchResultPipe)
    pipe.get_today_str.return_value = "Mon Jan 01, 2026"

    agent = ScopeAgent(
        model=model,
        clarify_with_user_instructions="Messages: {messages}\nDate: {date}",
        transform_messages_into_research_topic_prompt="Messages: {messages}\nDate: {date}",
        search_result_pipe=pipe,
    )
    return agent, model


def test_clarify_with_user_ends_the_graph_when_clarification_is_needed():
    response = ClarifyWithUser(
        need_clarification=True, question="Which country?", verification=""
    )
    agent, _ = _scope_agent(response)
    state = {"messages": [HumanMessage(content="Tell me about the economy")]}

    command = agent.clarify_with_user(state)

    assert command.goto == END
    assert command.update["messages"][0].content == "Which country?"


def test_clarify_with_user_routes_to_research_brief_when_context_is_sufficient():
    response = ClarifyWithUser(
        need_clarification=False, question="", verification="Starting research."
    )
    agent, _ = _scope_agent(response)
    state = {"messages": [HumanMessage(content="Research the French economy in 2024")]}

    command = agent.clarify_with_user(state)

    assert command.goto == "write_research_brief"
    assert command.update["messages"][0].content == "Starting research."


def test_write_research_brief_returns_brief_and_seeds_supervisor_messages():
    response = ResearchQuestion(
        research_brief="Investigate the French economy in 2024."
    )
    agent, _ = _scope_agent(response)
    state = {"messages": [HumanMessage(content="Research the French economy in 2024")]}

    result = agent.write_research_brief(state)

    assert result["research_brief"] == "Investigate the French economy in 2024."
    assert (
        "Investigate the French economy in 2024."
        in result["supervisor_messages"][0].content
    )


# ===== ResearchAgent =====


def _research_agent(model_with_tools=None, tools_by_name=None, compress_model=None):
    pipe = MagicMock(spec=SearchResultPipe)
    pipe.get_today_str.return_value = "Mon Jan 01, 2026"
    return ResearchAgent(
        model_with_tools=model_with_tools or MagicMock(),
        tools_by_name=tools_by_name or {},
        compress_model=compress_model or MagicMock(),
        research_agent_prompt="Research prompt",
        compress_research_system_prompt="Compress prompt {date}",
        compress_research_human_message="Summarize now.",
        search_result_pipe=pipe,
    )


def test_llm_call_invokes_the_model_with_system_prompt_and_history():
    model_with_tools = MagicMock()
    model_with_tools.invoke.return_value = AIMessage(content="thinking...")
    agent = _research_agent(model_with_tools=model_with_tools)
    state = {"researcher_messages": [HumanMessage(content="What's the weather?")]}

    result = agent.llm_call(state)

    assert result["researcher_messages"] == [AIMessage(content="thinking...")]
    invoked_messages = model_with_tools.invoke.call_args.args[0]
    assert invoked_messages[0].content == "Research prompt"


def test_tool_node_executes_every_requested_tool_call():
    fake_tool = MagicMock()
    fake_tool.invoke.return_value = "42 degrees"
    agent = _research_agent(tools_by_name={"get_weather": fake_tool})

    ai_message = AIMessage(
        content="",
        tool_calls=[{"name": "get_weather", "args": {"city": "Cairo"}, "id": "call_1"}],
    )
    state = {"researcher_messages": [ai_message]}

    result = agent.tool_node(state)

    fake_tool.invoke.assert_called_once_with({"city": "Cairo"})
    assert result["researcher_messages"][0].content == "42 degrees"
    assert result["researcher_messages"][0].tool_call_id == "call_1"


def test_should_continue_routes_to_tool_node_when_tool_calls_are_present():
    agent = _research_agent()
    state = {
        "researcher_messages": [
            AIMessage(content="", tool_calls=[{"name": "x", "args": {}, "id": "1"}])
        ]
    }
    assert agent.should_continue(state) == "tool_node"


def test_should_continue_routes_to_compress_research_when_no_tool_calls():
    agent = _research_agent()
    state = {"researcher_messages": [AIMessage(content="Here is my final answer.")]}
    assert agent.should_continue(state) == "compress_research"


def test_compress_research_extracts_notes_from_tool_and_ai_messages():
    compress_model = MagicMock()
    compress_model.invoke.return_value = AIMessage(content="Compressed findings.")
    agent = _research_agent(compress_model=compress_model)

    state = {
        "researcher_messages": [
            HumanMessage(content="Research the weather"),
            ToolMessage(content="It is sunny", name="get_weather", tool_call_id="1"),
            AIMessage(content="The weather is sunny."),
        ]
    }

    result = agent.compress_research(state)

    assert result["compressed_research"] == "Compressed findings."
    assert "It is sunny" in result["raw_notes"][0]
    assert "The weather is sunny." in result["raw_notes"][0]
    # HumanMessage isn't "tool" or "ai" - it should be excluded from raw_notes.
    assert "Research the weather" not in result["raw_notes"][0]


# ===== MultiAgent =====


def test_get_notes_from_tool_calls_extracts_only_tool_message_content():
    agent = MultiAgent(
        max_concurrent_researchers=3,
        max_researcher_iterations=6,
        supervisor_model_with_tools=MagicMock(),
        researcher_agent=MagicMock(),
        search_result_pipe=MagicMock(spec=SearchResultPipe),
        lead_researcher_prompt="prompt",
    )

    messages = [
        HumanMessage(content="Research X and Y"),
        AIMessage(content="Delegating..."),
        ToolMessage(
            content="Findings about X", name="ConductResearch", tool_call_id="1"
        ),
        ToolMessage(
            content="Findings about Y", name="ConductResearch", tool_call_id="2"
        ),
    ]

    notes = agent.get_notes_from_tool_calls(messages)

    assert notes == ["Findings about X", "Findings about Y"]


# ===== Tools =====


def test_think_tool_echoes_the_reflection_back():
    result = think_tool.invoke({"reflection": "Found three relevant sources so far."})
    assert result == "Reflection recorded: Found three relevant sources so far."


def test_tavily_search_tool_delegates_to_search_and_formatting_helpers(monkeypatch):
    from src.services.agents.tools import tools as tools_module

    fake_search_obj = MagicMock()
    fake_search_obj.tavily_search_multiple.return_value = [
        {"results": [{"url": "https://a.com"}]}
    ]
    fake_pipe_obj = MagicMock()
    fake_pipe_obj.deduplicate_search_results.return_value = {
        "https://a.com": {"title": "A", "content": "c"}
    }
    fake_pipe_obj.process_search_results.return_value = {
        "https://a.com": {"title": "A", "content": "summary"}
    }
    fake_pipe_obj.format_search_output.return_value = "FORMATTED OUTPUT"

    monkeypatch.setattr(tools_module, "search_obj", fake_search_obj)
    monkeypatch.setattr(tools_module, "pipe_obj", fake_pipe_obj)

    result = tools_module.tavily_search.invoke(
        {"query": "python testing best practices"}
    )

    assert result == "FORMATTED OUTPUT"
    fake_search_obj.tavily_search_multiple.assert_called_once()
    called_queries = fake_search_obj.tavily_search_multiple.call_args.args[0]
    assert called_queries == ["python testing best practices"]
