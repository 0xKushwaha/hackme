"""
Static tools used by UnknownFormatAgent to investigate unidentified files.

  format_sniffer   — magic bytes + heuristic signature detection
  content_sampler  — raw content views (hex, text, binary stats)
  structure_prober — exhaustive parser probing (30+ formats)
  schema_extractor — deep schema from a successfully parsed format
"""

from .format_sniffer   import sniff_format,   FormatHint
from .content_sampler  import sample_content,  ContentSample
from .structure_prober import probe_structure, ProbeResult
from .schema_extractor import extract_schema,  SchemaReport

__all__ = [
    "sniff_format",   "FormatHint",
    "sample_content", "ContentSample",
    "probe_structure","ProbeResult",
    "extract_schema", "SchemaReport",
]
