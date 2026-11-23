"""Factory for creating primary conversational LLMs."""
from langchain_openrouter import ChatOpenRouter
from src.config_loader import get_configs

def get_model() -> ChatOpenRouter:
    """
    Initialize and return the conversational model.
    Raises ValueError if OPENROUTER_API_KEY is not configured.
    """

    cfg = get_configs()

    return ChatOpenRouter(
        model=cfg["model"],
        api_key=cfg["api_key"],
        temperature=0.3
    )

