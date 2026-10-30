"""Whole-text creature sweeps rewarding actual destruction with artifact tokens."""
import re


def parse(text, types):
    if types != ['Sorcery']:
        return ()
    match = re.fullmatch(
        r'Destroy all creatures\. For each (nontoken )?creature destroyed this way, '
        r'you create (a|two|three) (tapped )?Treasure token(s)?\.', text)
    if not match:
        return ()
    quantity = {'a': 1, 'two': 2, 'three': 3}[match[2]]
    if (quantity == 1) == bool(match[4]):
        return ()  # Singular/plural must agree.
    return (bool(match[1]), quantity, bool(match[3]))
