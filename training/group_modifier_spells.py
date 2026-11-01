"""Whole-text, resolution-bound temporary creature-team modifiers.

The same typed instruction works for new card names, keyword grants, and
power/toughness measurements. It never assumes a missing Oracle sentence.
"""
from dataclasses import dataclass
import re

from oracle_abilities import KEYWORDS


@dataclass(frozen=True)
class GroupModifier:
    keyword: str
    counted_stat: str
    recipient: str = 'controller'

    def __post_init__(self):
        if (self.keyword not in KEYWORDS - {'flash'}
                or self.counted_stat not in ('power','toughness')
                or self.recipient != 'controller'):
            raise ValueError('Unsupported group modifier')


_GREATEST = re.compile(
    r'Until end of turn, creatures you control gain ([a-z ]+) and get '
    r'\+X/\+X, where X is the greatest (power|toughness) among creatures '
    r'you control\.'
)


def parse(text,types):
    if not {'Instant','Sorcery'}.intersection(types):return None
    match=_GREATEST.fullmatch(text)
    if not match:return None
    try:return GroupModifier(match[1],match[2])
    except ValueError:return None


def resolve(sim,controller,card,program):
    if not isinstance(program,GroupModifier):
        raise RuntimeError('Unverified team modifier')
    game=sim.event_game('main')
    creatures=[state for state in game.battlefield.values()
               if state.controller==controller and game.creature(state)]
    index=0 if program.counted_stat=='power' else 1
    amount=max((game.stats(state)[index] for state in creatures),default=0)
    # All affected creatures and X are determined together as the spell
    # resolves; later entry or changes do not retroactively modify the set.
    affected=[]
    for state in creatures:
        state.temporary_power+=amount
        state.temporary_toughness+=amount
        game.grant_temporary(state,program.keyword)
        affected.append(state.id)
    sim.sync_events(game)
    sim.log('group_modifier','Team-wide temporary modifier resolves.',
            actor=controller,source=card.name,keyword=program.keyword,
            countedStat=program.counted_stat,amount=amount,affected=affected)
    sim.resolve_entry_triggers(sim.state_based_actions(),card)
