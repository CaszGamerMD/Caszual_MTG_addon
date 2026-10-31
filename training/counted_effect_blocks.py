"""Verified resolution-time battlefield quantities for reusable spell blocks.

Only a whole-text deterministic importer creates these programs. A language
model's proposed verb or count is untrusted evidence and cannot reach this
module's executable compiler. The battlefield is queried once for each step
*when that step resolves*; a preceding token step can change a later count.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import re

from oracle_abilities import Effect, effect
from semantic_execution_blocks import AtomicBlock, compile_effects


_TYPES = {'creature':'Creature','artifact':'Artifact','enchantment':'Enchantment',
          'land':'Land','planeswalker':'Planeswalker'}
_SCOPES = {'you control':'controller','your opponents control':'opponent',
           'on the battlefield':'any'}
_COUNTED_EFFECTS = frozenset({'draw_cards','gain_life','create_tokens'})


@dataclass(frozen=True)
class BattlefieldCount:
    relation: str
    card_type: str = ''
    subtype: str = ''
    tapped: bool | None = None
    nontoken: bool = False

    def __post_init__(self):
        if (self.relation not in ('controller','opponent','any')
                or self.card_type not in ('','Creature','Artifact','Enchantment','Land','Planeswalker')
                or bool(self.card_type)==bool(self.subtype)
                or self.tapped not in (None,True,False)
                or type(self.nontoken) is not bool):
            raise ValueError('Incomplete or unsupported battlefield count')

    def evaluate(self, game, controller: int) -> int:
        """Use current effective battlefield types, controller and status."""
        return sum(
            (self.relation=='any' or
             self.relation=='controller' and state.controller==controller or
             self.relation=='opponent' and state.controller!=controller)
            and (not self.card_type or (game.creature(state) if self.card_type=='Creature'
                 else self.card_type in state.definition.types))
            and (not self.subtype or self.subtype in state.definition.subtypes)
            and (self.tapped is None or state.tapped==self.tapped)
            and (not self.nontoken or not state.token)
            for state in game.battlefield.values())


@dataclass(frozen=True)
class QuantityBlock:
    """A validated atomic effect and an optional bound count multiplier."""
    base: AtomicBlock
    count: BattlefieldCount | None = None

    def __post_init__(self):
        if (not isinstance(self.base,AtomicBlock) or self.count is not None and
                (not isinstance(self.count,BattlefieldCount)
                 or self.base.operation not in _COUNTED_EFFECTS)):
            raise ValueError('Unsupported resolution-time block')

    def bind(self, game, controller: int) -> AtomicBlock | None:
        multiplier=self.count.evaluate(game,controller) if self.count else 1
        amount=self.base.amount*multiplier
        if amount==0:return None  # No effect; later written steps still run.
        # Always pass the *entire concrete atom* through the independently
        # tested compiler, including dynamically updated TokenSpec.amount.
        token=(replace(self.base.token,amount=amount) if self.base.token else None)
        atom=Effect(self.base.operation,amount,recipient=self.base.recipient,token=token)
        return compile_effects((atom,)).blocks[0]


@dataclass(frozen=True)
class CountedSpellProgram:
    steps: tuple[QuantityBlock, ...]

    def __post_init__(self):
        if (not 1<=len(self.steps)<=8 or
                not all(isinstance(step,QuantityBlock) for step in self.steps) or
                not any(step.count for step in self.steps)):
            raise ValueError('A counted spell needs a complete counted program')


_COUNTER = re.compile(r'(.+) for each ((?:(?:tapped|untapped|nontoken) )?'
                      r'(?:creature|artifact|enchantment|land|planeswalker|'
                      r'[A-Z][a-z]+)) '
                      r'(you control|your opponents control|on the battlefield)\.')
_OBJECT = re.compile(r'(?:(tapped|untapped|nontoken) )?'
                     r'(creature|artifact|enchantment|land|planeswalker|[A-Z][a-z]+)')


def _count_from_text(noun: str, scope: str) -> BattlefieldCount | None:
    match=_OBJECT.fullmatch(noun)
    if not match:return None
    qualifier,kind=match.groups()
    card_type=_TYPES.get(kind,'')
    # Printed proper nouns are typed creature subtypes; they never match all
    # permanents just because the card name happens to contain that word.
    return BattlefieldCount(_SCOPES[scope],card_type=card_type,
                            subtype='' if card_type else kind,
                            tapped=(True if qualifier=='tapped' else False if qualifier=='untapped'
                                    else None),nontoken=qualifier=='nontoken')


def parse(text: str, types: list[str] | tuple[str, ...]) -> CountedSpellProgram | None:
    """Accept only complete instants/sorceries using checked atomic blocks."""
    if not {'Instant','Sorcery'}&set(types):return None
    sentences=re.split(r'(?<=\.)\s+(?=[A-Z])',text.strip())
    if not 1<=len(sentences)<=8 or any(not s.endswith('.') for s in sentences):
        return None
    steps=[]
    for sentence in sentences:
        match=_COUNTER.fullmatch(sentence)
        count=_count_from_text(match[2],match[3]) if match else None
        instruction=match[1]+'.' if match else sentence
        atom=effect(instruction[:1].lower()+instruction[1:])
        if atom is None or match and (count is None or atom.operation not in _COUNTED_EFFECTS):
            return None
        try:
            compiled=compile_effects((atom,))
        except ValueError:
            return None
        if len(compiled.blocks)!=1:return None
        steps.append(QuantityBlock(compiled.blocks[0],count))
    if not any(step.count for step in steps):return None
    return CountedSpellProgram(tuple(steps))
