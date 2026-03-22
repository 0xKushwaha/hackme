"""
FallbackLLM — multi-provider LLM with cooldown-aware rotation.

Ported from OpenClaw's src/agents/model-fallback.ts.

Behavior:
  - Maintains a list of (provider, model) profiles in priority order
  - On rate limit / overload → puts provider on 30s cooldown, tries next
  - On auth error → disables ALL profiles from that provider
  - On context overflow → does NOT fall back (smaller model = worse)
  - On billing error → only allows retry if single-provider setup
  - Exponential backoff on overload: 250ms → 500ms → 1s → 1.5s (max)
  - Each profile tracks: last_error_type, cooldown_until, consecutive_failures
"""

import time
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

from backends.llm_backends import get_llm


# Cooldown durations (seconds)
RATE_LIMIT_COOLDOWN  = 30.0
OVERLOAD_COOLDOWN    = 10.0
AUTH_COOLDOWN        = 3600.0   # 1 hour — effectively disabled

# Backoff config (mirrors OpenClaw: initialMs=250, maxMs=1500, factor=2)
BACKOFF_INITIAL_S = 0.25
BACKOFF_MAX_S     = 1.5
BACKOFF_FACTOR    = 2.0

# Error type constants
ERR_RATE_LIMIT      = "rate_limit"
ERR_AUTH            = "auth"
ERR_BILLING         = "billing"
ERR_CONTEXT_OVERFLOW = "context_overflow"
ERR_OVERLOAD        = "overload"
ERR_UNKNOWN         = "unknown"


@dataclass
class ProviderProfile:
    provider:              str
    model:                 Optional[str]  = None
    name:                  str            = ""         # display name
    cooldown_until:        Optional[float] = None      # epoch seconds
    last_error_type:       Optional[str]  = None
    consecutive_failures:  int            = 0
    disabled:              bool           = False
    _llm:                  object         = field(default=None, repr=False)

    def __post_init__(self):
        if not self.name:
            self.name = f"{self.provider}/{self.model or 'default'}"

    def is_available(self) -> bool:
        if self.disabled:
            return False
        if self.cooldown_until and time.time() < self.cooldown_until:
            remaining = self.cooldown_until - time.time()
            return False
        return True

    def set_cooldown(self, seconds: float, error_type: str = ERR_UNKNOWN):
        self.cooldown_until      = time.time() + seconds
        self.last_error_type     = error_type
        self.consecutive_failures += 1

    def reset(self):
        self.cooldown_until      = None
        self.last_error_type     = None
        self.consecutive_failures = 0

    def get_llm(self, **kwargs):
        if self._llm is None:
            self._llm = get_llm(self.provider, model=self.model, **kwargs)
        return self._llm

    def cooldown_remaining(self) -> float:
        if not self.cooldown_until:
            return 0.0
        return max(0.0, self.cooldown_until - time.time())


def _classify_error(exc: Exception) -> str:
    """Classify an LLM exception into an error type."""
    msg = str(exc).lower()
    if any(k in msg for k in ["rate limit", "rate_limit", "too many requests", "429"]):
        return ERR_RATE_LIMIT
    if any(k in msg for k in ["unauthorized", "invalid api key", "authentication", "401", "403"]):
        return ERR_AUTH
    if any(k in msg for k in ["billing", "quota exceeded", "payment"]):
        return ERR_BILLING
    if any(k in msg for k in ["context length", "maximum context", "too long", "tokens exceed"]):
        return ERR_CONTEXT_OVERFLOW
    if any(k in msg for k in ["overloaded", "503", "502", "server error", "timeout"]):
        return ERR_OVERLOAD
    return ERR_UNKNOWN


class FallbackLLM:
    """
    LangChain-compatible LLM wrapper that rotates across providers on failure.

    Usage:
        llm = FallbackLLM([
            ProviderProfile("claude", model="claude-3-5-haiku-20241022"),
            ProviderProfile("openai", model="gpt-4o-mini"),
        ])
        response = llm.invoke(messages)
    """

    def __init__(self, profiles: list[ProviderProfile], verbose: bool = True):
        if not profiles:
            raise ValueError("At least one ProviderProfile required.")
        self.profiles  = profiles
        self.verbose   = verbose
        self._backoff  = BACKOFF_INITIAL_S

    def invoke(self, messages, **kwargs):
        last_exc = None

        for profile in self.profiles:
            if not profile.is_available():
                if self.verbose:
                    remaining = profile.cooldown_remaining()
                    print(f"[FallbackLLM] {profile.name} on cooldown ({remaining:.0f}s remaining). Skipping.")
                continue

            try:
                llm      = profile.get_llm()
                response = llm.invoke(messages, **kwargs)
                profile.reset()
                self._backoff = BACKOFF_INITIAL_S   # reset backoff on success
                return response

            except Exception as exc:
                last_exc   = exc
                error_type = _classify_error(exc)
                if self.verbose:
                    print(f"[FallbackLLM] {profile.name} failed ({error_type}): {str(exc)[:120]}")

                if error_type == ERR_CONTEXT_OVERFLOW:
                    # Don't fall back — a smaller model will fail worse
                    raise

                if error_type == ERR_AUTH:
                    # Disable all profiles from this provider
                    for p in self.profiles:
                        if p.provider == profile.provider:
                            p.disabled = True
                            if self.verbose:
                                print(f"[FallbackLLM] Disabling all {profile.provider} profiles (auth error).")

                elif error_type == ERR_RATE_LIMIT:
                    profile.set_cooldown(RATE_LIMIT_COOLDOWN, error_type)

                elif error_type == ERR_OVERLOAD:
                    # Exponential backoff before trying next provider
                    wait = min(self._backoff + random.uniform(0, 0.1), BACKOFF_MAX_S)
                    if self.verbose:
                        print(f"[FallbackLLM] Overload — waiting {wait:.2f}s before next attempt.")
                    time.sleep(wait)
                    self._backoff = min(self._backoff * BACKOFF_FACTOR, BACKOFF_MAX_S)
                    profile.set_cooldown(OVERLOAD_COOLDOWN, error_type)

                elif error_type == ERR_BILLING:
                    single_provider = len({p.provider for p in self.profiles}) == 1
                    if not single_provider:
                        profile.set_cooldown(AUTH_COOLDOWN, error_type)

                else:
                    profile.set_cooldown(OVERLOAD_COOLDOWN, error_type)

        if last_exc:
            raise last_exc
        raise RuntimeError("All LLM provider profiles exhausted or unavailable.")

    def status(self) -> list[dict]:
        """Return status of all profiles for debugging."""
        return [
            {
                "name":    p.name,
                "available": p.is_available(),
                "disabled":  p.disabled,
                "cooldown_remaining": round(p.cooldown_remaining(), 1),
                "last_error": p.last_error_type,
                "failures":  p.consecutive_failures,
            }
            for p in self.profiles
        ]

    def print_status(self):
        print("\n[FallbackLLM] Provider status:")
        for s in self.status():
            state = "disabled" if s["disabled"] else (
                f"cooldown {s['cooldown_remaining']}s" if s["cooldown_remaining"] > 0 else "ok"
            )
            print(f"  {s['name']:35s} {state:20s} failures={s['failures']}")


def build_fallback_llm(providers: list[dict]) -> FallbackLLM:
    """
    Convenience builder.

    providers = [
        {"provider": "claude", "model": "claude-3-5-haiku-20241022"},
        {"provider": "openai", "model": "gpt-4o-mini"},
    ]
    """
    profiles = [
        ProviderProfile(
            provider=p["provider"],
            model=p.get("model"),
            name=p.get("name", f"{p['provider']}/{p.get('model','default')}"),
        )
        for p in providers
    ]
    return FallbackLLM(profiles)
