"""Typed, fail-closed bridge from *compiled* rules to existing game primitives.

There are two deliberately separate paths:

* ``compile_effects`` receives only deterministic, already-compiled ``Effect``
  instances and produces a complete ordered block program for the stack.
* ``inspect_semantic_proposal`` inventories possible blocks in an LLM response.
  It NEVER produces a playable program or a game event.

Source-evidence validation alone cannot certify Magic rules, legal targets,
costs, timing, choices, replacement effects, or intervening conditions.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

from oracle_abilities import Effect, TokenSpec


class BlockCompilationError(ValueError):
    """A whole program contains a step the atomic kernel cannot execute."""


# The left side is a proposed *semantic* verb, not an authorization. The right
# side identifies a pre-existing simulator handler, not a newly invented one.
SEMANTIC_HANDLER_CANDIDATES = {
    'draw': 'draw_cards',
    'gain_life': 'gain_life',
    'lose_life': 'lose_life',
    'scry': 'scry',
    'surveil': 'surveil',
    'mill': 'mill_cards',
    'create_token': 'create_tokens',
}

_RECIPIENTS = {
    'draw_cards': frozenset({'controller'}),
    'gain_life': frozenset({'controller'}),
    'lose_life': frozenset({'self', 'each opponent'}),
    'scry': frozenset({'controller'}),
    'surveil': frozenset({'controller'}),
    'mill_cards': frozenset({'controller', 'each opponent', 'each player'}),
    'create_tokens': frozenset({'controller'}),
}


@dataclass(frozen=True)
class AtomicBlock:
    operation: str
    amount: int
    recipient: str
    token: TokenSpec | None = None

    def __post_init__(self):
        if self.operation not in _RECIPIENTS:
            raise BlockCompilationError(f'No atomic handler for {self.operation}')
        if type(self.amount) is not int or not 1 <= self.amount <= 1000:
            raise BlockCompilationError('Atomic amount must be an integer from 1 to 1000')
        if self.recipient not in _RECIPIENTS[self.operation]:
            raise BlockCompilationError(f'Unsupported {self.operation} recipient: {self.recipient}')
        if self.operation == 'create_tokens':
            if not isinstance(self.token, TokenSpec) or self.token.amount != self.amount:
                raise BlockCompilationError('Token creation needs a complete, matching token specification')
        elif self.token is not None:
            raise BlockCompilationError('Only token creation may carry a token specification')

    def event_step(self) -> dict:
        """Only the already-tested simulator event vocabulary crosses this edge."""
        data=dict(operation=self.operation,amount=self.amount,recipient=self.recipient)
        if self.token:
            data['tokenSpec']=dict(asdict(self.token),keywords=sorted(self.token.keywords))
        return data


@dataclass(frozen=True)
class CompiledBlockProgram:
    """A fully checked spell-resolution sequence from a trusted compiler."""
    blocks: tuple[AtomicBlock, ...]

    def __post_init__(self):
        if not self.blocks or len(self.blocks)>32 or not all(
                isinstance(step,AtomicBlock) for step in self.blocks):
            raise BlockCompilationError('A spell block program needs 1 to 32 complete steps')

    def stack_event(self, *, controller: int, source: str, name: str) -> dict:
        """Call only while resolving an already-legal spell on the game stack.

        This is not an action API and does not cast spells or grant priority.
        The simulator owns targets, payment, zone movement and stack timing.
        """
        if type(controller) is not int or controller<0 or not source or not name:
            raise BlockCompilationError('Missing stack resolution context')
        return dict(operation='ordered_effects',controller=controller,
                    source=source,name=name,
                    effect='; then '.join(step.operation for step in self.blocks),
                    steps=[step.event_step() for step in self.blocks])


def _compiled_steps(effect: Effect):
    if type(effect) is not Effect:
        raise BlockCompilationError('Only trusted compiler Effect objects may be lowered')
    if effect.operation=='ordered_effects':
        # A composite effect may only contain ordered steps, not independent
        # costs, targets, choices, replacement rules or side effects.
        if effect != Effect('ordered_effects',0,steps=effect.steps) or not effect.steps:
            raise BlockCompilationError('An ordered program has unhandled qualifiers')
        for step in effect.steps:
            yield from _compiled_steps(step)
        return
    # Check *every* Effect field against the minimal kernel representation.
    # Otherwise a new parser attribute could be silently dropped.
    if effect != Effect(effect.operation,effect.amount,
                        recipient=effect.recipient,token=effect.token):
        raise BlockCompilationError('Atomic effect has an unhandled cost, target or qualifier')
    yield AtomicBlock(effect.operation,effect.amount,effect.recipient,effect.token)


def compile_effects(effects: tuple[Effect, ...]) -> CompiledBlockProgram:
    """Lower an entire trusted rule program atomically; no partial execution."""
    if not isinstance(effects,tuple) or not effects:
        raise BlockCompilationError('Expected nonempty compiled Effect tuple')
    blocks=[]
    for effect in effects:
        blocks.extend(_compiled_steps(effect))
        if len(blocks)>32:raise BlockCompilationError('Too many atomic blocks')
    return CompiledBlockProgram(tuple(blocks))


def inspect_semantic_proposal(card: dict, proposal: dict) -> dict:
    """Read-only candidate mapping; model output can NEVER call stack_event.

    Showing that a handler exists does not verify its amount, target, scope,
    dependencies, timing, legality or that the model interpreted text right.
    """
    from oracle_semantic_reader import fingerprint, validate_proposal
    validate_proposal(card,proposal)
    candidates=[]
    for unit in proposal['units']:
        for op in unit['operations']:
            candidates.append(dict(sourceOrder=len(candidates),faceIndex=unit['face_index'],
                lineIndex=unit['line_index'],source=unit['source'],
                category=unit['category'],verb=op['verb'],
                evidence=op['evidence'],amountExpression=op['amount'],
                subjectExpression=op['subject'],
                recipientExpression=op['recipient'],
                objectExpression=op['object'],
                qualifierExpression=op['qualifier'],
                timingExpression=unit['timing'],
                costExpression=unit['cost'],
                candidateHandler=SEMANTIC_HANDLER_CANDIDATES.get(op['verb']),
                dependencies=list(unit['needs'])))
    return dict(kind='untrusted-semantic-block-candidates',
                fingerprint=fingerprint(card),
                candidateOperations=len(candidates),
                handlerCandidates=sum(bool(c['candidateHandler']) for c in candidates),
                executionReady=False,approved=False,learningEligible=False,
                missing='Independent semantic verification, typed operand binding, timing, costs, targets and complete gameplay tests',
                candidates=candidates)
