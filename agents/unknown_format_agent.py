"""
UnknownFormatAgent — adaptive agent for files with unidentified or unusual formats.

Triggered by DatasetDiscovery when a file's extension is missing, misleading,
or maps to a format that couldn't be parsed by standard readers.

Strategy (4 phases):
  1. SNIFF   — magic bytes + text heuristics (format_sniffer)
  2. PROBE   — try 30+ parsers in confidence order (structure_prober)
  3. EXTRACT — deep column/schema analysis (schema_extractor)
  4. LLM     — fallback: LLM inspects raw content sample when all parsers fail

Output: FormatDiscovery — a structured description the rest of the pipeline
can use exactly like a normal DatasetProfile entry.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from tools.format_sniffer   import sniff_format,   FormatHint
from tools.content_sampler  import sample_content,  ContentSample
from tools.structure_prober import probe_structure, ProbeResult
from tools.schema_extractor import extract_schema,  SchemaReport


# ------------------------------------------------------------------ #
# Output type                                                          #
# ------------------------------------------------------------------ #

@dataclass
class FormatDiscovery:
    """
    Complete result of the UnknownFormatAgent investigation.
    Compatible with the rest of the pipeline (phases, profiler, orchestrator).
    """
    original_path:   str
    confirmed_format:str            # "csv", "parquet", "sqlite", "binary_unknown", …
    category:        str            # tabular | text | image | audio | binary | archive
    parser_used:     str

    # If the format was decoded successfully
    schema:          Optional[SchemaReport] = None

    # If the agent converted the file to CSV for downstream use
    converted_csv_path: Optional[str] = None

    # Routing for the rest of the pipeline
    routing_hints:   dict  = field(default_factory=dict)
    target_candidates: list[str] = field(default_factory=list)

    # Quality
    confidence:      float = 1.0
    warnings:        list[str] = field(default_factory=list)

    # Full narrative for agent context
    summary_text:    str   = ""

    def is_usable(self) -> bool:
        """True if the pipeline can proceed with this file."""
        return self.confirmed_format != "binary_unknown"


# ------------------------------------------------------------------ #
# Agent                                                                #
# ------------------------------------------------------------------ #

class UnknownFormatAgent:
    """
    Adaptive agent that identifies and parses any unknown file format.

    Usage:
        agent = UnknownFormatAgent(llm=llm)
        discovery = agent.investigate("/path/to/mystery.dat")
        print(discovery.summary_text)
    """

    def __init__(self, llm=None, verbose: bool = True):
        self.llm     = llm
        self.verbose = verbose

    # ---------------------------------------------------------------- #
    # Public                                                            #
    # ---------------------------------------------------------------- #

    def investigate(self, path: str) -> FormatDiscovery:
        """
        3-phase investigation of an unknown file.

        Returns a FormatDiscovery regardless of outcome.
        """
        path = str(Path(path).resolve())
        self._log(f"Investigating: {os.path.basename(path)}")

        # ── Phase 1: Sniff ───────────────────────────────────────────
        self._log("  [1/3] Sniffing magic bytes and heuristics…")
        hints: list[FormatHint] = sniff_format(path)
        self._log(f"       Candidates: {[(h.format, round(h.confidence,2)) for h in hints[:5]]}")

        # ── Phase 2: Content sample ──────────────────────────────────
        self._log("  [2/3] Sampling raw content…")
        cs: ContentSample = sample_content(path)
        if cs.structure_notes:
            self._log(f"       Notes: {cs.structure_notes[:3]}")

        # ── Phase 3: Probe parsers ───────────────────────────────────
        self._log("  [3/3] Probing structure with known parsers…")
        probe: ProbeResult = probe_structure(path, hints)
        self._log(f"       Result: {probe.format} (conf={probe.confidence:.2f}, "
                  f"parser={probe.parser_used})")

        # ── Extract schema if probe succeeded ────────────────────────
        schema: Optional[SchemaReport] = None

        if probe.format != "binary_unknown":
            schema = extract_schema(path, probe)
            self._log(f"       {len(schema.columns)} columns analysed" if schema.columns
                      else "       Non-tabular schema extracted")
        else:
            self._log("       Format unrecognised by static probers")
            # ── Phase 4: LLM fallback ────────────────────────────────
            if self.llm is not None:
                self._log("  [4/4] LLM fallback — asking LLM to identify format…")
                probe = self._llm_identify(path, hints, cs, probe)
                self._log(f"       LLM result: {probe.format} (conf={probe.confidence:.2f})")
                if probe.format != "binary_unknown":
                    schema = extract_schema(path, probe)
            else:
                self._log("       No LLM available — marking as binary_unknown")

        # ── Assemble result ──────────────────────────────────────────
        discovery = self._build_discovery(path, probe, schema, hints, cs)
        self._log(f"Done. Format={discovery.confirmed_format}  Usable={discovery.is_usable()}")
        return discovery

    # ---------------------------------------------------------------- #
    # Build discovery object                                            #
    # ---------------------------------------------------------------- #

    def _build_discovery(
        self,
        path: str,
        probe: ProbeResult,
        schema: Optional[SchemaReport],
        hints: list[FormatHint],
        cs: ContentSample,
    ) -> FormatDiscovery:

        routing: dict = {}
        targets: list[str] = []
        warnings: list[str] = list(probe.parse_warnings)

        if schema:
            routing = schema.routing_hints
            targets = schema.target_candidates

        discovery = FormatDiscovery(
            original_path=path,
            confirmed_format=probe.format,
            category=probe.category,
            parser_used=probe.parser_used,
            schema=schema,
            routing_hints=routing,
            target_candidates=targets,
            confidence=probe.confidence,
            warnings=warnings,
        )

        # ── Summary text ─────────────────────────────────────────────
        lines = [
            "=" * 60,
            "UNKNOWN FORMAT AGENT — DISCOVERY REPORT",
            "=" * 60,
            f"File        : {os.path.basename(path)}",
            f"Format      : {probe.format}  (confidence {probe.confidence:.0%})",
            f"Category    : {probe.category}",
            f"Parser      : {probe.parser_used}",
        ]

        if hints:
            top = [(h.format, round(h.confidence, 2)) for h in hints[:4]]
            lines.append(f"Sniff hints : {top}")

        if cs.structure_notes:
            lines.append(f"Content     : {' | '.join(cs.structure_notes[:3])}")

        if schema and schema.summary_text:
            lines.append("")
            lines.append(schema.summary_text)
        elif probe.raw_schema:
            lines.append(f"\nSchema:\n{probe.raw_schema}")

        if warnings:
            lines.append(f"\nWarnings: {warnings}")

        if routing:
            lines.append(f"\nRouting hints: {routing}")
        if targets:
            lines.append(f"Target candidates: {targets}")

        lines.append("=" * 60)
        discovery.summary_text = "\n".join(lines)
        return discovery

    # ---------------------------------------------------------------- #
    # LLM fallback                                                      #
    # ---------------------------------------------------------------- #

    def _llm_identify(
        self,
        path: str,
        hints: list[FormatHint],
        cs: ContentSample,
        original_probe: ProbeResult,
    ) -> ProbeResult:
        """
        Ask the LLM to identify the file format when all static probers fail.
        Returns a ProbeResult with the LLM's best guess, or the original
        binary_unknown result if the LLM cannot determine the format.
        """
        fname = os.path.basename(path)
        size  = os.path.getsize(path)

        hint_summary = ", ".join(
            f"{h.format}({h.confidence:.0%})" for h in hints[:5]
        ) or "none"

        # Build a compact content snapshot for the LLM
        content_snippet = ""
        if cs.text_head:
            content_snippet = cs.text_head[:600]
        elif cs.hex_dump:
            content_snippet = f"[hex] {cs.hex_dump[:300]}"

        prompt = f"""You are a file format identification expert.

A file could not be identified by any automated parser. Analyse the evidence below and identify the format.

FILE: {fname}
SIZE: {size:,} bytes
MAGIC-BYTE HINTS: {hint_summary}

CONTENT SAMPLE:
{content_snippet}

Reply in this exact format (no other text):
FORMAT: <format name, e.g. csv / sqlite / arrow / protobuf / hdf5 / binary_unknown>
CATEGORY: <tabular | text | image | audio | binary | archive>
CONFIDENCE: <0.0–1.0>
REASON: <one sentence>
"""
        try:
            from langchain_core.messages import HumanMessage
            response = self.llm.invoke([HumanMessage(content=prompt)])
            text = response.content if hasattr(response, "content") else str(response)

            fmt      = "binary_unknown"
            category = "binary"
            conf     = 0.3

            for line in text.splitlines():
                line = line.strip()
                if line.startswith("FORMAT:"):
                    fmt = line.split(":", 1)[1].strip().lower()
                elif line.startswith("CATEGORY:"):
                    category = line.split(":", 1)[1].strip().lower()
                elif line.startswith("CONFIDENCE:"):
                    try:
                        conf = float(line.split(":", 1)[1].strip())
                    except ValueError:
                        pass

            # Rebuild a minimal ProbeResult with LLM findings
            return ProbeResult(
                format=fmt,
                category=category,
                parser_used="llm_fallback",
                confidence=conf,
                parse_warnings=original_probe.parse_warnings + ["Identified by LLM fallback"],
                raw_schema=original_probe.raw_schema,
            )

        except Exception as exc:
            self._log(f"       LLM fallback failed: {exc}")
            return original_probe

    # ---------------------------------------------------------------- #
    # Helpers                                                           #
    # ---------------------------------------------------------------- #

    def _log(self, msg: str):
        if self.verbose:
            print(f"[UnknownFormatAgent] {msg}")
