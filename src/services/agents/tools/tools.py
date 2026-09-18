from typing_extensions import Annotated, Literal

from langchain_core.tools import tool, InjectedToolArg

from src.services.search.search_service import SearchService
from src.dependencies.injection import get_app_settings, _get_search_provider
from src.providers.llm.factory import get_llm_provider
from src.prompts.prompts import summarize_webpage_prompt
from src.pipes.search_result_pipes import SearchResultPipe


settings = get_app_settings()


search_provider = _get_search_provider(settings.search_provider)                           # Empty for tavily which is the provider
search_obj = SearchService(search_client=search_provider)

llm_provider = get_llm_provider(settings.default_llm_provider)
pipe_obj = SearchResultPipe(llm_provider=llm_provider, summarize_webpage_prompt=summarize_webpage_prompt)




@tool(parse_docstring=True)
def tavily_search(
    query: str,
    summarization_model = settings.default_llm_model,
    max_results: Annotated[int, InjectedToolArg] = 3,
    topic: Annotated[Literal["general", "news", "finance"], InjectedToolArg] = "general",
) -> str:
    """Fetch results from Tavily search API with content summarization.

    Args:
        query: A single search query to execute
        max_results: Maximum number of results to return
        topic: Topic to filter results by ('general', 'news', 'finance')

    Returns:
        Formatted string of search results with summaries
    """
    # Execute search for single query
    search_results = search_obj.tavily_search_multiple(
        [query],  # Convert single query to list for the internal function
        max_results=max_results,
        topic=topic,
        include_raw_content=True,
    )

    # Deduplicate results by URL to avoid processing duplicate content
    unique_results = pipe_obj.deduplicate_search_results(search_results)

    # Process results with summarization
    summarized_results = pipe_obj.process_search_results(unique_results, summarization_model)

    # Format output for consumption
    return pipe_obj.format_search_output(summarized_results)

@tool(parse_docstring=True)
def think_tool(reflection: str) -> str:
    """Tool for strategic reflection on research progress and decision-making.

    Use this tool after each search to analyze results and plan next steps systematically.
    This creates a deliberate pause in the research workflow for quality decision-making.

    When to use:
    - After receiving search results: What key information did I find?
    - Before deciding next steps: Do I have enough to answer comprehensively?
    - When assessing research gaps: What specific information am I still missing?
    - Before concluding research: Can I provide a complete answer now?

    Reflection should address:
    1. Analysis of current findings - What concrete information have I gathered?
    2. Gap assessment - What crucial information is still missing?
    3. Quality evaluation - Do I have sufficient evidence/examples for a good answer?
    4. Strategic decision - Should I continue searching or provide my answer?

    Args:
        reflection: Your detailed reflection on research progress, findings, gaps, and next steps

    Returns:
        Confirmation that reflection was recorded for decision-making
    """
    return f"Reflection recorded: {reflection}"




