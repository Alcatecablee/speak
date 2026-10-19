"""
Entity normalization engine for Speak V2 AI Conversation Intelligence.
Provides controlled, explicit normalization while preserving raw STT provenance and confidence.
Never silently replaces raw transcript text.
"""

import re
from typing import Dict, List, Optional, Tuple
from intelligence.models import NormalizedEntity, NormalizationMethod


# Controlled domain dictionary
DOMAIN_CATALOG: Dict[str, Dict[str, str]] = {
    # Product / Recipe Items
    "cheesecake": {"normalized": "Cheesecake Recipe / Batch", "category": "PRODUCT"},
    "bata nadpuray": {"normalized": "Butternut Puree", "category": "PRODUCT", "method": "PHONETIC_HEURISTIC", "confidence": "0.75"},
    "bata nadpurai": {"normalized": "Butternut Puree", "category": "PRODUCT", "method": "PHONETIC_HEURISTIC", "confidence": "0.75"},
    "batanadpuray": {"normalized": "Butternut Puree", "category": "PRODUCT", "method": "PHONETIC_HEURISTIC", "confidence": "0.75"},
    "butternut": {"normalized": "Butternut Puree", "category": "PRODUCT"},
    "purée": {"normalized": "Puree Production Item", "category": "PRODUCT"},
    "puree": {"normalized": "Puree Production Item", "category": "PRODUCT"},
    
    # Systems & Modules
    "production": {"normalized": "Production Module", "category": "SYSTEM_MODULE"},
    "unit of measure": {"normalized": "Unit of Measure Configuration", "category": "SYSTEM_SETTING"},
    "variance": {"normalized": "Stock Variance / Recipe Balancing", "category": "SYSTEM_FUNCTION"},
    "anyshop": {"normalized": "AnyShop POS", "category": "SYSTEM_MODULE"},
    "microsip": {"normalized": "MicroSIP Softphone", "category": "TELEPHONY"},
    "salesforce": {"normalized": "Salesforce CRM", "category": "CRM_SYSTEM"},
    "license": {"normalized": "Software License Certificate", "category": "SYSTEM_MODULE"},
    "grv": {"normalized": "Goods Received Voucher / GRV", "category": "INVENTORY"},
    "cashup": {"normalized": "Cashup Balancing", "category": "SYSTEM_FUNCTION"},
    "adumo": {"normalized": "Adumo Payment Driver", "category": "PAYMENT_INTEGRATION"},
    "sql": {"normalized": "SQL Database Engine", "category": "DATABASE"},
    "backup": {"normalized": "Database Backup", "category": "SYSTEM_FUNCTION"},

    # Hardware & Peripherals
    "printer": {"normalized": "Network / Receipt Printer", "category": "HARDWARE"},
    "epson": {"normalized": "Epson Printer", "category": "HARDWARE"},
    "scanner": {"normalized": "Barcode Scanner", "category": "HARDWARE"},
    "terminal": {"normalized": "POS Terminal", "category": "HARDWARE"},
    "till": {"normalized": "POS Till / Cash Drawer", "category": "HARDWARE"},
    "kingpos": {"normalized": "Kingpos Application", "category": "SYSTEM_MODULE"},
    "king pos": {"normalized": "Kingpos Application", "category": "SYSTEM_MODULE", "method": "PHONETIC_HEURISTIC", "confidence": "0.85"},
    "mc1": {"normalized": "Main Controller 1 (MC1)", "category": "HARDWARE"},
    "mc2": {"normalized": "Main Controller 2 (MC2)", "category": "HARDWARE"},
    "ped": {"normalized": "Adumo PED / Card Terminal", "category": "HARDWARE"},
    "pax": {"normalized": "PAX Payment Terminal", "category": "HARDWARE"},
    "till roll": {"normalized": "Thermal Till Roll Consumable", "category": "CONSUMABLE"},
    "till rolls": {"normalized": "Thermal Till Roll Consumable", "category": "CONSUMABLE"},
    "polokwane": {"normalized": "Polokwane Regional Branch", "category": "LOCATION"}
}


class EntityNormalizer:
    """Normalizes terms while strictly tracking provenance, confidence, and raw text."""

    def __init__(self, catalog: Optional[Dict[str, Dict[str, str]]] = None):
        self.catalog = catalog or DOMAIN_CATALOG

    def normalize_term(
        self,
        raw_text: str,
        turn_index: Optional[int] = None,
        timestamp: Optional[str] = None,
        source_quote: str = ""
    ) -> NormalizedEntity:
        """
        Normalizes a raw text string against the domain catalog.
        If no confident match is found, returns an UNNORMALIZED entity retaining raw text.
        """
        clean_raw = raw_text.strip()
        lower = clean_raw.lower()

        # 1. Exact catalog match
        if lower in self.catalog:
            entry = self.catalog[lower]
            method = NormalizationMethod(entry.get("method", NormalizationMethod.DICTIONARY_MATCH.value))
            conf = float(entry.get("confidence", 0.95))
            return NormalizedEntity(
                raw_text=clean_raw,
                normalized_value=entry["normalized"],
                category=entry["category"],
                normalization_method=method,
                confidence=conf,
                turn_index=turn_index,
                timestamp=timestamp,
                source_quote=source_quote
            )

        # 2. Check substrings in catalog
        for key, entry in self.catalog.items():
            if key in lower:
                method = NormalizationMethod(entry.get("method", NormalizationMethod.EXACT_MATCH.value))
                conf = float(entry.get("confidence", 0.90))
                return NormalizedEntity(
                    raw_text=clean_raw,
                    normalized_value=entry["normalized"],
                    category=entry["category"],
                    normalization_method=method,
                    confidence=conf,
                    turn_index=turn_index,
                    timestamp=timestamp,
                    source_quote=source_quote
                )

        # 3. Fallback: Unnormalized entity retaining verbatim transcript text
        return NormalizedEntity(
            raw_text=clean_raw,
            normalized_value=clean_raw,
            category="UNCLASSIFIED",
            normalization_method=NormalizationMethod.UNNORMALIZED,
            confidence=0.50,
            turn_index=turn_index,
            timestamp=timestamp,
            source_quote=source_quote
        )

    def extract_and_normalize_all(
        self,
        turns: List[Dict[str, str]]
    ) -> List[NormalizedEntity]:
        """
        Scans all dialogue turns and returns normalized entities with full source tracking.
        """
        results: List[NormalizedEntity] = []
        seen_normalized = set()

        for idx, turn in enumerate(turns):
            text = turn.get("text", "")
            lower_text = text.lower()
            ts = turn.get("timestamp_str")

            for key in self.catalog.keys():
                if key in lower_text:
                    # Find raw matching snippet
                    match = re.search(re.escape(key), text, re.IGNORECASE)
                    raw_snippet = match.group(0) if match else key
                    
                    norm_ent = self.normalize_term(
                        raw_text=raw_snippet,
                        turn_index=idx,
                        timestamp=ts,
                        source_quote=text[:120]
                    )

                    combo_key = (norm_ent.normalized_value, norm_ent.category)
                    if combo_key not in seen_normalized:
                        seen_normalized.add(combo_key)
                        results.append(norm_ent)

        return results
