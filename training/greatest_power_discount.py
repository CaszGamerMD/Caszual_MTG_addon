"""Strict parser for a permanent's self-referential greatest-power discount."""
import re

_PATTERN=re.compile(
    r'This spell costs \{X\} less to cast, where X is the greatest power '
    r'among creatures you control\.'
)


def parse(text):
    """Remove one exact greatest-controlled-creature-power discount clause."""
    lines=[line.strip() for line in text.splitlines() if line.strip()]
    found=[index for index,line in enumerate(lines) if _PATTERN.fullmatch(line)]
    if len(found)!=1:
        return None
    index=found[0]
    return '\n'.join(line for i,line in enumerate(lines) if i!=index)
