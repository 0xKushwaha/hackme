"""
UnknownFormatAgent — adaptive agent for files with unidentified or unusual formats.

Triggered by DatasetDiscovery when a file's extension is missing, misleading,
or maps to a format that couldn't be parsed by standard readers.

Strategy (3 phases):
  1. SNIFF   — magic bytes + text heuristics (format_sniffer)
  2. PROBE   — try 30+ parsers in confidence order (structure_prober)
  3. EXTRACT — deep column/schema analysis (schema_extractor)

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
        agent = UnknownFormatAgent()
        discovery = agent.investigate("/path/to/mystery.dat")
        print(discovery.summary_text)
    """

    def __init__(self, verbose: bool = True):
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
            self._log("       Format unrecognised — file marked as binary_unknown")

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
    # Helpers                                                           #
    # ---------------------------------------------------------------- #

    def _log(self, msg: str):
        if self.verbose:
            print(f"[UnknownFormatAgent] {msg}")
