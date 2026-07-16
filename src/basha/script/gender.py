"""Best-effort gender inference from a speaker's first name.

Used by the audio-drama pipeline to pick a gender-appropriate voice for each
character. This is intentionally a *heuristic*: when a name is unknown or
ambiguous it returns ``None`` and the caller falls back to its normal
round-robin voice assignment (so a character always still gets a voice).

Resolution order:
    1. Curated first-name dictionary (free, offline, covers common Indian and
       European names — enough for typical scripts).
    2. Optional ``gender-guesser`` package, used only if installed (broader
       Western coverage). Its absence is handled gracefully.
    3. ``None`` -> caller decides (round-robin).
"""
import re
from typing import Optional, Set, Tuple

# Lowercased first names with a strong majority gender. Deliberately excludes
# clearly unisex names (e.g. "Kiran", "Andrea") so we never guess wrongly —
# those fall through to None and the round-robin handles them.
_MALE: Set[str] = {
    # Indian
    "ravi", "raj", "raju", "ramu", "arjun", "krishna", "vijay", "anil",
    "suresh", "ramesh", "rahul", "rohit", "amit", "sanjay", "vikram",
    "karthik", "akash", "aakash", "aditya", "aryan", "gopal", "hari",
    "manoj", "naveen", "prakash", "pradeep", "surya", "varun", "vishal",
    "abhishek", "ajay", "deepak", "harish", "mahesh", "srinivas", "venkat",
    "bharath", "mohan", "nikhil", "pranav", "shankar", "tarun", "uday",
    "yash", "ganesh", "kumar", "arun", "vivek", "sandeep", "rakesh", "ashok",
    "balu", "naga", "ravindra", "gopi", "sai",
    # European / Western
    "john", "james", "michael", "david", "robert", "william", "richard",
    "thomas", "charles", "daniel", "mark", "paul", "peter", "george",
    "henry", "jack", "adam", "ben", "chris", "eric", "frank", "greg",
    "harry", "ivan", "kevin", "leo", "max", "nick", "oscar", "ryan", "sam",
    "tom", "victor", "carlos", "diego", "hans", "pierre", "luca", "marco",
    "pedro", "jose", "juan", "antonio", "luis", "miguel",
}
_FEMALE: Set[str] = {
    # Indian
    "meena", "priya", "lakshmi", "sita", "gita", "geeta", "radha", "deepa",
    "divya", "anjali", "pooja", "kavya", "sneha", "swati", "aishwarya",
    "ananya", "bhavana", "chitra", "deepika", "gayatri", "indira", "jyothi",
    "kalpana", "lata", "madhuri", "nandini", "padma", "rani", "rekha",
    "shreya", "sunita", "usha", "vidya", "asha", "devi", "kamala", "manju",
    "nisha", "pallavi", "sangeeta", "shanti", "tara", "vani", "roja",
    "saroja", "sridevi", "bhanu",
    # European / Western
    "mary", "maria", "emma", "olivia", "sophia", "sofia", "isabella", "anna",
    "elena", "laura", "sarah", "sara", "julia", "clara", "emily", "grace",
    "hannah", "alice", "rose", "lily", "eva", "nina", "lucy", "kate", "jane",
    "diana", "lucia", "carmen", "marie", "claire", "chloe", "sophie",
    "amelia", "mia", "ella",
}

# Optional broader fallback. Pure-python, no data download; used only when the
# package is present. We import lazily and never fail if it is missing.
try:  # pragma: no cover - optional dependency
    from gender_guesser.detector import Detector as _Detector

    _detector = _Detector(case_sensitive=False)
except Exception:  # pragma: no cover - optional dependency
    _detector = None


def _normalize(name: Optional[str]) -> str:
    """Reduce a speaker label to its first name token: letters only, lowercased."""
    if not name or not name.strip():
        return ""
    first_token = name.strip().split()[0]
    return "".join(ch for ch in first_token.lower() if ch.isalpha())


def guess_gender(name: Optional[str]) -> Optional[str]:
    """Return ``"male"`` / ``"female"`` for *name*, or ``None`` if unknown.

    ``None`` is returned for ambiguous names and non-name speakers (e.g.
    ``"Narrator"``, ``"Guard"``), letting the caller fall back to round-robin.
    """
    key = _normalize(name)
    if not key:
        return None
    if key in _MALE:
        return "male"
    if key in _FEMALE:
        return "female"
    if _detector is not None:
        guess = _detector.get_gender(key)
        if guess in ("male", "mostly_male"):
            return "male"
        if guess in ("female", "mostly_female"):
            return "female"
    return None


# Matches an optional trailing gender tag, e.g. "Ravi (male)" / "Meena (f)".
_GENDER_TAG = re.compile(r"^\s*(.*?)\s*\(\s*(m|male|f|female)\s*\)\s*$", re.IGNORECASE)


def split_gender_tag(label: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """Split an optional trailing "(male)"/"(female)" tag off a speaker label.

    ``"Ravi (male)"`` -> ``("Ravi", "male")``; ``"Meena"`` -> ``("Meena", None)``;
    ``None`` -> ``(None, None)``. Single letters ``m``/``f`` are accepted too. A
    parenthetical that is not a gender (e.g. ``"Ravi (the king)"``) is left as-is.
    """
    if label is None:
        return None, None
    match = _GENDER_TAG.match(label)
    if not match:
        return label.strip(), None
    name = match.group(1).strip()
    tag = match.group(2).lower()
    return name, ("male" if tag in ("m", "male") else "female")
