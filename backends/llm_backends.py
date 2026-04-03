import os
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI

# Model tiering:
#   "full"  — complex reasoning (Explorer, CodeWriter, Optimizer, Architect, Storyteller)
#   "fast"  — critique / simple planning (Skeptic, Ethicist, Devil's Advocate, Pragmatist)
_CLAUDE_MODELS = {
    "full": "claude-opus-4-6",
    "fast": "claude-haiku-4-5",
}
_OPENAI_MODELS = {
    "full": "gpt-4o",
    "fast": "gpt-4o-mini",
}

# Agents that only need a fast/cheap model
FAST_TIER_AGENTS = {"skeptic", "ethicist", "devil_advocate", "pragmatist"}


def get_llm(provider: str, model: str = None, base_url: str = None, tier: str = "full", **kwargs):
    """
    Returns a LangChain-compatible LLM.

    Providers:
        claude : Anthropic Claude  (requires ANTHROPIC_API_KEY)
        openai : OpenAI            (requires OPENAI_API_KEY)
        local  : Local vLLM server — OpenAI-compatible (requires VLLM_URL or base_url)

    tier: "full" (default) or "fast"
        "fast" uses a smaller/cheaper model for critique and simple planning agents.
        Ignored when `model` is explicitly provided or provider is "local".
    """
    if provider == "claude":
        api_key    = os.getenv("ANTHROPIC_API_KEY")
        chosen     = model or _CLAUDE_MODELS.get(tier, _CLAUDE_MODELS["full"])
        return ChatAnthropic(model=chosen, api_key=api_key, **kwargs)

    if provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        chosen  = model or _OPENAI_MODELS.get(tier, _OPENAI_MODELS["full"])
        return ChatOpenAI(model=chosen, api_key=api_key, **kwargs)

    if provider == "local":
        vllm_url   = base_url or os.getenv("VLLM_URL") or "http://localhost:8001/v1"
        vllm_model = model    or os.getenv("VLLM_MODEL") or "mistral-7b-instruct"
        vllm_url   = vllm_url.rstrip("/")
        if not vllm_url.endswith("/v1"):
            vllm_url = vllm_url + "/v1"
        return ChatOpenAI(model=vllm_model, base_url=vllm_url, api_key="EMPTY", **kwargs)

    raise ValueError(f"Unknown provider '{provider}'. Choose from: claude, openai, local")


def get_fast_llm(provider: str, model: str = None, base_url: str = None, **kwargs):
    """Convenience wrapper — returns the fast-tier LLM for the given provider."""
    return get_llm(provider, model=model, base_url=base_url, tier="fast", **kwargs)
