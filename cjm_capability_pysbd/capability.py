"""Pure-compute sentence-segmentation tool capability using pySBD (Option C; B.5 work item 81e43606)."""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from cjm_capability_primitives.sentence_segmentation import SentenceSegmentationResult, SentenceSpan
from cjm_substrate.core.capability import RELOAD_TRIGGER, ToolCapability
from cjm_substrate.core.errors import CapabilityFatalError, CapabilityInputError
from cjm_substrate.utils.validation import (config_to_dict, dataclass_to_jsonschema, dict_to_config,
                                            SCHEMA_DESC, SCHEMA_TITLE)

# The tool is PURE COMPUTE (PILLAR 1c): `segment_text` runs pySBD's rule-based
# Golden-Rules segmenter over the caller's original text and builds the typed
# result. No cache, no storage, no model download — pySBD is pure-pip rules
# (the DEC cc904eee rationale: built for the abbreviation/initial/title class
# the decomp sentence-split token heuristic chased across v2/v3).

# pySBD Imports
try:
    import pysbd
    PYSBD_AVAILABLE = True
except ImportError:
    PYSBD_AVAILABLE = False


@dataclass
class PySBDConfig:
    """Configuration for the pySBD segmenter.

    `clean` and `char_span` are deliberately NOT config fields: the task
    contract is char spans over the ORIGINAL text, which requires
    `char_span=True` and `clean=False` (pySBD refuses the combination
    otherwise) — they are contract invariants, not knobs.
    """

    language: str = field(
        default="en",
        metadata={
            SCHEMA_TITLE: "Language",
            SCHEMA_DESC: "pySBD language code (ISO 639-1) selecting the Golden-Rules set.",
            RELOAD_TRIGGER: "segmenter",  # a language change invalidates the built segmenter
        }
    )


class PySBDSegmentationCapability(ToolCapability):
    """Sentence-segmentation tool capability using pySBD (pure compute).

    Native-surface model (PILLAR 1c): `segment_text` runs the rule-based
    segmenter over the caller's ORIGINAL text and returns typed
    `SentenceSpan`s indexing into exactly that string, trimmed to
    non-whitespace extents (pySBD's raw spans carry inter-sentence
    whitespace). The generic adapter
    (cjm-sentence-segmentation-adapter-interface) is a thin pass-through —
    no cache bookends, because rule-based segmentation is deterministic
    sub-millisecond CPU work."""

    config_class = PySBDConfig

    def __init__(self):
        """Initialize the pySBD segmentation capability."""
        self.logger = logging.getLogger(f"{__name__}.{type(self).__name__}")
        self.config: Optional[PySBDConfig] = None
        self._segmenter = None

    @property
    def name(self) -> str:  # Capability name identifier
        """Capability identity, derived from the installed distribution (PILLAR 1c)."""
        from importlib.metadata import metadata, packages_distributions
        dist = (packages_distributions().get(__package__) or [__package__.replace("_", "-")])[0]
        return metadata(dist)["Name"]

    @property
    def version(self) -> str:  # Capability version string
        """Get the capability version string."""
        from cjm_capability_pysbd import __version__
        return __version__

    def get_current_config(self) -> Dict[str, Any]:  # Current configuration as dictionary
        """Return current configuration state."""
        return config_to_dict(self.config) if self.config else {}

    def get_config_schema(self) -> Dict[str, Any]:  # JSON Schema for configuration
        """Return JSON Schema for UI generation."""
        return dataclass_to_jsonschema(PySBDConfig)

    def _apply_config(
        self,
        config: Optional[Any] = None  # Configuration dataclass, dict, or None
    ) -> None:
        """Apply config values only (no heavy-resource work). Called by
        initialize (first-time) and by the substrate's reconfigure delta path."""
        self.config = dict_to_config(PySBDConfig, config or {})

    def initialize(
        self,
        config: Optional[Any] = None  # Configuration dataclass, dict, or None
    ) -> None:
        """First-time setup. Config application is factored into _apply_config;
        the substrate's reconfigure(old, new) fires _release_segmenter on a
        language change (RELOAD_TRIGGER) then re-applies config."""
        self._apply_config(config)
        self.logger.info(f"Initialized pySBD segmentation capability (language={self.config.language})")

    def _load_segmenter(self) -> None:
        """Lazily build the pySBD segmenter for the configured language.

        `clean=False` + `char_span=True` are the task-contract invariants:
        spans must index into the caller's ORIGINAL text."""
        if self._segmenter is None:
            if not PYSBD_AVAILABLE:
                raise CapabilityFatalError(  # load-time dependency missing — fatal until operator installs pysbd
                    "pysbd not installed.",
                )
            self._segmenter = pysbd.Segmenter(
                language=self.config.language, clean=False, char_span=True)

    def _release_segmenter(self) -> None:
        """Release the built segmenter. RELOAD_TRIGGER target for `language`;
        on_disable / cleanup delegate here. Guarded so a redundant call is a no-op."""
        if self._segmenter is not None:
            self._segmenter = None

    def segment_text(
        self,
        text: str,   # The original (punctuated) text to segment
        **kwargs     # Provenance pass-through (unused by segmentation compute)
    ) -> SentenceSegmentationResult:  # Ordered sentence spans over `text`
        """Segment text into ordered sentence character spans — PURE COMPUTE.

        pySBD's raw char spans carry inter-sentence whitespace (and newline
        runs) at the edges; each span is trimmed to its non-whitespace extents
        so downstream consumers (the decomp sentence-split stage mapping
        sentence ends onto FA word spans) see tight sentence boundaries.
        Whitespace-only spans are dropped; empty text yields no spans."""
        if not isinstance(text, str):
            raise CapabilityInputError(  # typed input-validation
                f"Unsupported text input type: {type(text)}; expected str",
                fields_invalid=["text"],
            )
        self._load_segmenter()

        spans: List[SentenceSpan] = []
        for ts in self._segmenter.segment(text):
            start, end = int(ts.start), int(ts.end)
            while start < end and text[start].isspace():
                start += 1
            while end > start and text[end - 1].isspace():
                end -= 1
            if start < end:
                spans.append(SentenceSpan(start_char=start, end_char=end))
        return SentenceSegmentationResult(
            spans=spans,
            metadata={"sentence_count": len(spans), "language": self.config.language},
        )

    def is_available(self) -> bool:  # True if pySBD is available
        """Check if pySBD is available."""
        return PYSBD_AVAILABLE

    def prefetch(self) -> None:
        """Eagerly build the segmenter so the first call doesn't pay the build cost."""
        self._load_segmenter()

    def on_disable(self) -> None:
        """Release the segmenter when the operator disables the capability (worker stays alive)."""
        self._release_segmenter()

    def cleanup(self) -> None:
        """Release resources on unload."""
        self._release_segmenter()
