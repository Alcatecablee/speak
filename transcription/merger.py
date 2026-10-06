from typing import List, Optional
from datetime import datetime, timedelta
from transcription.models import TranscriptSegment, MergedTurn

def format_timestamp(seconds: float, start_time: Optional[datetime] = None) -> str:
    """Format seconds into HH:MM:SS (wall-clock if start_time given, else relative HH:MM:SS)."""
    if start_time:
        actual_time = start_time + timedelta(seconds=seconds)
        return actual_time.strftime("%H:%M:%S")
    else:
        td = timedelta(seconds=int(seconds))
        total_seconds = int(td.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        secs = total_seconds % 60
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

def merge_speaker_streams(
    consultant_segments: List[TranscriptSegment],
    client_segments: List[TranscriptSegment],
    call_start_time: Optional[datetime] = None,
    merge_adjacent_gap: float = 1.0
) -> List[MergedTurn]:
    """
    Merge separate consultant and client transcript segments chronologically.
    
    1. Tags each segment with explicit speaker role ('CONSULTANT' vs 'CLIENT').
    2. Combines all segments and sorts them by start_seconds.
    3. Coalesces adjacent segments from the SAME speaker if the gap between them <= merge_adjacent_gap.
    4. Computes formatted timestamps for every dialogue turn.
    """
    all_segments: List[TranscriptSegment] = []
    
    for seg in consultant_segments:
        seg.speaker = "CONSULTANT"
        all_segments.append(seg)
        
    for seg in client_segments:
        seg.speaker = "CLIENT"
        all_segments.append(seg)
        
    # Sort strictly by start time
    all_segments.sort(key=lambda s: s.start_seconds)
    
    if not all_segments:
        return []
    
    merged_turns: List[MergedTurn] = []
    
    current_speaker = all_segments[0].speaker
    current_start = all_segments[0].start_seconds
    current_end = all_segments[0].end_seconds
    current_texts = [all_segments[0].text.strip()]
    
    for seg in all_segments[1:]:
        text = seg.text.strip()
        if not text:
            continue
            
        # Check if same speaker and close in time
        if seg.speaker == current_speaker and (seg.start_seconds - current_end) <= merge_adjacent_gap:
            current_texts.append(text)
            current_end = max(current_end, seg.end_seconds)
        else:
            # Emit completed turn
            combined_text = " ".join(current_texts)
            timestamp_str = format_timestamp(current_start, call_start_time)
            merged_turns.append(MergedTurn(
                speaker=current_speaker,
                start_seconds=current_start,
                end_seconds=current_end,
                timestamp_str=timestamp_str,
                text=combined_text
            ))
            
            # Start new turn
            current_speaker = seg.speaker
            current_start = seg.start_seconds
            current_end = seg.end_seconds
            current_texts = [text]
            
    # Emit final turn
    if current_texts:
        combined_text = " ".join(current_texts)
        timestamp_str = format_timestamp(current_start, call_start_time)
        merged_turns.append(MergedTurn(
            speaker=current_speaker,
            start_seconds=current_start,
            end_seconds=current_end,
            timestamp_str=timestamp_str,
            text=combined_text
        ))
        
    return merged_turns

def render_transcript_text(turns: List[MergedTurn]) -> str:
    """Render a clean text block of the merged speaker turns."""
    lines = [turn.formatted_line() for turn in turns]
    return "\n".join(lines)
