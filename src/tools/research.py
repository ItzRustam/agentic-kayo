# Author: ItzRustam (Rustam Singh Bhadouriya)
# Project: Agentic Kayo | Licensed under the MIT License

from langchain_core.tools import tool
from ddgs import DDGS
import wikipediaapi
import arxiv


@tool
def web_search(query: str) -> str:
    """Search the web using DuckDuckGo and return relevant search results."""

    try:
        results = DDGS().text(query, max_results=5)

        if not results:
            return "No search results found."

        return "\n\n".join(
            f"Title: {result.get('title', '')}\n"
            f"URL: {result.get('href', '')}\n"
            f"Snippet: {result.get('body', '')}"
            for result in results
        )

    except Exception as e:
        return f"Error while searching web: {e}"


@tool
def search_arxiv(query: str) -> str:
    """Search arXiv for scientific papers and return their titles, authors, publication dates, abstracts, and links."""

    try:
        client = arxiv.Client()

        search = arxiv.Search(
            query=query,
            max_results=2,
            sort_by=arxiv.SortCriterion.Relevance
        )

        results = []

        for paper in client.results(search):
            paper_info = (
                f"Title: {paper.title}\n"
                f"Published: {paper.published.date()}\n"
                f"Authors: {', '.join(author.name for author in paper.authors)}\n"
                f"Abstract: {paper.summary.strip()}\n"
                f"URL: {paper.entry_id}"
            )

            results.append(paper_info)

        if not results:
            return f"No arXiv results found for: {query}"

        return "\n\n---\n\n".join(results)

    except Exception as e:
        return f"Error while querying arXiv: {e}"


@tool
def search_wikipedia(topic: str, language: str = "en") -> str:
    """Search Wikipedia for a topic in the specified language and return its article summary and URL."""

    try:
        wiki = wikipediaapi.Wikipedia(
            language=language,
            user_agent="AgenticKayo/1.0 (AI assistant)"
        )

        page = wiki.page(topic)

        if not page.exists():
            return f"Wikipedia article not found: {topic}"

        return (
            f"Title: {page.title}\n"
            f"URL: {page.fullurl}\n"
            f"Summary:\n{page.summary}"
        )

    except Exception as e:
        return f"Error while searching Wikipedia: {e}"