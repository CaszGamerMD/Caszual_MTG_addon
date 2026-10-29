"""Strict complete-text grammar for attack-group card-draw triggers.

This is one independent rule primitive; combining it with other abilities
requires an explicit complete-program parser, never dropping trailing text.
"""
import re

_NUMBERS = {'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6}

def parse(text, types):
    if not {'Artifact', 'Enchantment', 'Creature', 'Planeswalker'} & set(types):
        return None
    match = re.fullmatch(
        r'Whenever you attack with (two|three|four|five|six|[2-9]) or more creatures, '
        r'draw (a card|one card|two cards|three cards|[1-9] cards)\.', text)
    if not match:
        return None
    threshold = _NUMBERS.get(match[1], int(match[1]) if match[1].isdigit() else 0)
    amount_word = match[2].split()[0]
    amount = 1 if amount_word in ('a', 'one') else _NUMBERS.get(amount_word, int(amount_word) if amount_word.isdigit() else 0)
    return threshold, amount
