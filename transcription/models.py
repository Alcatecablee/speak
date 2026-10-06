from dataclasses import dataclass, asdict
from typing import Optional, List
from datetime import datetime, timedelta

@dataclass
class TranscriptSegment:
    start_seconds: float
    end_seconds: float
    text: str
    speaker: str  # 'CONSULTANT' or 'CLIENT'
    confidence: Optional[float] = None

    def to_dict(self):
        return asdict(self)

@dataclass
class MergedTurn:
    speaker: str  # 'CONSULTANT' or 'CLIENT'
    start_seconds: float
    end_seconds: float
    timestamp_str: str  # e.g. "10:31:04" or "[+00:12]"
    text: str

    def to_dict(self):
        return asdict(self)
    
    def formatted_line(self) -> str:
        return f"[{self.timestamp_str}] {self.speaker}: {self.text}"
