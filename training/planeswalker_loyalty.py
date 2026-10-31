"""Whole-card verified, name-independent loyalty ability compiler.

The first foundation deliberately implements ONLY untargeted draw, gain-life,
and fully specified creature-token effects. Every Oracle line must be
understood, and the actual starting loyalty must be present. Real complex
planeswalkers remain unsupported until their entire instruction set works.
"""
from dataclasses import dataclass
import re
from oracle_abilities import effect
from semantic_execution_blocks import compile_effects,BlockCompilationError

@dataclass(frozen=True)
class LoyaltyAbility:
    delta: int
    program: object
    target_kind: str = ''
    effect_kind: str = 'atomic'

@dataclass(frozen=True)
class TimedCreatureModifier:
    power: int
    toughness: int
    expires: str = 'controller_next_turn'

@dataclass(frozen=True)
class MillThenOptionalCreatureReturn:
    amount: int

@dataclass(frozen=True)
class PlaneswalkerProgram:
    starting_loyalty: int
    abilities: tuple[LoyaltyAbility,...]

def compile_card(card):
    if card.get('layout','normal')!='normal' or card.get('faces'):
        return None
    if set(card.get('types',()))!={'Planeswalker'}:
        return None
    printed=card.get('loyalty')
    if type(printed) is int:
        amount=printed
    elif isinstance(printed,str) and re.fullmatch(r'0|[1-9][0-9]*',printed):
        amount=int(printed)
    else:return None
    if not 0<=amount<=1000:return None
    lines=(card.get('oracleText') or '').strip().splitlines()
    if not 1<=len(lines)<=6:return None
    abilities=[]
    for line in lines:
        m=re.fullmatch(r'([+\-−])([0-9]+): (.+)',line)
        if not m:return None
        number=int(m[2])
        if number>1000:return None
        delta=number if m[1]=='+' else -number
        body=m[3]
        # Reject choices, targeting, clauses, and all hidden effects instead
        # of dropping unrecognized text. Keep full text in the evidence.
        targeted=re.fullmatch(
            r'Up to one target creature gets ([+-][0-9]+)/([+-][0-9]+) until your next turn\.',
            body)
        if targeted:
            power,toughness=int(targeted[1]),int(targeted[2])
            if not -20<=power<=20 or not -20<=toughness<=20:return None
            abilities.append(LoyaltyAbility(delta,TimedCreatureModifier(power,toughness),
                                            'up_to_one_creature','timed_modifier'))
            continue
        mill=re.fullmatch(
            r'Mill (one|two|three|[1-9][0-9]*) cards?, then you may return '
            r'a creature card from your graveyard to your hand\.',body)
        if mill:
            count={'one':1,'two':2,'three':3}.get(mill[1])
            if count is None:count=int(mill[1])
            if count>1000:return None
            abilities.append(LoyaltyAbility(delta,MillThenOptionalCreatureReturn(count),
                                            effect_kind='mill_optional_creature_return'))
            continue
        # Parse the complete emblem instruction, including the quoted
        # delayed trigger. Do not permit unsupported embedded clauses.
        if body.startswith('You get an emblem with '):
            from planeswalker_emblems import compile_emblem
            emblem=compile_emblem(body)
            if emblem is None:return None
            abilities.append(LoyaltyAbility(delta,emblem,effect_kind='emblem'))
            continue
        from planeswalker_conditional import compile_ability,DrawThenConditionalDiscard,UnblockableTokenProgram
        candidate=compile_ability(body)
        if candidate is not None:
            family=('draw_conditional_discard' if isinstance(candidate,DrawThenConditionalDiscard)
                    else 'unblockable_tokens')
            abilities.append(LoyaltyAbility(delta,candidate,effect_kind=family))
            continue
        parsed=effect(body[:1].lower()+body[1:])
        if parsed is None:return None
        try:program=compile_effects((parsed,))
        except (BlockCompilationError,ValueError):return None
        if len(program.blocks)!=1:return None
        if program.blocks[0].operation not in ('draw_cards','gain_life','create_tokens'):
            return None
        abilities.append(LoyaltyAbility(delta,program))
    return PlaneswalkerProgram(amount,tuple(abilities))

def inspect_card(card):
    """Read-only blockers for deck study; this never enables unsupported cards."""
    lines=(card.get('oracleText') or '').strip().splitlines()
    return dict(name=card.get('name'),kind='planeswalker-capabilities',
                startingLoyalty=card.get('loyalty'),
                loyaltyAbilities=[dict(cost=line.split(':',1)[0],
                                       oracle=line.split(':',1)[1].strip())
                                  for line in lines if re.match(r'^[+\-−][0-9]+:',line)],
                unhandledLines=[line for line in lines if not re.match(r'^[+\-−][0-9]+:',line)],
                executionReady=compile_card(card) is not None)
