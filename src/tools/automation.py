import webbrowser
from langchain_core.tools import tool


@tool
def open_website(url: str | None = None) -> str:
    """Open a website in a new tab using the default web browser.

    Args:
        url: The URL of the website to open.
    """
    try:
        if not url:
            return "URL cannot be empty or None."

        webbrowser.open_new_tab(url)
        return f"Open the given url {url} without any error"

    except Exception as e:
        return str(e)
