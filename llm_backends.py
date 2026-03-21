from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langchain_community.llms import VLLMOpenAI


def get_llm(provider: str, model: str = None, base_url: str = None, **kwargs):
    """
    Returns a LangChain LLM based on the provider.

    Providers:
        - "claude"  : Anthropic Claude (requires ANTHROPIC_API_KEY env var)
        - "openai"  : OpenAI (requires OPENAI_API_KEY env var)
        - "local"   : Local vLLM server (requires VLLM_URL env var or base_url param)

    Usage:
        llm = get_llm("claude")
        llm = get_llm("local", base_url="http://localhost:8000/v1", model="mistral-7b")
    """
    if provider == "claude":
        return ChatAnthropic(
            model=model or "claude-3-5-haiku-20241022",
            **kwargs
        )

    elif provider == "openai":
        return ChatOpenAI(
            model=model or "gpt-4o-mini",
            **kwargs
        )

    elif provider == "local":
        return VLLMOpenAI(
            openai_api_base=base_url or "http://localhost:8000/v1",
            model_name=model or "mistral-7b-instruct",
            openai_api_key="EMPTY",   # vLLM doesn't need a key
            **kwargs
        )

    else:
        raise ValueError(f"Unknown provider '{provider}'. Choose from: claude, openai, local")
