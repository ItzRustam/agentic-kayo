from src.tools.automation import open_website
from src.tools.research import search_arxiv, search_wikipedia, web_search
from src.tools.terminal import run_command
from src.tools.utils import calculate, update_user_info


TOOLS_BOARD = {
    "open_website": open_website,
    "web_search": web_search,
    "search_arxiv": search_arxiv,
    "search_wikipedia": search_wikipedia,
    "run_command": run_command,
    "calculate": calculate,
    "update_user_info": update_user_info
}

__all__ = [
    "open_website",
    "web_search",
    "search_arxiv",
    "search_wikipedia",
    "run_command",
    "calculate",
    "update_user_info",
]
