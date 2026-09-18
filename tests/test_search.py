from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.providers.search.base import SearchProvider
from src.providers.search.factory import get_search_provider, register_search_provider
from src.providers.search.tavily_provider import TavilySearchProvider
from src.services.search.search_service import SearchService
from src.pipes.search_result_pipes import SearchResultPipe


# ===== TavilySearchProvider (mocked TavilyClient - no real network calls) =====

def test_search_calls_the_underlying_client_with_expected_args():
    with patch("src.providers.search.tavily_provider.TavilyClient") as fake_client_cls:
        fake_client = MagicMock()
        fake_client.search.return_value = {"results": []}
        fake_client_cls.return_value = fake_client

        provider = TavilySearchProvider(api_key="test-key")
        result = provider.search("weather in Cairo", max_results=5, topic="news", include_raw_content=False)

        fake_client_cls.assert_called_once_with(api_key="test-key")
        fake_client.search.assert_called_once_with(
            "weather in Cairo", max_results=5, include_raw_content=False, topic="news"
        )
        assert result == {"results": []}


def test_search_provider_reads_the_environment_when_no_api_key_is_given():
    with patch("src.providers.search.tavily_provider.TavilyClient") as fake_client_cls:
        TavilySearchProvider(api_key=None)
        fake_client_cls.assert_called_once_with()  


def test_search_provider_implements_the_search_provider_interface():
    with patch("src.providers.search.tavily_provider.TavilyClient"):
        assert isinstance(TavilySearchProvider(api_key="k"), SearchProvider)


# ===== Search provider factory =====

def test_factory_returns_a_tavily_provider():
    with patch("src.providers.search.tavily_provider.TavilyClient"):
        provider = get_search_provider("tavily", api_key="k")
        assert isinstance(provider, TavilySearchProvider)


def test_factory_is_case_insensitive():
    with patch("src.providers.search.tavily_provider.TavilyClient"):
        assert isinstance(get_search_provider("TAVILY"), TavilySearchProvider)


def test_factory_raises_for_an_unknown_provider_name():
    with pytest.raises(ValueError, match="Unknown search provider"):
        get_search_provider("bing")


def test_register_search_provider_adds_a_new_entry():
    class FakeProvider(SearchProvider):
        def search(self, query, max_results=3, topic="general", include_raw_content=True):
            return {"results": []}

    register_search_provider("fake", lambda api_key: FakeProvider())
    try:
        assert isinstance(get_search_provider("fake"), FakeProvider)
    finally:
        from src.providers.search.factory import _PROVIDER_REGISTRY
        _PROVIDER_REGISTRY.pop("fake", None)


# ===== SearchService =====

def test_tavily_search_multiple_executes_one_search_call_per_query():
    fake_provider = MagicMock(spec=SearchProvider)
    fake_provider.search.side_effect = [{"results": [{"url": "a"}]}, {"results": [{"url": "b"}]}]
    service = SearchService(search_client=fake_provider)

    results = service.tavily_search_multiple(["query one", "query two"])

    assert fake_provider.search.call_count == 2
    assert results == [{"results": [{"url": "a"}]}, {"results": [{"url": "b"}]}]


def test_tavily_search_multiple_passes_through_options_to_every_query():
    fake_provider = MagicMock(spec=SearchProvider)
    fake_provider.search.return_value = {"results": []}
    service = SearchService(search_client=fake_provider)

    service.tavily_search_multiple(["q"], max_results=7, topic="finance", include_raw_content=False)

    fake_provider.search.assert_called_once_with(
        "q", max_results=7, include_raw_content=False, topic="finance"
    )


def test_tavily_search_multiple_returns_empty_list_for_no_queries():
    service = SearchService(search_client=MagicMock(spec=SearchProvider))
    assert service.tavily_search_multiple([]) == []


# ===== SearchResultPipe =====

@pytest.fixture
def pipe():
    llm_provider = MagicMock()
    return SearchResultPipe(llm_provider=llm_provider, summarize_webpage_prompt="{webpage_content} | {date}")


def test_get_today_str_matches_expected_format(pipe):
    import re
    assert re.match(r"^[A-Za-z]{3} [A-Za-z]{3} \d{2}, \d{4}$", pipe.get_today_str())


def test_deduplicate_search_results_keeps_first_occurrence_per_url(pipe):
    search_results = [
        {"results": [{"url": "https://a.com", "title": "First A"}]},
        {"results": [{"url": "https://a.com", "title": "Duplicate A"}, {"url": "https://b.com", "title": "B"}]},
    ]

    unique = pipe.deduplicate_search_results(search_results)

    assert set(unique.keys()) == {"https://a.com", "https://b.com"}
    assert unique["https://a.com"]["title"] == "First A"


def test_process_search_results_uses_plain_content_when_no_raw_content(pipe):
    unique_results = {"https://a.com": {"title": "A", "content": "short summary", "raw_content": None}}

    processed = pipe.process_search_results(unique_results, "gpt-4.1")

    assert processed["https://a.com"] == {"title": "A", "content": "short summary"}


def test_process_search_results_summarizes_when_raw_content_present(pipe, monkeypatch):
    monkeypatch.setattr(pipe, "summarize_webpage_content", lambda model, content: f"SUMMARY({model}):{content}")
    unique_results = {"https://a.com": {"title": "A", "content": "short", "raw_content": "very long raw html..."}}

    processed = pipe.process_search_results(unique_results, "gpt-4.1")

    assert processed["https://a.com"]["content"] == "SUMMARY(gpt-4.1):very long raw html..."


def test_format_search_output_returns_placeholder_for_no_results(pipe):
    assert "No valid search results" in pipe.format_search_output({})


def test_format_search_output_includes_titles_and_urls(pipe):
    summarized = {"https://a.com": {"title": "Page A", "content": "content A"}}

    output = pipe.format_search_output(summarized)

    assert "Page A" in output
    assert "https://a.com" in output
    assert "content A" in output


def test_summarize_webpage_content_returns_structured_summary(pipe):
    fake_summary = MagicMock(summary="a concise summary", key_excerpts="an excerpt")
    structured_model = MagicMock()
    structured_model.invoke.return_value = fake_summary
    chat_model = MagicMock()
    chat_model.with_structured_output.return_value = structured_model
    pipe.llm_provider.get_chat_model.return_value = chat_model

    result = pipe.summarize_webpage_content("gpt-4.1", "raw webpage text")

    assert "a concise summary" in result
    assert "an excerpt" in result


def test_summarize_webpage_content_falls_back_to_truncated_text_on_error(pipe):
    pipe.llm_provider.get_chat_model.side_effect = RuntimeError("model unavailable")

    long_text = "x" * 1500
    result = pipe.summarize_webpage_content("gpt-4.1", long_text)

    assert result == "x" * 1000 + "..."


def test_summarize_webpage_content_returns_short_text_unmodified_on_error(pipe):
    pipe.llm_provider.get_chat_model.side_effect = RuntimeError("model unavailable")

    short_text = "too short to truncate"
    assert pipe.summarize_webpage_content("gpt-4.1", short_text) == short_text


@pytest.mark.asyncio
async def test_final_report_generation_builds_the_report_from_notes(pipe):
    writer_model = MagicMock()
    writer_model.ainvoke = AsyncMock(return_value=MagicMock(content="Final report body"))
    state = {"notes": ["finding one", "finding two"], "research_brief": "brief text"}

    result = await pipe.final_report_generation(
        writer_model, "Brief: {research_brief}\nFindings: {findings}\nDate: {date}", state
    )

    assert result["final_report"] == "Final report body"
    assert "Final report body" in result["messages"][0]
    prompt_used = writer_model.ainvoke.call_args.args[0][0].content
    assert "finding one" in prompt_used and "finding two" in prompt_used
    assert "brief text" in prompt_used
