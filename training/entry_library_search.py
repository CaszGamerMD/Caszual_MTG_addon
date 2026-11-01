"""Ordered, typed ETB search for any number of subtype cards.

The diagnostic uses a documented deterministic selection/ordering policy.
Only names of revealed cards become public, and unsupported card programs
remain unsupported even when they are legally found in a private library.
"""
from dataclasses import dataclass
import random
import re

from creature_types import card_has_subtype, valid_creature_choice


@dataclass(frozen=True)
class EntryTopSearch:
    subtype: str
    any_number: bool = True

    def __post_init__(self):
        if not self.any_number or not valid_creature_choice(self.subtype):
            raise ValueError('Unsupported entry search selector')


_SEARCH=re.compile(
    r'When this creature enters, search your library for any number of '
    r'([A-Z][A-Za-z-]+) cards, reveal them, then shuffle and put those cards '
    r'on top in any order\.'
)


def parse(text,types):
    if 'Creature' not in types:return None
    match=_SEARCH.fullmatch(text)
    if not match:return None
    try:return EntryTopSearch(match[1])
    except ValueError:return None


def resolve(sim,controller,source_name,program):
    if not isinstance(program,EntryTopSearch):
        raise RuntimeError('Unverified ETB library search')
    player=sim.players[controller]
    # Accept the optional "any number" decision: select all matches in the
    # strict diagnostic's deterministic policy and order by physical id.
    chosen=sorted((c for c in player.library if card_has_subtype(c,program.subtype)),
                  key=lambda card:card.id)
    for card in chosen:player.library.remove(card)
    # Complete the physical zone move before logging: sim.log asserts card
    # conservation and the cards are only temporarily between zones here.
    sim.library_random_sequence+=1
    random.Random(f'{sim.seed}:library:{sim.library_random_sequence}').shuffle(player.library)
    player.library.extend(chosen)
    sim.log('entry_search','Choose zero or more matching subtype cards from a private library.',
        actor=controller,source=source_name,subtype=program.subtype,
        count=len(chosen))
    if chosen:
        sim.log('entry_search_reveal','Reveal all chosen cards from the private search.',
            actor=controller,source=source_name,cards=[card.name for card in chosen])
    sim.log('library_shuffle','Shuffle before putting the revealed cards on top.',
            actor=controller,source=source_name)
    sim.log('entry_search_top','Put chosen cards on top in a deterministic legal order.',
        actor=controller,source=source_name,orderedCards=[card.name for card in chosen])
