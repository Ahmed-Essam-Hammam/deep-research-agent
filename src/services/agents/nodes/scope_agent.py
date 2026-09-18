"""User Clarification and Research Brief Generation.

This module implements the scoping phase of the research workflow, where we:
1. Assess if the user's request needs clarification
2. Generate a detailed research brief from the conversation

The workflow uses structured output to make deterministic decisions about
whether sufficient context exists to proceed with research.
"""

from typing_extensions import Literal

from langchain_core.messages import HumanMessage, AIMessage, get_buffer_string
from langgraph.graph import END
from langgraph.types import Command

from src.models.agents_states.state_scope import AgentState, ClarifyWithUser, ResearchQuestion
from src.pipes.search_result_pipes import SearchResultPipe

class ScopeAgent:
    def __init__(self, model, 
                 clarify_with_user_instructions: str,
                 transform_messages_into_research_topic_prompt: str,
                 search_result_pipe: SearchResultPipe,):
        
        self.model = model
        self.clarify_with_user_instructions = clarify_with_user_instructions
        self.transform_messages_into_research_topic_prompt = transform_messages_into_research_topic_prompt
        self.search_result_pipe = search_result_pipe



    def clarify_with_user(self, state: AgentState) -> Command[Literal["write_research_brief", "__end__"]]:
        """
        Determine if the user's request contains sufficient information to proceed with research.

        Uses structured output to make deterministic decisions and avoid hallucination.
        Routes to either research brief generation or ends with a clarification question.
        """
        # Set up structured output model
        structured_output_model = self.model.with_structured_output(ClarifyWithUser)

        # Invoke the model with clarification instructions
        response = structured_output_model.invoke([
            HumanMessage(content=self.clarify_with_user_instructions.format(
                messages=get_buffer_string(messages=state["messages"]), 
                date=self.search_result_pipe.get_today_str()
            ))
        ])

        # Route based on clarification need
        if response.need_clarification:
            return Command(
                goto=END, 
                update={"messages": [AIMessage(content=response.question)]}
            )
        else:
            return Command(
                goto="write_research_brief", 
                update={"messages": [AIMessage(content=response.verification)]}
        )

    def write_research_brief(self, state: AgentState):
        """
        Transform the conversation history into a comprehensive research brief.

        Uses structured output to ensure the brief follows the required format
        and contains all necessary details for effective research.
        """
        # Set up structured output model
        structured_output_model = self.model.with_structured_output(ResearchQuestion)

        # Generate research brief from conversation history
        response = structured_output_model.invoke([
            HumanMessage(content=self.transform_messages_into_research_topic_prompt.format(
                messages=get_buffer_string(state.get("messages", [])),
                date=self.search_result_pipe.get_today_str()
            ))
        ])

        # Update state with generated research brief and pass it to the supervisor
        return {
            "research_brief": response.research_brief,
            "supervisor_messages": [HumanMessage(content=f"{response.research_brief}.")]
        }


