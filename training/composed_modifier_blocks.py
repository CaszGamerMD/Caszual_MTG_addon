"""Reviewed target/temporary/conditional spell blocks, never model-executable.

This conservative whole-text grammar *verifies* a small compositional family
of Oracle effects. All instructions must lower into known typed blocks. The
program is attached only by the deterministic importer; model proposals may
suggest these blocks but cannot construct an executable spell from evidence
quotes alone.
"""
from __future__ import annotations

from dataclasses import dataclass
import re

from oracle_abilities import KEYWORDS, TokenSpec, effect, parse_token_creation
from counted_effect_blocks import BattlefieldCount, parse as parse_counted_effects


@dataclass(frozen=True)
class CreatureTargets:
    minimum: int
    maximum: int

    def bind(self, supplied, legal_ids) -> tuple[str, ...]:
        """Choose and validate distinct targets before paying the spell cost."""
        targets=() if supplied is None else (supplied,) if isinstance(supplied,str) else supplied
        if (not isinstance(targets,(tuple,list)) or any(not isinstance(t,str) for t in targets)
                or len(targets)!=len(set(targets))
                or not self.minimum<=len(targets)<=self.maximum
                or any(t not in legal_ids for t in targets)):
            raise ValueError('Invalid creature target selection')
        return tuple(targets)


@dataclass(frozen=True)
class TemporaryModifier:
    power: int = 0
    toughness: int = 0
    keyword: str = ''
    set_color: str = ''

    def __post_init__(self):
        if self.keyword and self.keyword not in KEYWORDS-{'flash'}:
            raise ValueError('Unsupported temporary keyword')
        if self.set_color and self.set_color not in ('White','Blue','Black','Red','Green'):
            raise ValueError('Unsupported temporary color')
        if not (self.power or self.toughness or self.keyword or self.set_color):
            raise ValueError('Temporary modifier has no effect')


@dataclass(frozen=True)
class ControlCondition:
    """Evaluate from the current battlefield *at resolution*, not on cast."""
    permanent_type_or_subtype: str

    def holds(self, game, controller: int) -> bool:
        return any(state.controller==controller and self.permanent_type_or_subtype in (
            state.definition.types|state.definition.subtypes)
            for state in game.battlefield.values())


@dataclass(frozen=True)
class SpellStep:
    operation: str
    modifier: TemporaryModifier | None = None
    amount: int = 0
    token: TokenSpec | None = None
    condition: ControlCondition | None = None
    count: BattlefieldCount | None = None

    def __post_init__(self):
        if self.count is not None and not isinstance(self.count,BattlefieldCount):
            raise ValueError('Malformed count binding')
        if self.operation=='modify_targets':
            if self.modifier is None or self.amount or self.token or self.condition or self.count:
                raise ValueError('Malformed temporary modifier block')
        elif self.operation in ('draw_cards','gain_life'):
            if self.modifier or self.token or type(self.amount) is not int or not 1<=self.amount<=1000:
                raise ValueError('Malformed draw/life block')
        elif self.operation=='create_tokens':
            if self.modifier or not isinstance(self.token,TokenSpec) or self.amount!=self.token.amount:
                raise ValueError('Malformed token block')
        else:
            raise ValueError('Unimplemented spell block')


@dataclass(frozen=True)
class ComposedModifierProgram:
    targets: CreatureTargets
    steps: tuple[SpellStep, ...]

    def __post_init__(self):
        if (not isinstance(self.targets,CreatureTargets) or not 1<=len(self.steps)<=8
                or not all(isinstance(step,SpellStep) for step in self.steps)
                or self.steps[0].operation!='modify_targets'
                or any(step.operation=='modify_targets' for step in self.steps[1:])):
            raise ValueError('Incomplete targeted spell program')


_FIRST = re.compile(r'(Target creature|Up to two target creatures each) (.+)')
_STATS = re.compile(r'gets? ([+-][0-9]+)/([+-][0-9]+)(?: and gains? ([a-z ]+))? until end of turn')
_COLOR = re.compile(r'becomes (white|blue|black|red|green) and gains ([a-z ]+) until end of turn')
_ABILITY = re.compile(r'gains? ([a-z ]+) until end of turn')
_CONDITION = re.compile(r'If you control an? ([A-Z][a-z]+), (.+)')


def parse(text: str, types: list[str] | tuple[str, ...]) -> ComposedModifierProgram | None:
    """Parse independent verified instructions; reject unknown remainders."""
    if not {'Instant','Sorcery'}&set(types):return None
    sentences=re.split(r'(?<=\.)\s+(?=[A-Z])',text.strip())
    if not sentences or len(sentences)>8 or any(not s.endswith('.') for s in sentences):
        return None
    first=_FIRST.fullmatch(sentences[0][:-1])
    if not first:return None
    targets=(CreatureTargets(1,1) if first[1]=='Target creature' else CreatureTargets(0,2))
    body=first[2]
    try:
        match=_STATS.fullmatch(body)
        if match:
            modifier=TemporaryModifier(int(match[1]),int(match[2]),match[3] or '')
        else:
            match=_COLOR.fullmatch(body)
            if match:modifier=TemporaryModifier(keyword=match[2],set_color=match[1].title())
            else:
                match=_ABILITY.fullmatch(body)
                if not match:return None
                modifier=TemporaryModifier(keyword=match[1])
    except ValueError:
        return None
    steps=[SpellStep('modify_targets',modifier=modifier)]
    for sentence in sentences[1:]:
        condition=None;instruction=sentence
        match=_CONDITION.fullmatch(sentence[:-1])
        if match:
            condition=ControlCondition(match[1])
            instruction=match[2][:1].upper()+match[2][1:]+'.'
        atom=effect(instruction[:1].lower()+instruction[1:])
        if atom is not None and atom.operation in ('draw_cards','gain_life') and atom.amount>0:
            steps.append(SpellStep(atom.operation,amount=atom.amount,condition=condition))
            continue
        token=parse_token_creation(instruction)
        if token:
            steps.append(SpellStep('create_tokens',amount=token.amount,token=token,
                                   condition=condition))
            continue
        # The same independently checked count block may follow a targeted
        # modifier. Its current battlefield operands bind at resolution.
        counted=parse_counted_effects(instruction,types)
        if counted and len(counted.steps)==1:
            bound=counted.steps[0]
            steps.append(SpellStep(bound.base.operation,amount=bound.base.amount,
                                   token=bound.base.token,condition=condition,
                                   count=bound.count))
            continue
        return None
    return ComposedModifierProgram(targets,tuple(steps))
