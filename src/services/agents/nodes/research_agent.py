from langchain_core.messages import (
    HumanMessage,
    SystemMessage,
    ToolMessage,
    filter_messages,
)
from typing_extensions import Literal

from src.models.agents_states.state_research import ResearcherState
from src.pipes.search_result_pipes import SearchResultPipe


class ResearchAgent:
    def __init__(
        self,
        model_with_tools,
        tools_by_name,
        compress_model,
        research_agent_prompt: str,
        compress_research_system_prompt: str,
        compress_research_human_message: str,
        search_result_pipe: SearchResultPipe,
    ):

        self.model_with_tools = model_with_tools
        self.tools_by_name = tools_by_name
        self.compress_model = compress_model
        self.research_agent_prompt = research_agent_prompt
        self.compress_research_system_prompt = compress_research_system_prompt
        self.compress_research_human_message = compress_research_human_message
        self.search_result_pipe = search_result_pipe

    def llm_call(self, state: ResearcherState):
        """Analyze current state and decide on next actions.

        The model analyzes the current conversation state and decides whether to:
        1. Call search tools to gather more information
        2. Provide a final answer based on gathered information

        Returns updated state with the model's response.
        """
        return {
            "researcher_messages": [
                self.model_with_tools.invoke(
                    [SystemMessage(content=self.research_agent_prompt)]
                    + state["researcher_messages"]
                )
            ]
        }

    def tool_node(self, state: ResearcherState):
        """Execute all tool calls from the previous LLM response.

        Executes all tool calls from the previous LLM responses.
        Returns updated state with tool execution results.
        """
        tool_calls = state["researcher_messages"][-1].tool_calls

        # Execute all tool calls
        observations = []
        for tool_call in tool_calls:
            tool = self.tools_by_name[tool_call["name"]]
            observations.append(tool.invoke(tool_call["args"]))

        # Create tool message outputs
        tool_outputs = [
            ToolMessage(
                content=observation,
                name=tool_call["name"],
                tool_call_id=tool_call["id"],
            )
            for observation, tool_call in zip(observations, tool_calls)
        ]

        return {"researcher_messages": tool_outputs}

    def compress_research(self, state: ResearcherState) -> dict:
        """Compress research findings into a concise summary.

        Takes all the research messages and tool outputs and creates
        a compressed summary suitable for the supervisor's decision-making.
        """
        system_message = self.compress_research_system_prompt.format(
            date=self.search_result_pipe.get_today_str()
        )
        messages = (
            [SystemMessage(content=system_message)]
            + state.get("researcher_messages", [])
            + [HumanMessage(content=self.compress_research_human_message)]
        )
        response = self.compress_model.invoke(messages)

        # Extract raw notes from tool and AI messages
        raw_notes = [
            str(m.content)
            for m in filter_messages(
                state["researcher_messages"], include_types=["tool", "ai"]
            )
        ]

        return {
            "compressed_research": str(response.content),
            "raw_notes": ["\n".join(raw_notes)],
        }

    # ===== ROUTING LOGIC =====

    def should_continue(
        self, state: ResearcherState
    ) -> Literal["tool_node", "compress_research"]:
        """Determine whether to continue research or provide final answer.

        Determines whether the agent should continue the research loop or provide
        a final answer based on whether the LLM made tool calls.

        Returns:
            "tool_node": Continue to tool execution
            "compress_research": Stop and compress research
        """
        messages = state["researcher_messages"]
        last_message = messages[-1]

        # If the LLM makes a tool call, continue to tool execution
        if last_message.tool_calls:
            return "tool_node"
        # Otherwise, we have a final answer
        return "compress_research"
