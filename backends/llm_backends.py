import os
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI


def get_llm(provider: str, model: str = None, base_url: str = None, **kwargs):
    """
    Returns a LangChain-compatible LLM.

    Providers:
        claude : Anthropic Claude  (requires ANTHROPIC_API_KEY)
        openai : OpenAI            (requires OPENAI_API_KEY)
        local  : Local vLLM server — OpenAI-compatible (requires VLLM_URL or base_url)
                 Works with vLLM, Ollama, LM Studio, llama.cpp, any OpenAI-compatible server.
    """
    if provider == "claude":
        api_key = os.getenv("ANTHROPIC_API_KEY")
        return ChatAnthropic(
            model=model or "claude-3-5-haiku-20241022",
            api_key=api_key,
            **kwargs
        )

    if provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        return ChatOpenAI(
            model=model or "gpt-4o-mini",
            api_key=api_key,
            **kwargs
        )

    if provider == "local":
        # VLLMOpenAI from langchain-community is deprecated.
        # All modern local servers (vLLM, Ollama, LM Studio, llama.cpp)
        # expose an OpenAI-compatible /v1 endpoint — ChatOpenAI works directly.
        vllm_url   = base_url or os.getenv("VLLM_URL")   or "http://localhost:8000/v1"
        vllm_model = model    or os.getenv("VLLM_MODEL") or "mistral-7b-instruct"
        return ChatOpenAI(
            model=vllm_model,
            base_url=vllm_url,
            api_key="EMPTY",   # local servers don't need a real key
            **kwargs
        )

    raise ValueError(f"Unknown provider '{provider}'. Choose from: claude, openai, local")
