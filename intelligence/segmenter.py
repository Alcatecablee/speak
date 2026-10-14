"""
Discourse-Aware Clause Segmenter for Speak V2 Conversation Intelligence.

Decomposes raw turn utterances into fine-grained linguistic clauses,
isolating contrastive discourse markers, coordinate conjunctions, correlatives
("not only ... but also ..."), and temporal anchors while tracking exact character
spans back to the original transcript turn.
"""

import re
from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass
class SegmentedClause:
    """A single segmented clause with character spans and discourse attributes."""
    turn_index: int
    clause_index: int
    text: str
    span: Tuple[int, int]  # (start_char, end_char) within turn text
    discourse_marker: Optional[str] = None
    is_contrastive: bool = False
    temporal_marker: Optional[str] = None


# Contrastive discourse markers that separate independent propositions
CONTRASTIVE_MARKERS = [
    "but", "however", "although", "whereas", "while", "though", "yet",
    "except that", "except", "on the other hand", "despite"
]

# Temporal indicators that establish chronological scope
TEMPORAL_KEYWORDS = [
    "earlier", "previously", "before", "initially", "at first", "yesterday",
    "now", "currently", "at the moment", "right now", "still",
    "tomorrow", "later", "next week", "sometime"
]


def _adjust_span_for_whitespace(raw_text: str, start: int, end: int) -> Tuple[str, Tuple[int, int]]:
    """Trims leading/trailing whitespace from text while adjusting start and end offsets."""
    chunk = raw_text[start:end]
    l_strip = len(chunk) - len(chunk.lstrip())
    r_strip = len(chunk) - len(chunk.rstrip())
    new_start = start + l_strip
    new_end = end - r_strip
    return raw_text[new_start:new_end], (new_start, new_end)


def segment_turn(text: str, turn_index: int = 0) -> List[SegmentedClause]:
    """
    Segments a dialogue turn into discrete semantic clauses with exact character spans.
    
    Handles:
    - Correlative constructions: 'not only ... but (also) ...'
    - Semicolons and sentence terminators: ';', '.', '!', '?', newline
    - Contrastive conjunctions: 'but', 'however', 'although', 'whereas', etc.
    - Coordinate clause conjunctions: 'and', 'as well as'
    - Temporal markers: 'earlier', 'now', 'tomorrow', etc.
    """
    if not text or not text.strip():
        return []

    # 1. First, check for correlative 'not only ... but (also) ...'
    correlative_match = re.search(
        r"\bnot\s+only\b(?P<first>.+?)\bbut(?:\s+also)?\b(?P<second>.+?)(?:[.;!?]|$)",
        text,
        re.IGNORECASE
    )
    if correlative_match:
        clauses: List[SegmentedClause] = []
        c_idx = 0
        
        # Leading text before correlative if any
        prefix_end = correlative_match.start()
        if prefix_end > 0 and text[:prefix_end].strip():
            p_text, p_span = _adjust_span_for_whitespace(text, 0, prefix_end)
            if p_text:
                clauses.append(SegmentedClause(
                    turn_index=turn_index,
                    clause_index=c_idx,
                    text=p_text,
                    span=p_span,
                    discourse_marker=None,
                    is_contrastive=False
                ))
                c_idx += 1

        # First branch: 'not only ...'
        g1_start = correlative_match.start()
        # Find where 'but' starts
        but_pos = correlative_match.start() + correlative_match.group(0).lower().find("but")
        c1_text, c1_span = _adjust_span_for_whitespace(text, g1_start, but_pos)
        clauses.append(SegmentedClause(
            turn_index=turn_index,
            clause_index=c_idx,
            text=c1_text,
            span=c1_span,
            discourse_marker="not only",
            is_contrastive=False
        ))
        c_idx += 1

        # Second branch: 'but (also) ...'
        c2_end = correlative_match.end()
        c2_text, c2_span = _adjust_span_for_whitespace(text, but_pos, c2_end)
        clauses.append(SegmentedClause(
            turn_index=turn_index,
            clause_index=c_idx,
            text=c2_text,
            span=c2_span,
            discourse_marker="but also",
            is_contrastive=False  # Correlative 'not only... but also' is cumulative, not contrastive
        ))
        c_idx += 1

        # Trailing text after correlative if any
        if c2_end < len(text) and text[c2_end:].strip():
            rest = text[c2_end:]
            sub_clauses = segment_turn(rest, turn_index=turn_index)
            for sc in sub_clauses:
                adj_span = (sc.span[0] + c2_end, sc.span[1] + c2_end)
                clauses.append(SegmentedClause(
                    turn_index=turn_index,
                    clause_index=c_idx,
                    text=sc.text,
                    span=adj_span,
                    discourse_marker=sc.discourse_marker,
                    is_contrastive=sc.is_contrastive,
                    temporal_marker=sc.temporal_marker
                ))
                c_idx += 1

        return clauses

    # 2. General segmentation pattern
    # Split on sentence boundaries and discourse markers
    # We construct a regex pattern that matches delimiter boundaries while capturing positions
    # Delimiters:
    # - [.;!?\n]+
    # - ,?\s*\b(but|however|although|whereas|while|though|yet|except that|except)\b
    # - ,?\s*\band\b(?=\s+[A-Za-z0-9_]+\s+(?:is|are|was|were|has|have|does|did|works|fails|failed|offline|broken|sorted))
    
    # Punctuation terminators and conjunctions
    split_pattern = re.compile(
        r"(?:[.;!?\n]+|"
        r",\s*(?:but|however|although|whereas|while|though|yet|except that|except|on the other hand)\b|"
        r"\s+\b(?:but|however|although|whereas|though|yet)\b|"
        r",\s*and\b|"
        r"\s+\band\b(?=\s+(?:(?:the\s+)?[A-Za-z0-9_]+\s+(?:is|are|was|were|has|have|does|did|works|fails|failed|offline|broken|sorted|rebooted|swapped)|(?:pinged|tested|checked|rebooted|restarted|swapped|replaced)\b)))",
        re.IGNORECASE
    )

    raw_segments: List[Tuple[int, int, Optional[str], bool, bool]] = []  # (start, end, marker_name, is_contrast, is_delimiter)
    last_pos = 0

    for match in split_pattern.finditer(text):
        m_start = match.start()
        m_end = match.end()
        delim = match.group(0).strip().lower()

        if m_start > last_pos:
            raw_segments.append((last_pos, m_start, None, False, False))

        is_contrast = any(cm in delim for cm in CONTRASTIVE_MARKERS)
        marker_name = next((cm for cm in CONTRASTIVE_MARKERS if cm in delim), None)
        if not marker_name and "and" in delim:
            marker_name = "and"
        elif not marker_name and any(p in delim for p in [";", ".", "!", "?", "\n"]):
            marker_name = delim

        raw_segments.append((m_start, m_end, marker_name, is_contrast, True))
        last_pos = m_end

    if last_pos < len(text):
        raw_segments.append((last_pos, len(text), None, False, False))

    # Assemble into clauses
    clauses = []
    clause_idx = 0
    curr_start: Optional[int] = None
    curr_marker: Optional[str] = None
    curr_is_contrast = False

    for start, end, marker, is_contrast, is_delim in raw_segments:
        chunk = text[start:end]
        if is_delim:
            # This is a delimiter/marker
            if curr_start is not None:
                # Flush existing text
                t, sp = _adjust_span_for_whitespace(text, curr_start, start)
                if t:
                    temporal = next((tm for tm in TEMPORAL_KEYWORDS if re.search(r"\b" + tm + r"\b", t, re.IGNORECASE)), None)
                    clauses.append(SegmentedClause(
                        turn_index=turn_index,
                        clause_index=clause_idx,
                        text=t,
                        span=sp,
                        discourse_marker=curr_marker,
                        is_contrastive=curr_is_contrast,
                        temporal_marker=temporal
                    ))
                    clause_idx += 1
                curr_start = None

            curr_marker = marker
            curr_is_contrast = is_contrast
            continue

        if not chunk.strip():
            continue

        if curr_start is None:
            curr_start = start

    if curr_start is not None and curr_start < len(text):
        t, sp = _adjust_span_for_whitespace(text, curr_start, len(text))
        if t:
            temporal = next((tm for tm in TEMPORAL_KEYWORDS if re.search(r"\b" + tm + r"\b", t, re.IGNORECASE)), None)
            clauses.append(SegmentedClause(
                turn_index=turn_index,
                clause_index=clause_idx,
                text=t,
                span=sp,
                discourse_marker=curr_marker,
                is_contrastive=curr_is_contrast,
                temporal_marker=temporal
            ))

    # If segmentation produced nothing (e.g. pure symbols), fall back to whole string if non-empty
    if not clauses and text.strip():
        t, sp = _adjust_span_for_whitespace(text, 0, len(text))
        temporal = next((tm for tm in TEMPORAL_KEYWORDS if re.search(r"\b" + tm + r"\b", t, re.IGNORECASE)), None)
        clauses.append(SegmentedClause(
            turn_index=turn_index,
            clause_index=0,
            text=t,
            span=sp,
            discourse_marker=None,
            is_contrastive=False,
            temporal_marker=temporal
        ))

    return clauses
