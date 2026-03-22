"""
ToolRegistry — agents write reusable Python utility modules here mid-run.

Why this works without restarting the orchestrator:
  The main process stays running. Training scripts execute as *subprocesses*
  via CodeExecutor. Each subprocess starts fresh and imports from disk, so
  any module written to tool_registry/ between attempts is automatically
  available the next time — no reload of the orchestrator needed.

Workflow:
  1. Agent (or code_writer) calls registry.register(name, code, description)
  2. Module is written to tool_registry/<name>.py
  3. registry.get_import_block([name]) returns the sys.path + import lines
     to prepend to the generated training script
  4. Next subprocess imports the module and reuses the logic

Index:
  _index.json  — lightweight JSON index (name → metadata)
  ChromaDB     — optional semantic search over descriptions
"""

import json
import os
import re
from datetime import datetime
from typing import Optional


REGISTRY_DIR  = "tool_registry"
INDEX_FILE    = "_index.json"


class ToolRegistry:
    """
    Manages a directory of reusable Python utility modules.
    Agents can write tools mid-run; the next training subprocess picks them
    up automatically because CodeExecutor runs scripts as fresh subprocesses.
    """

    def __init__(
        self,
        registry_dir:     str = REGISTRY_DIR,
        chroma_collection = None,
    ):
        self.registry_dir   = os.path.abspath(registry_dir)
        self.chroma         = chroma_collection
        self._index_path    = os.path.join(self.registry_dir, INDEX_FILE)
        os.makedirs(self.registry_dir, exist_ok=True)
        self._index: dict[str, dict] = self._load_index()

    # ------------------------------------------------------------------ #
    # Write a new tool                                                     #
    # ------------------------------------------------------------------ #

    def register(
        self,
        name:        str,
        code:        str,
        description: str,
        author:      str       = "agent",
        tags:        list[str] = None,
        overwrite:   bool      = True,
    ) -> str:
        """
        Write a Python module to tool_registry/<name>.py and index it.
        Returns the absolute path to the written file.
        """
        safe_name = re.sub(r"[^a-zA-Z0-9_]", "_", name).strip("_") or "tool"
        file_path = os.path.join(self.registry_dir, f"{safe_name}.py")

        if not overwrite and os.path.exists(file_path):
            print(f"[ToolRegistry] '{safe_name}' already exists — skipping.")
            return file_path

        header = (
            f'"""\nTool       : {safe_name}\n'
            f'Description: {description}\n'
            f'Author     : {author}\n'
            f'Registered : {datetime.now().isoformat()}\n"""\n\n'
        )
        with open(file_path, "w") as f:
            f.write(header + code)

        entry = {
            "name":       safe_name,
            "description": description,
            "path":       file_path,
            "author":     author,
            "tags":       tags or [],
            "registered": datetime.now().isoformat(),
        }
        self._index[safe_name] = entry
        self._save_index()

        # Optionally index in ChromaDB for semantic search
        if self.chroma:
            try:
                self.chroma.upsert(
                    ids=[safe_name],
                    documents=[f"{description}\n\n{code[:500]}"],
                    metadatas=[{
                        "path":   file_path,
                        "author": author,
                        "tags":   ",".join(tags or []),
                    }],
                )
            except Exception:
                pass

        print(f"[ToolRegistry] Registered '{safe_name}' → {file_path}")
        return file_path

    # ------------------------------------------------------------------ #
    # Search / list                                                        #
    # ------------------------------------------------------------------ #

    def search(self, query: str, top_k: int = 3) -> list[dict]:
        """
        Semantic search via ChromaDB, or keyword fallback over the JSON index.
        Returns list of {name, description, path, distance?}.
        """
        if self.chroma and self._index:
            try:
                n = min(top_k, len(self._index))
                results = self.chroma.query(
                    query_texts=[query],
                    n_results=n,
                    include=["ids", "metadatas", "distances"],
                )
                return [
                    {
                        "name":        doc_id,
                        "description": self._index.get(doc_id, {}).get("description", ""),
                        "path":        meta.get("path", ""),
                        "distance":    dist,
                    }
                    for doc_id, meta, dist in zip(
                        results["ids"][0],
                        results["metadatas"][0],
                        results["distances"][0],
                    )
                ]
            except Exception:
                pass

        # Keyword fallback
        q = query.lower()
        matches = [
            e for e in self._index.values()
            if q in e["description"].lower()
            or any(q in t.lower() for t in e.get("tags", []))
        ]
        return matches[:top_k]

    def list_all(self) -> list[dict]:
        """Return all registered tools."""
        return list(self._index.values())

    def get(self, name: str) -> Optional[dict]:
        return self._index.get(name)

    # ------------------------------------------------------------------ #
    # Code generation helpers                                              #
    # ------------------------------------------------------------------ #

    def get_import_block(self, tool_names: list[str]) -> str:
        """
        Return Python import lines to prepend to a generated training script.
        Adds tool_registry/ to sys.path so imports just work.

        Example output:
            import sys, os
            sys.path.insert(0, '/abs/path/to/tool_registry')
            import preprocessing_utils
            import feature_helpers
        """
        lines = [
            "import sys as _sys, os as _os",
            f"_sys.path.insert(0, {repr(self.registry_dir)})",
        ]
        for name in tool_names:
            safe = re.sub(r"[^a-zA-Z0-9_]", "_", name).strip("_")
            if safe in self._index:
                lines.append(f"import {safe}")
        return "\n".join(lines)

    def build_tool_context(self) -> str:
        """
        Returns a human-readable summary of available tools for injection
        into agent prompts so they know what utilities exist.
        """
        if not self._index:
            return ""
        lines = ["Available tool_registry modules (importable in generated code):"]
        for entry in self._index.values():
            tags = ", ".join(entry.get("tags", [])) or "general"
            lines.append(f"  - {entry['name']}: {entry['description']} [tags: {tags}]")
        return "\n".join(lines)

    # ------------------------------------------------------------------ #
    # Persistence                                                          #
    # ------------------------------------------------------------------ #

    def _load_index(self) -> dict:
        if os.path.exists(self._index_path):
            try:
                with open(self._index_path) as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save_index(self):
        with open(self._index_path, "w") as f:
            json.dump(self._index, f, indent=2)

    def print_summary(self):
        print(f"\n[ToolRegistry] {len(self._index)} tools registered in {self.registry_dir}:")
        for entry in self._index.values():
            print(f"  - {entry['name']:30s} | {entry['description'][:60]}")
