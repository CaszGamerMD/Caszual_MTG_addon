"""Conservative sequence grammar for independent Oracle instructions.

Split *only* known instruction separators, not the "and" in card types,
colors, targeting phrases, or conditional sentences. The caller supplies
the existing atomic effect parser; all parts must compile or nothing does.
No interpretation of unknown effects, no skipping extra text.
"""
from __future__ import annotations
import re

# Supported standalone instructions after a connector. Never break e.g.
# 'white and green', 'sacrifice and return', 'an Elf and a Goblin'.
_START = r"(?:you\s+)?(?:gain|lose|draw|create|scry|surveil|mill|put)\b"
_SEP = re.compile(
    r"(?:,\s*then\s+|\.\s*Then\s+|\s+and\s+)(?=" + _START + r")",
    re.IGNORECASE
)
# A short approved vocabulary of target-free and target-self instructions.
# Any separate spell targets, sacrifice costs, timing windows and 'if' checks
# require a different interpreter with explicit legality semantics.
_SAFE = frozenset((
    "draw_cards", "gain_life", "lose_life", "self_counter",
    "create_tokens", "create_treasures", "scry", "surveil",
    "mill_cards",
))


def parse_sequence(text: str, atom):
    """Return a tuple of fully parsed atomic Effect objects, or None."""
    if not text.endswith("."):
        return None
    pieces = _SEP.split(text[:-1])
    if len(pieces)<2 or len(pieces)>8:
        return None
    compiled=[]
    subject_is_you=False
    for piece in pieces:
        chunk=piece.strip()
        if not chunk:
            return None
        # A coordinated verb shares its explicit subject: "You draw two cards
        # and lose 2 life." The second atom still belongs to the controller.
        # Never infer a subject across an unsupported or target-dependent verb.
        if re.match(r'^you\s+',chunk,re.IGNORECASE):
            subject_is_you=True
        elif subject_is_you and re.match(r'^(draw|gain|lose)\b',chunk,re.IGNORECASE):
            chunk='you '+chunk
        else:
            subject_is_you=False
        chunk=chunk[0].lower()+chunk[1:]+"."
        parsed=atom(chunk)
        if parsed is None or parsed.operation not in _SAFE:
            return None
        if parsed.operation=="lose_life" and parsed.recipient not in (
                "self", "each opponent"):
            return None
        if parsed.operation=="self_counter" and parsed.amount<=0:
            return None
        if parsed.steps or parsed.optional or parsed.controller_loss:
            return None
        compiled.append(parsed)
    return tuple(compiled)
