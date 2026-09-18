from typing import Any, Dict, List

from langchain_core.messages import HumanMessage

from src.providers.llm.base import LLMProvider
from src.models.agents_states.state_research import Summary
from src.models.agents_states.state_scope import AgentState


class SearchResultPipe:
    def __init__(self, llm_provider: LLMProvider, summarize_webpage_prompt: str):
        self.llm_provider = llm_provider
        self.summarize_webpage_prompt = summarize_webpage_prompt

    
    def get_today_str(self) -> str:
        """Get current date in a human-readable format."""
        from datetime import datetime

        return datetime.now().strftime("%a %b %d, %Y")

    # Remove duplicates URLs
    def deduplicate_search_results(self, search_results: List[dict]) -> Dict[str, dict]:
        """Deduplicate raw search results by URL."""
        unique_results: Dict[str, dict] = {}
        for response in search_results:
            for result in response["results"]:
                url = result["url"]
                if url not in unique_results:
                    unique_results[url] = result
        return unique_results

    # Summarize the webpage content
    def summarize_webpage_content(self, model: str, webpage_content: str) -> str:
        """Summarize a single webpage's raw content using the given LLM provider."""
        try:
            summarization_model = self.llm_provider.get_chat_model(model=model)
            structured_model = summarization_model.with_structured_output(Summary)

            summary = structured_model.invoke(
                [
                    HumanMessage(
                        content=self.summarize_webpage_prompt.format(
                            webpage_content=webpage_content,
                            date=self.get_today_str(),
                        )
                    )
                ]
            )

            return (
                f"<summary>\n{summary.summary}\n</summary>\n\n"
                f"<key_excerpts>\n{summary.key_excerpts}\n</key_excerpts>"
            )
        except Exception as exc:  # noqa: BLE001 - deliberate fallback, logged by caller
            print(f"Failed to summarize webpage: {exc}")
            return webpage_content[:1000] + "..." if len(webpage_content) > 1000 else webpage_content

    # Apply the summarization on each search result
    def process_search_results(
        self, unique_results: Dict[str, dict], summarization_model: str
    ) -> Dict[str, dict]:
        """Summarize raw content for each unique search result where available."""
        processed: Dict[str, dict] = {}
        for url, result in unique_results.items():
            if not result.get("raw_content"):
                content = result["content"]
            else:
                content = self.summarize_webpage_content(summarization_model, result["raw_content"])

            processed[url] = {"title": result["title"], "content": content}
        return processed

    # Adding some small formats
    def format_search_output(self, summarized_results: Dict[str, dict]) -> str:
        """Format processed search results into a single readable string."""
        if not summarized_results:
            return "No valid search results found. Please try different search queries or use a different search API."

        formatted_output = "Search results: \n\n"
        for i, (url, result) in enumerate(summarized_results.items(), 1):
            formatted_output += f"\n\n--- SOURCE {i}: {result['title']} ---\n"
            formatted_output += f"URL: {url}\n\n"
            formatted_output += f"SUMMARY:\n{result['content']}\n\n"
            formatted_output += "-" * 80 + "\n"
        return formatted_output



    async def final_report_generation(self, writer_model, final_report_generation_prompt: str, state: AgentState):
        """
        Final report generation node.

        Synthesizes all research findings into a comprehensive final report
        """

        notes = state.get("notes", [])

        findings = "\n".join(notes)

        final_report_prompt = final_report_generation_prompt.format(
            research_brief=state.get("research_brief", ""),
            findings=findings,
            date=self.get_today_str()
        )

        final_report = await writer_model.ainvoke([HumanMessage(content=final_report_prompt)])

        return {
            "final_report": final_report.content, 
            "messages": ["Here is the final report: " + final_report.content],
        }
