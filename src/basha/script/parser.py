import re
from typing import Dict, List, Tuple

# Simple script parser for dialogue lines.
# Expected format per line: "Speaker: text" (colon separates speaker and utterance).
# Empty lines are ignored.

def parse_script(script: str, voice_mapping: Dict[str, str] = None) -> List[Tuple[str, str]]:
    """Parse a dialogue script into a list of (text, voice_id) tuples.

    Args:
        script: Multiline string containing the script.
        voice_mapping: Optional mapping from speaker name to Edge‑TTS voice ID.
                       If a speaker is not present in the mapping, ``None`` is returned
                       for that line, meaning the default backend voice will be used.
    Returns:
        List of (utterance_text, voice_id) tuples preserving the original order.
    """
    if voice_mapping is None:
        voice_mapping = {}
    result: List[Tuple[str, str]] = []
    for line in script.splitlines():
        line = line.strip()
        if not line:
            continue
        # Split on the first colon
        parts = line.split(":", 1)
        if len(parts) != 2:
            # If no colon, treat the entire line as narration with default voice
            speaker = None
            utterance = line
        else:
            speaker, utterance = parts[0].strip(), parts[1].strip()
        voice_id = voice_mapping.get(speaker) if speaker else None
        result.append((utterance, voice_id))
    return result
