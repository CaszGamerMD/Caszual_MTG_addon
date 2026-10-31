"""Read-only bridge from compiled executable rules to strategy evidence.

Printed-text matching can hypothesize a payoff, but only a successful
diagnostic importer and an actual compiled definition can confirm executable
mechanics. This component never creates legal actions or overrides the engine.
A supported result is *diagnostic* support, not full Commander certification.
"""
from __future__ import annotations
from dataclasses import asdict
import simulator as s


ROLE_BY_OPERATION = {
    'create_tokens': 'token_supply',
    'create_treasures': 'mana_engine',
    'draw_cards': 'card_engine',
    'reveal_creatures': 'card_engine',
    'gain_life': 'life_engine',
    'lose_life': 'damage_payoff',
    'damage': 'damage_payoff',
    'damage_board': 'damage_payoff',
    'damage_any_target': 'damage_payoff',
    'self_counter': 'counter_growth',
    'add_counters': 'counter_growth',
    'target_counter': 'counter_growth',
    'return_graveyard': 'recursion_engine',
}
ROLE_BY_KIND = {
    'removal_spell': 'removal',
    'counter_spell': 'interaction',
    'equipment': 'equipment_engine',
    'token_spell': 'token_supply',
    'mana_artifact': 'mana_engine',
}


def _strategy_role(step):
    # Losing your *own* life is a cost/drawback, not opponent damage output.
    if step['operation']=='lose_life' and step.get('recipient') in ('self','controller'):
        return None
    return ROLE_BY_OPERATION.get(step['operation'])


def _effect_steps(effect):
    """Flatten a known ordered effect into individual ordered mechanics."""
    if effect.operation == 'ordered_effects':
        return tuple(_effect_steps(part)[0] for part in effect.steps)
    data=dict(operation=effect.operation,amount=effect.amount,
              recipient=effect.recipient, optional=effect.optional)
    if effect.token:
        data['token']=dict(amount=effect.token.amount,power=effect.token.power,
                           toughness=effect.token.toughness,
                           subtypes=list(effect.token.subtypes))
    return (data,)


def compiled_knowledge(card: s.Card) -> dict:
    """An auditable semantic representation of one *already compiled* card."""
    if card.kind=='unsupported':
        return dict(supported=False,diagnosticOnly=True,
                    card=card.name,roles=[],rules=[],why='whole-card compiler rejected card')
    definition=card.event_definition
    roles=set()
    if card.kind in ROLE_BY_KIND:
        roles.add(ROLE_BY_KIND[card.kind])
    entries=[]
    if card.kind=='sequence_spell' and card.sequence_effects:
        steps=[step for part in card.sequence_effects for step in _effect_steps(part)]
        entries.append(dict(timing='spell_resolution',event='resolve',steps=steps))
        for step in steps:
            role=_strategy_role(step)
            if role:roles.add(role)
    if definition:
        for trig in definition.triggers:
            steps=_effect_steps(trig.effect)
            entries.append(dict(timing='trigger',event=trig.event,
                  subject=dict(relation=trig.subject.relation,
                               subtype=trig.subject.subtype,
                               other=trig.subject.other,
                               selfOnly=trig.subject.self_only,
                               creature=trig.subject.creature),
                  steps=list(steps)))
            for item in steps:
                role=_strategy_role(item)
                if role:roles.add(role)
        if definition.scaled_mana_tap:
            family=definition.scaled_mana_tap
            entries.append(dict(timing='activated',cost='{T}',
                event='mana',source='self',
                amountBasis='current effective power' if family.startswith('power:')
                            else 'controlled permanent type count',
                color=family[6:] if family.startswith('power:') else 'one chosen color',
                steps=[dict(operation='add_mana')]))
            roles.add('mana_engine')
        if definition.static_effects:
            entries.append(dict(timing='continuous',
                count=len(definition.static_effects),
                steps=[dict(operation='continuous_modifier')]))
            roles.add('board_amplifier')
        if definition.attachment:
            roles.add('equipment_engine' if definition.attachment[0]=='equipment' else
                      'attachment_engine')
        if definition.token_action_triggers or definition.token_replacements:
            roles.add('token_synergy')
        if definition.counter_replacements:
            roles.add('counter_synergy')
    return dict(supported=True,diagnosticOnly=True,card=card.name,
                kind=card.kind,roles=sorted(roles),rules=entries,
                why='The diagnostic rules importer compiled this whole card')


def compile_knowledge(rules: s.RulesBridge, raw: dict, uid='knowledge') -> dict:
    """Compile via the same importer used by matches; no text-only promotion."""
    identity=set(raw.get('colorIdentity') or [])
    card=s.import_diagnostic_card(rules,raw,0,uid,identity)
    return compiled_knowledge(card)


def analyze_known_cards(rules, deck: dict) -> dict:
    """Summarize known semantics; never claim unsupported card roles are proven."""
    results=[]
    for i,raw in enumerate([*deck['commanders'],*deck['mainboard']]):
        meaning=compile_knowledge(rules,raw,f'knowledge-{i}')
        meaning['quantity']=int(raw.get('quantity',1))
        results.append(meaning)
    return dict(deckId=deck.get('sourceDeckId'),deck=deck.get('name'),
                confirmedRules=[x for x in results if x['supported']],
                uncompiledCards=[x['card'] for x in results if not x['supported']],
                diagnosticOnly=True)
