from typing import List, Optional, Tuple

# Dialogue script parser — the single source of truth used by the pipeline
# orchestrator to render multi-voice scenes.
#
# Expected format per line: "Speaker: text" (the first colon separates the
# speaker from the utterance). A line with no colon — or an empty speaker — is
# treated as narration (speaker = None). Blank lines are skipped.


def parse_dialogue(script: str) -> List[Tuple[Optional[str], str]]:
    """Parse a dialogue script into ordered ``(speaker, utterance)`` pairs.

    Args:
        script: Multiline string. Each line is ``Speaker: text``.

    Returns:
        List of ``(speaker, utterance)`` tuples preserving the original order.
        ``speaker`` is ``None`` for narration (no colon or empty speaker), in
        which case the caller assigns a default/narrator voice.
    """
    parsed: List[Tuple[Optional[str], str]] = []
    for line in script.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(":", 1)
        if len(parts) == 2 and parts[0].strip():
            parsed.append((parts[0].strip(), parts[1].strip()))
        else:
            # No colon, or an empty speaker -> narration; keep the line as-is.
            parsed.append((None, line))
    return parsed
