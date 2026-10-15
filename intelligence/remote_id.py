"""
Remote-ID Candidate Resolver for Speak V2 Conversation Intelligence.

Extracts, validates, and classifies remote access identifiers (AnyDesk, TeamViewer)
while strictly isolating them from case references, ticket numbers, serial numbers,
phone numbers, and currencies.

Enforces the Five Remote-ID Validation Gates:
1. Strict Exclusion: Rejects phone numbers (SA cell/landline), currencies, OTPs, case refs.
2. Software Anchor: Requires explicit remote tool context (AnyDesk, TeamViewer, 'connected to').
3. Parse Hygiene: Rejects spoken word representations ('four one nine...') -> REMOTE_ID_UNPARSEABLE.
4. Target/Site Association: Binds IDs to targets (Till 1, POS 2) and site labels (Site 1, Site 2).
5. Supersession & Ambiguity: Verbal corrections strictly supersede earlier candidates;
   multiple active distinct IDs leave canonical field blank with MULTIPLE_ACTIVE_REMOTE_IDS flag.
"""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from intelligence.models import (
    ActorRole,
    RemoteIdAnchor,
    RemoteIdCandidate,
    RemoteIdStatus,
)


@dataclass
class OtherIdentifier:
    """Non-connection identifier (case reference, serial number, etc.)."""
    kind: str  # CASE_NUMBER, TICKET_REF, SERIAL_NUMBER, POS_ID
    value: str
    turn_index: int
    source_quote: str


@dataclass
class RemoteIdResolutionResult:
    """Complete result of Remote ID extraction, validation, and disambiguation."""
    canonical_remote_id: Optional[str]
    candidates: List[RemoteIdCandidate]
    other_identifiers: List[OtherIdentifier]
    review_required: bool
    review_reasons: List[str]
    remote_id_status: RemoteIdStatus = RemoteIdStatus.ACTIVE
    field_review_flags: Dict[str, str] = field(default_factory=dict)

    @property
    def field_flags(self) -> Dict[str, str]:
        return self.field_review_flags


# --- Exclusion Lexicons ---

PHONE_PREFIXES = [
    "082", "083", "084", "072", "073", "074", "076", "071", "079",
    "0861", "0860", "0800", "011", "021", "031", "012", "041", "051"
]

PHONE_TRIGGERS = [
    "call me", "call the manager", "cell phone", "phone me", "dial",
    "whatsapp", "tel", "mobile", "cell", "telephone", "landline"
]

CURRENCY_CUES = [
    "rand", "rands", "$", "dollar", "dollars", "€", "euro", "euros",
    "tender", "float", "batch variance", "refund", "amount"
]

OTP_CUES = [
    "otp", "pin", "supervisor code", "override", "authorization code",
    "security pin", "manager code", "passcode"
]

CASE_REF_CUES = [
    "ticket", "case number", "case ref", "reference", "ref:", "ref #"
]

REMOTE_SOFTWARE_ANCHORS = [
    (RemoteIdAnchor.ANYDESK, [r"\banydesk\b", r"\bany desk\b"]),
    (RemoteIdAnchor.TEAMVIEWER, [r"\bteamviewer\b", r"\bteam viewer\b"]),
    (RemoteIdAnchor.GENERIC_REMOTE, [
        r"\bremote\s+(?:id|connection|session|access)\b",
        r"\bscreen\s+share\b",
        r"\b(?:my\s+)?id\s+(?:is|:)\b"
    ]),
    (RemoteIdAnchor.POSITIONAL, [
        r"\b(?:connected|connecting|logged in|dialed in|station)\s+(?:now\s+)?(?:on|to|via)?\b",
        r"\bconnect\s+to\s+(?:your\s+)?(?:machine|terminal)\b"
    ])
]

# Spoken digit words
SPOKEN_DIGITS = [
    "zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"
]


def _normalize_id_digits(raw: str) -> str:
    """Standardizes spacing into groups of 3 (or 3-3-4 / 5-4-4)."""
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 9:
        return f"{digits[0:3]} {digits[3:6]} {digits[6:9]}"
    elif len(digits) == 10:
        return f"{digits[0:3]} {digits[3:6]} {digits[6:10]}"
    elif len(digits) == 13:
        return f"{digits[0:5]} {digits[5:9]} {digits[9:13]}"
    return raw.strip()


class RemoteIdResolver:
    """Stateful extractor evaluating and resolving connection ID candidates."""

    def __init__(self):
        self.candidates: List[RemoteIdCandidate] = []
        self.other_identifiers: List[OtherIdentifier] = []
        self.review_reasons: List[str] = []
        self.field_review_flags: Dict[str, str] = {}
        self._candidate_counter = 0

    def _is_excluded(self, text: str, matched_str: str) -> Tuple[bool, Optional[str]]:
        """Gate 1: Verifies candidate is not a phone number, currency, OTP, or case ref."""
        lower = text.lower()
        digits = re.sub(r"\D", "", matched_str)

        # Phone prefix exclusion (e.g. 082, 083, +27...)
        for pfx in PHONE_PREFIXES:
            if digits.startswith(pfx) or f"+27 {pfx[1:]}" in lower or f"+27{pfx[1:]}" in lower:
                return True, "PHONE_PREFIX_EXCLUSION"

        # Surrounding context windows (up to 30 chars before and after match)
        pos = lower.find(matched_str.lower())
        if pos >= 0:
            window_before = lower[max(0, pos - 30):pos]
            window_after = lower[pos + len(matched_str):min(len(lower), pos + len(matched_str) + 30)]
        else:
            window_before = lower
            window_after = ""

        # Phone verbal cue exclusion (using word boundaries to avoid matching 'tell' for 'tel')
        for pt in PHONE_TRIGGERS:
            if re.search(r"\b" + re.escape(pt) + r"\b", window_before) or re.search(r"\b" + re.escape(pt) + r"\b", window_after):
                return True, "PHONE_TRIGGER_EXCLUSION"

        # Currency exclusion
        if re.search(r"\b[rR]\s*$", window_before):
            return True, "CURRENCY_EXCLUSION"

        for c in CURRENCY_CUES:
            if c in ("$", "€"):
                if c in window_before or c in window_after:
                    return True, "CURRENCY_EXCLUSION"
            else:
                if re.search(r"\b" + re.escape(c) + r"\b", window_before) or re.search(r"\b" + re.escape(c) + r"\b", window_after):
                    return True, "CURRENCY_EXCLUSION"

        # OTP / PIN exclusion
        for otp in OTP_CUES:
            if re.search(r"\b" + re.escape(otp) + r"\b", window_before) or re.search(r"\b" + re.escape(otp) + r"\b", window_after):
                return True, "SECURITY_PIN_EXCLUSION"

        # Account number exclusion
        for acc in ["account", "acc", "client number", "customer number"]:
            if re.search(r"\b" + re.escape(acc) + r"\b", window_before):
                return True, "ACCOUNT_NUMBER_EXCLUSION"

        return False, None

    def _detect_anchor(self, text: str) -> RemoteIdAnchor:
        """Gate 2: Determines if a valid remote software anchor exists."""
        lower = text.lower()
        for anchor_type, patterns in REMOTE_SOFTWARE_ANCHORS:
            if any(re.search(pat, lower) for pat in patterns):
                return anchor_type
        return RemoteIdAnchor.NONE

    def _detect_site_and_target(self, text: str) -> Tuple[Optional[str], Optional[str]]:
        """Gate 4: Identifies site and target equipment associations."""
        lower = text.lower()
        site_label: Optional[str] = None
        target_id: Optional[str] = None

        # Site extraction
        if "other site" in lower or "second site" in lower or "site two" in lower:
            site_label = "Site 2"
        elif "site one" in lower or "main site" in lower or "main branch" in lower:
            site_label = "Site 1"

        # Target extraction
        m_till = re.search(r"\b(?:pos|till|terminal)\s*(\d+)\b", lower)
        if m_till:
            target_id = f"target_pos_{m_till.group(1)}"

        return site_label, target_id

    def process_turn(
        self,
        text: str,
        turn_index: int,
        speaker: ActorRole = ActorRole.UNKNOWN
    ) -> None:
        """Processes a dialogue turn for remote ID candidates and other identifiers."""
        lower = text.lower()

        # 1. Non-connection Identifiers (Case references, Serial numbers)
        # Case / Ticket references
        for m in re.finditer(r"\b(?:CAS|REF|TICKET|CASE)[-:\s#]*([A-Z0-9]{5,15})\b", text, re.IGNORECASE):
            self.other_identifiers.append(OtherIdentifier(
                kind="CASE_REFERENCE",
                value=m.group(0).strip(),
                turn_index=turn_index,
                source_quote=text
            ))

        # Serial numbers
        for m in re.finditer(r"\b(?:SN|S/N|SERIAL)[-:\s#]*([A-Z0-9]{5,20})\b", text, re.IGNORECASE):
            self.other_identifiers.append(OtherIdentifier(
                kind="SERIAL_NUMBER",
                value=m.group(0).strip(),
                turn_index=turn_index,
                source_quote=text
            ))

        # 2. Gate 3: Check for Spoken Words ("AnyDesk is four one nine...")
        has_anchor_phrase = any(re.search(p, lower) for _, patterns in REMOTE_SOFTWARE_ANCHORS for p in patterns)
        if has_anchor_phrase:
            spoken_count = sum(1 for w in SPOKEN_DIGITS if re.search(r"\b" + w + r"\b", lower))
            if spoken_count >= 4:
                # Client uttered digits as spoken words!
                # Do NOT assemble digits; record unparseable candidate
                self._candidate_counter += 1
                cand = RemoteIdCandidate(
                    candidate_id=f"cand_{self._candidate_counter}",
                    value=None,
                    turn_index=turn_index,
                    clause_index=0,
                    speaker=speaker,
                    anchor=RemoteIdAnchor.ANYDESK if "anydesk" in lower else RemoteIdAnchor.GENERIC_REMOTE,
                    status=RemoteIdStatus.REJECTED,
                    rejected_reasons=["REMOTE_ID_UNPARSEABLE"]
                )
                self.candidates.append(cand)
                self.field_review_flags["Remote_Connection_ID__c"] = "REMOTE_ID_UNPARSEABLE"
                if "REMOTE_ID_UNPARSEABLE" not in self.review_reasons:
                    self.review_reasons.append("REMOTE_ID_UNPARSEABLE")
                return

        # 3. Candidate Remote ID Numerical Patterns
        # Matches 9-digit (3-3-3), 10-digit (3-3-4 / 4-3-3), or multi-block station IDs (e.g. 20288 2622 06609)
        num_pattern = re.compile(
            r"\b(?:\d{3,5}[-\s]?){2,4}\b"
        )

        matches = list(num_pattern.finditer(text))
        if not matches:
            return

        anchor = self._detect_anchor(text)
        site_label, target_id = self._detect_site_and_target(text)
        is_correction = any(k in lower for k in [
            "not ", "sorry", "misread", "correct anydesk", "correct id", "use ", "instead of"
        ])

        for match in matches:
            raw_match = match.group(0).strip()
            digits_only = re.sub(r"\D", "", raw_match)
            if len(digits_only) < 6 or len(digits_only) > 16:
                continue
            
            # Gate 1: Exclusion Filters
            excluded, reason = self._is_excluded(text, raw_match)
            if excluded:
                continue

            # Gate 2: Anchor Validation
            cand_anchor = anchor
            if cand_anchor == RemoteIdAnchor.NONE:
                if is_correction and any(c.status == RemoteIdStatus.ACTIVE for c in self.candidates):
                    # Inherit anchor from the candidate being corrected
                    cand_anchor = next((c.anchor for c in reversed(self.candidates) if c.status == RemoteIdStatus.ACTIVE), RemoteIdAnchor.GENERIC_REMOTE)
                else:
                    # Bare number without remote tool context is rejected
                    continue

            normalized_val = _normalize_id_digits(raw_match)

            # Check if this exact ID was already recorded
            existing_cand = next(
                (c for c in self.candidates if c.value == normalized_val),
                None
            )

            if existing_cand:
                # Repeated mention of same ID
                if speaker == ActorRole.CONSULTANT and "connected" in lower:
                    existing_cand.consultant_connected = True
                continue

            # Create new candidate
            self._candidate_counter += 1
            cand_id = f"cand_{self._candidate_counter}"
            
            cand = RemoteIdCandidate(
                candidate_id=cand_id,
                value=normalized_val,
                turn_index=turn_index,
                clause_index=0,
                speaker=speaker,
                anchor=cand_anchor,
                site_label=site_label,
                target_id=target_id,
                status=RemoteIdStatus.ACTIVE,
                consultant_connected=(speaker == ActorRole.CONSULTANT and "connected" in lower)
            )

            # Gate 5: Verbal Correction Supersession
            if is_correction:
                # Mark previous active candidates as SUPERSEDED
                for prev in self.candidates:
                    if prev.status == RemoteIdStatus.ACTIVE:
                        prev.status = RemoteIdStatus.SUPERSEDED
                        prev.superseded_by = cand_id

            self.candidates.append(cand)

    def resolve(self) -> RemoteIdResolutionResult:
        """Determines the safe canonical remote ID according to validation gates."""
        active_candidates = [
            c for c in self.candidates
            if c.status == RemoteIdStatus.ACTIVE and c.value is not None
        ]

        # Case 1: Exactly one active candidate
        if len(active_candidates) == 1:
            return RemoteIdResolutionResult(
                canonical_remote_id=active_candidates[0].value,
                candidates=self.candidates,
                other_identifiers=self.other_identifiers,
                review_required=len(self.review_reasons) > 0,
                review_reasons=self.review_reasons,
                remote_id_status=RemoteIdStatus.ACTIVE,
                field_review_flags=self.field_review_flags
            )

        # Case 2: Zero active candidates
        if len(active_candidates) == 0:
            zero_status = RemoteIdStatus.REJECTED if any(c.status == RemoteIdStatus.REJECTED for c in self.candidates) else RemoteIdStatus.REJECTED
            return RemoteIdResolutionResult(
                canonical_remote_id=None,
                candidates=self.candidates,
                other_identifiers=self.other_identifiers,
                review_required=len(self.review_reasons) > 0,
                review_reasons=self.review_reasons,
                remote_id_status=zero_status,
                field_review_flags=self.field_review_flags
            )

        # Case 3: Multiple active candidates without explicit correction!
        # Ambiguous remote connection target must NEVER pick the first ID arbitrarily!
        # Leaves canonical_remote_id = None, sets remote_id_status = AMBIGUOUS.
        if "MULTIPLE_ACTIVE_REMOTE_IDS" not in self.review_reasons:
            self.review_reasons.append("MULTIPLE_ACTIVE_REMOTE_IDS")
        self.field_review_flags["Remote_Connection_ID__c"] = "AMBIGUOUS"

        for c in active_candidates:
            c.status = RemoteIdStatus.AMBIGUOUS

        return RemoteIdResolutionResult(
            canonical_remote_id=None,  # Leave field blank for safety!
            candidates=self.candidates,
            other_identifiers=self.other_identifiers,
            review_required=True,
            review_reasons=self.review_reasons,
            remote_id_status=RemoteIdStatus.AMBIGUOUS,
            field_review_flags=self.field_review_flags
        )


def resolve_remote_ids(
    dialogue: List[Tuple[str, str]]
) -> RemoteIdResolutionResult:
    """
    Convenience function resolving remote IDs across a list of (speaker_str, text) tuples.
    """
    resolver = RemoteIdResolver()
    for idx, (spk_str, text) in enumerate(dialogue):
        spk = ActorRole.CONSULTANT if spk_str.upper() == "CONSULTANT" else ActorRole.CLIENT
        resolver.process_turn(text, turn_index=idx, speaker=spk)
    return resolver.resolve()
