"""Tests for the pySBD segmentation capability — config plumbing + span contract on the abbreviation/title class that motivated the capability (B.5)."""
import pytest

from cjm_capability_primitives.sentence_segmentation import SentenceSegmentationResult
from cjm_capability_pysbd.capability import PySBDConfig, PySBDSegmentationCapability
from cjm_sentence_segmentation_adapter_interface.adapter import (
    SentenceSegmentationToolProtocol)
from cjm_substrate.core.errors import CapabilityInputError


@pytest.fixture
def cap():
    c = PySBDSegmentationCapability()
    c.initialize()
    return c


def test_satisfies_tool_protocol(cap):
    assert isinstance(cap, SentenceSegmentationToolProtocol)


def test_config_defaults_and_schema(cap):
    assert cap.get_current_config() == {"language": "en"}
    schema = cap.get_config_schema()
    assert "language" in schema["properties"]


def test_abbreviation_title_class_does_not_split(cap):
    # The exact false-positive class the v2/v3 token heuristic chased
    # (DEC cc904eee): honorifics, dotted abbreviations, initials.
    text = 'We spoke to Mr. Gorbachev at 3 p.m. yesterday. "It works," he said. The U.S. team agreed.'
    result = cap.segment_text(text)
    sentences = [text[s.start_char:s.end_char] for s in result.spans]
    assert sentences == [
        'We spoke to Mr. Gorbachev at 3 p.m. yesterday.',
        '"It works," he said.',
        'The U.S. team agreed.',
    ]


def test_spans_are_trimmed_ordered_non_overlapping(cap):
    text = "One sentence here\n\nAnother thing.  Third bit!"
    result = cap.segment_text(text)
    assert isinstance(result, SentenceSegmentationResult)
    prev_end = -1
    for s in result.spans:
        assert s.start_char < s.end_char
        assert not text[s.start_char].isspace()
        assert not text[s.end_char - 1].isspace()
        assert s.start_char > prev_end
        prev_end = s.end_char
    assert result.metadata["sentence_count"] == len(result.spans)


def test_empty_and_whitespace_text(cap):
    assert cap.segment_text("").spans == []
    assert cap.segment_text("   \n ").spans == []


def test_non_string_input_is_typed_error(cap):
    with pytest.raises(CapabilityInputError):
        cap.segment_text(42)


def test_language_reconfigure_rebuilds_segmenter(cap):
    cap.segment_text("Hello there. Second.")
    assert cap._segmenter is not None
    cap.reconfigure({"language": "en"}, {"language": "es"})
    assert cap._segmenter is None  # RELOAD_TRIGGER released the built segmenter
    assert cap.get_current_config() == {"language": "es"}
    r = cap.segment_text("Hola. Que tal?")
    assert r.metadata["language"] == "es"
