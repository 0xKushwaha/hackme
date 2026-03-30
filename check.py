"""
First-run health check for the Multi-Agent Data Science pipeline.

Usage:
    python check.py
    python check.py --provider openai
    python check.py --no-llm          # skip LLM connection test
"""

import os
import sys
import argparse


def ok(msg):  print(f"  ✅ {msg}")
def warn(msg): print(f"  ⚠️  {msg}")
def fail(msg): print(f"  ❌ {msg}")


# ------------------------------------------------------------------ #
# 1. Core dependencies                                                 #
# ------------------------------------------------------------------ #

def check_core_deps():
    print("\n[1] Core dependencies")
    required = [
        ("langchain",           "langchain"),
        ("langchain_anthropic", "langchain-anthropic"),
        ("langchain_openai",    "langchain-openai"),
        ("pandas",              "pandas"),
        ("sklearn",             "scikit-learn"),
        ("dotenv",              "python-dotenv"),
    ]
    all_ok = True
    for module, pkg in required:
        try:
            __import__(module)
            ok(pkg)
        except ImportError:
            fail(f"{pkg}  →  pip install {pkg}")
            all_ok = False
    return all_ok


# ------------------------------------------------------------------ #
# 2. Optional / memory dependencies                                    #
# ------------------------------------------------------------------ #

def check_optional_deps():
    print("\n[2] Optional dependencies (memory / ML)")
    optional = [
        ("chromadb",             "chromadb",             "long-term agent memory"),
        ("sentence_transformers","sentence-transformers", "embedding model"),
        ("rank_bm25",            "rank-bm25",            "BM25 hybrid search"),
        ("xgboost",              "xgboost",              "XGBoost models"),
        ("pyarrow",              "pyarrow",              "Parquet streaming (OOM guard)"),
    ]
    for module, pkg, purpose in optional:
        try:
            __import__(module)
            ok(f"{pkg}  ({purpose})")
        except ImportError:
            warn(f"{pkg} not installed — {purpose} will be unavailable  →  pip install {pkg}")


# ------------------------------------------------------------------ #
# 3. API keys                                                          #
# ------------------------------------------------------------------ #

def check_api_keys(provider: str):
    print("\n[3] API keys")
    from dotenv import load_dotenv
    load_dotenv(override=True)

    key_map = {
        "claude":  ("ANTHROPIC_API_KEY",  "Anthropic Claude"),
        "openai":  ("OPENAI_API_KEY",     "OpenAI"),
        "local":   (None,                 "local vLLM — no key needed"),
    }

    env_var, label = key_map.get(provider, (None, provider))
    if env_var is None:
        ok(f"{label}")
        return True

    val = os.getenv(env_var, "")
    if val and len(val) > 8:
        masked = val[:6] + "..." + val[-4:]
        ok(f"{env_var} found  [{masked}]  ({label})")
        return True
    else:
        fail(f"{env_var} is missing or too short — set it in .env or export it")
        return False


# ------------------------------------------------------------------ #
# 4. LLM connection test                                               #
# ------------------------------------------------------------------ #

def check_llm_connection(provider: str):
    print(f"\n[4] LLM connection test  ({provider})")
    try:
        from backends.llm_backends import get_llm
        llm = get_llm(provider)
        response = llm.invoke("Reply with exactly one word: OK")
        text = getattr(response, "content", str(response)).strip()
        ok(f"LLM responded: '{text[:60]}'")
        return True
    except Exception as e:
        fail(f"LLM call failed: {e}")
        return False


# ------------------------------------------------------------------ #
# 5. Paths                                                             #
# ------------------------------------------------------------------ #

def check_paths():
    print("\n[5] Paths")
    from pathlib import Path
    base = Path(__file__).parent
    experiments = base / "experiments"
    experiments.mkdir(exist_ok=True)
    ok(f"experiments/  →  {experiments}")

    if not (base / ".env").exists():
        warn(".env file not found — create one with your API keys")
    else:
        ok(".env file present")


# ------------------------------------------------------------------ #
# Entry point                                                          #
# ------------------------------------------------------------------ #

def main():
    parser = argparse.ArgumentParser(description="Pre-flight health check")
    parser.add_argument("--provider", default="claude",
                        help="LLM provider to test: claude | openai | local")
    parser.add_argument("--no-llm", action="store_true",
                        help="Skip the live LLM connection test")
    args = parser.parse_args()

    print("=" * 55)
    print(" Multi-Agent Data Science — health check")
    print("=" * 55)

    core_ok  = check_core_deps()
    check_optional_deps()
    keys_ok  = check_api_keys(args.provider)
    check_paths()

    if not args.no_llm and core_ok and keys_ok:
        llm_ok = check_llm_connection(args.provider)
    else:
        llm_ok = True
        if args.no_llm:
            print("\n[4] LLM connection test  (skipped via --no-llm)")

    print("\n" + "=" * 55)
    if core_ok and keys_ok and llm_ok:
        print("✅  All checks passed — ready to run!")
        print(f"   python main.py --dataset data.csv --provider {args.provider} --mode train")
    else:
        print("❌  Some checks failed — fix the issues above before running.")
        sys.exit(1)


if __name__ == "__main__":
    main()
