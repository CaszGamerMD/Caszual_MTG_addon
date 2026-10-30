"""Experimental event/continuous-effect kernel for a small set of real cards.

This is an isolated rules prototype: it does not implement priority, the stack,
combat damage, costs for casting spells, or the full turn simulator. Unknown
rules raise NeedsRules rather than being treated as blank.
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
import re
from attachments import parse as parse_attachment, parse_bestow, parse_equipment_removals, parse_with_intrinsic
from attack_abilities import compile as compile_attacks
from oracle_abilities import Trigger, StaticEffect, compile_abilities, matches, event_data, cast_matches


class NeedsRules(ValueError):
    pass


class IllegalAction(ValueError):
    pass


def rule_text(text: str) -> str:
    # Remove only balanced parenthetical reminder text; actual rules stay intact.
    out, depth = [], 0
    for c in text:
        if c == "(":
            depth += 1
        elif c == ")":
            if depth == 0: return text.strip()
            depth -= 1
        elif depth == 0:
            out.append(c)
    return text.strip() if depth else "".join(out).strip()


KOLODIN = """Mounts and Vehicles you control have haste.
Whenever a Mount you control enters, it becomes saddled until end of turn.
Whenever a Vehicle you control enters, it becomes an artifact creature until end of turn."""
ANDURIL = """Equipped creature gets +3/+1.
Whenever equipped creature attacks, create two tapped 1/1 white Spirit creature tokens with flying. If that creature is legendary, instead create two of those tokens that are tapped and attacking.
Equip {2}"""
ZURGO = """Haste
Zurgo attacks each combat if able.
During your turn, Zurgo has indestructible.
Whenever a creature dealt damage by Zurgo this turn dies, put a +1/+1 counter on Zurgo."""
OBYRA = """Flash
Flying
Whenever another Faerie you control enters, each opponent loses 1 life."""
COHORT = """Flying
This creature gets +1/+1 as long as you control another blue creature."""
BITTERBLOSSOM = "At the beginning of your upkeep, you lose 1 life and create a 1/1 black Faerie Rogue creature token with flying."
BITTERBLOOM = """Flash
Flying
At the beginning of your upkeep, you lose 1 life and create a 1/1 blue and black Faerie creature token with flying."""
SEER = """Flying
When this creature enters, scry 2."""
SQUIRREL_MOB = "This creature gets +1/+1 for each other Squirrel on the battlefield."
SQUIRREL_SOVEREIGN = "Other Squirrels you control get +1/+1."
BLOOD_ARTIST = "Whenever this creature or another creature dies, target player loses 1 life and you gain 1 life."
ZULAPORT = "Whenever this creature or another creature you control dies, each opponent loses 1 life and you gain 1 life."
NESTED_SHAMBLER = "When this creature dies, create X tapped 1/1 green Squirrel creature tokens, where X is this creature's power."
IMPACT_TREMORS = "Whenever a creature you control enters, this enchantment deals 1 damage to each opponent."
INSTIGATOR = "When this creature enters, create a 1/1 red Goblin creature token."
MUSTANG = """Whenever this creature attacks while saddled, untap it and put a +1/+1 counter on it.
Saddle 1"""
SIMPLE_ABILITIES = {"flying", "first strike", "double strike", "lifelink", "vigilance",
                    "trample", "haste", "defender", "reach", "deathtouch", "indestructible", "hexproof", "menace",
                    "plainswalk", "islandwalk", "swampwalk", "mountainwalk", "forestwalk", "shroud", "fear"}


@dataclass(frozen=True)
class Definition:
    name: str
    types: frozenset[str]
    subtypes: frozenset[str]
    legendary: bool
    power: int
    toughness: int
    abilities: frozenset[str]
    crew: int | None = None
    saddle: int | None = None
    supported: bool = True
    reason: str = ""
    colors: frozenset[str] = frozenset()
    triggers: tuple[Trigger, ...] = ()
    static_effects: tuple[StaticEffect, ...] = ()
    attack_effects: tuple = ()
    attachment: tuple = ()
    activations: tuple = ()
    devotion: tuple = ()
    mana_cost: str = ""
    bestow: tuple = ()
    ability_removals: tuple = ()
    loyalty: int | None = None
    station: tuple = ()
    history_activation: tuple = ()
    equipment_attacks: tuple = ()
    pilot_bonus: int = 0
    attachment_scale: tuple = ()
    role_events: tuple = ()
    enchanted_draw: bool = False
    attachment_draw: bool = False
    aura_graveyard_draw: bool = False
    damage_events: tuple = ()
    life_multiplier: int = 1
    opponent_creatures_enter_tapped: bool = False
    life_addition: int = 0
    opponent_life_gain_becomes_loss: bool = False
    prevent_combat_damage_to_attackers: bool = False
    cost_reductions: tuple = ()
    counter_replacements: tuple = ()
    token_replacements: tuple = ()
    token_action_triggers: tuple = ()
    token_leave_triggers: tuple = ()
    upkeep_attachment_counters: int = 0
    entry_attachment_counters: int = 0
    double_attachment_counters_upkeep: bool = False
    role: str = ""
    entry_counter_grants: tuple = ()
    attack_watchers: tuple = ()
    chosen_type_entry: bool = False
    aura_exile: bool = False  # Targeted ETB exile lasting until this Aura leaves.
    linked_exile: str = ''  # Separate ETB-exile and LTB-return triggers, with source identity.
    tribal_tap_tokens: tuple = ()  # (token spec, counted subtype), evaluated on resolution.
    scaled_mana_tap: str = ''  # Tap for X mana of one chosen color, based on permanents.
    living_weapon: bool = False  # ETB create 0/0 Phyrexian Germ, then attach.
    sacrifice_ability: tuple = ()  # (effect, sacrificed subtype, effect parameter).
    land_counter_ability: str = ''  # Mana cost for tap-to-counter-each-controlled-creature.
    land_counter_scope: str = 'all'  # Or a color-limited, entered-this-turn subset.
    mentor: bool = False  # Attack trigger: counter on a lesser-power attacker.
    attack_nontoken_tokens: tuple = ()  # Nontoken attacker creates a tapped attacking token.
    modal_attack_tokens: tuple = ()  # Two modes; chosen on attack, variable X at resolution.
    sacrifice_team_boost: tuple = ()  # Self-sacrifice cost for a team-wide temporary boost.
    sacrifice_protection: tuple = ()  # Mana + self-sacrifice to grant chosen-color protection.
    attack_group_draw: tuple = ()  # (minimum declared attackers, cards drawn) on the stack.
    discard_token_ability: tuple = ()  # (mana cost, TokenSpec); discard one card as cost.
    umbra_armor: bool = False  # Replace destruction of the enchanted creature.
    regenerate_subtype: str = ''  # Tap: create a one-use destruction replacement shield.
    entry_keyword_choices: tuple[str, ...] = ()  # Choose one keyword counter before entry.
    dynamic_pt_color: str = ''  # Characteristic-defining P/T: own colored permanents.
    combat_limits: tuple[int, int] = ()  # Attack-triggered block cap, tapped-source attack cap.
    upkeep_token_rule: tuple = ()  # (each/your, condition, counted subtype, divisor, TokenSpec).
    land_type_effect: tuple = ()  # (scope, replace/add, basic land subtypes).
    additional_land_plays: int = 0  # Static permission, counted while source stays in play.
    end_step_life_distribution: bool = False  # Other targets, allocation at trigger placement.
    modal_role_choices: tuple = ()  # Role types; one chosen when ETB trigger enters stack.
    protected_spell_types: tuple = ()  # Spell types controlled by this source cannot be countered.
    animate_land_ability: tuple = ()  # (mana cost, Elemental subtype, counted permanent type).
    prevents_opponent_sacrifice: bool = False  # Continuous rule: opposing effects can't force sacrifices.
    equipment_basic_search: bool = False  # Equipped attacker searches for tapped basic land.
    graveyard_exile_activation: tuple = ()  # Cost, conditional creature-token specification.
    enchantment_copy_cost: str = ''  # Pay mana and tap to copy a stack ability from an enchantment.
    class_program: tuple = ()  # Spell tax, Level 2/3 costs, anthem, attack bonus and keyword.
    attachment_counter_scale: tuple = ()  # P/T added per counter on the attached permanent.
    equipment_planeswalker_cost: str = ''  # Alternative equip targeting a planeswalker.
    equipment_creature_conversion: bool = False  # Equipped permanent becomes non-planeswalker creature.
    combat_reattach: bool = False  # Optional start-of-combat Aura/Equipment movement.
    equipment_return_dying: bool = False  # Equipped creature dies -> return from graveyard.
    constellation_counter: bool = False  # Enchantment ETB triggers targeted +1/+1.
    enchantment_combat_copy: bool = False  # Once-per-turn enchantment token copy on damage.
    saga_chapter_scale: tuple = ()  # Chapter I and II P/T per artifact/enchantment.
    self_artifact_enchantment_scale: tuple = ()  # Self static P/T count on transformed face.


def parse_card(card: dict) -> Definition:
    name = card.get("name", "")
    types = frozenset(card.get("types") or [])
    subtypes = frozenset(card.get("subTypes") or [])
    text = rule_text(card.get("oracleText") or "")
    from dynamic_characteristics import parse_colored_permanent_pt
    dynamic_pt=parse_colored_permanent_pt(text,name,types)
    try:
        power, toughness = ((0,0) if dynamic_pt and card.get('power')=='*' and card.get('toughness')=='*'
                            else (int(card.get("power") or 0),int(card.get("toughness") or 0)))
    except ValueError:
        return Definition(name, types, subtypes, False, 0, 0, frozenset(), supported=False,
                          reason="Variable power or toughness")
    loyalty=None
    if 'Planeswalker' in types:
        printed=str(card.get('loyalty',''))
        if not re.fullmatch(r'[0-9]+',printed):
            return Definition(name,types,subtypes,False,power,toughness,frozenset(),supported=False,reason='Missing or variable loyalty')
        loyalty=int(printed)
    base = dict(name=name, types=types, subtypes=subtypes,
                legendary="Legendary" in (card.get("superTypes") or []), power=power, toughness=toughness,
                colors=frozenset(card.get("colors") or []),mana_cost=card.get("manaCost") or "",loyalty=loyalty)
    if ("Creature" in types or "Vehicle" in subtypes or "Spacecraft" in subtypes) and not dynamic_pt and any(card.get(stat) in (None, "") for stat in ("power", "toughness")):
        return Definition(**base, abilities=frozenset(), supported=False, reason="Missing or invalid fixed power/toughness")
    from saga_abilities import compile_saga, compile_transformed_creature
    saga_program=compile_saga(text,types,subtypes)
    if saga_program:
        return Definition(**base,abilities=frozenset(),saga_chapter_scale=saga_program)
    self_scale=compile_transformed_creature(text,types)
    if self_scale:
        return Definition(**base,abilities=frozenset(),
                          self_artifact_enchantment_scale=self_scale)
    from constellation_copy import compile as compile_constellation_copy
    if compile_constellation_copy(text,name,types,subtypes):
        return Definition(**base,abilities=frozenset(),constellation_counter=True,
                          enchantment_combat_copy=True)
    halvar_lines=text.splitlines()
    if len(halvar_lines)==2 and halvar_lines[1]==(
            'At the beginning of each combat, you may attach target Aura or Equipment '
            'attached to a creature you control to target creature you control.'):
        anthem=compile_abilities(halvar_lines[0],name)
        if anthem and anthem.static_effects and all(
                effect.requires_attachment for effect in anthem.static_effects):
            return Definition(**base,abilities=anthem.keywords,
                              static_effects=anthem.static_effects,combat_reattach=True)
    from counter_equipment import parse as parse_counter_equipment
    scaling_equipment=parse_counter_equipment(text,types,subtypes)
    if scaling_equipment:
        return Definition(**base,abilities=frozenset(),
                          attachment=scaling_equipment[0],
                          attachment_counter_scale=scaling_equipment[1],
                          equipment_planeswalker_cost=scaling_equipment[2],
                          equipment_creature_conversion=True)
    from class_abilities import parse as parse_class
    class_program=parse_class(text,types,subtypes)
    if class_program:
        return Definition(**base,abilities=frozenset(),class_program=class_program)
    from land_animation_spell_protection import parse as parse_land_animation
    land_animation=parse_land_animation(text,types)
    if land_animation:
        return Definition(**base,abilities=frozenset(),protected_spell_types=land_animation[0],
                          animate_land_ability=land_animation[1:])
    from modal_role_choices import parse as parse_modal_role_choices
    role_choices=parse_modal_role_choices(text,name,types)
    if role_choices:
        return Definition(**base,abilities=frozenset(),modal_role_choices=role_choices)
    from life_distribution import parse as parse_life_distribution
    life_distribution=parse_life_distribution(text,types)
    if life_distribution:
        return Definition(**base,abilities=life_distribution,end_step_life_distribution=True)
    from graveyard_exile_anthem import parse as parse_graveyard_exile_anthem
    graveyard_program=parse_graveyard_exile_anthem(text,types)
    if graveyard_program:
        effects,activation=graveyard_program
        return Definition(**base,abilities=frozenset(),static_effects=effects,
                          graveyard_exile_activation=activation)
    from death_exile_cast import parse as parse_death_exile_cast
    death_program=parse_death_exile_cast(text,types)
    if death_program:
        static,trigger=death_program
        return Definition(**base,abilities=frozenset(),static_effects=(static,),triggers=(trigger,))
    from forced_sacrifice import prevention as parse_sacrifice_prevention
    sacrifice_protected=parse_sacrifice_prevention(text,types)
    if sacrifice_protected:
        return Definition(**base,abilities=sacrifice_protected,prevents_opponent_sacrifice=True)
    from modal_attack_tokens import parse as parse_modal_attack_tokens
    modal_attack=parse_modal_attack_tokens(text,types)
    if modal_attack:
        return Definition(**base,abilities=modal_attack[0],modal_attack_tokens=modal_attack[1])
    from land_type_effects import parse as parse_land_type_effect
    land_type_effect=parse_land_type_effect(text,types)
    if land_type_effect:
        # Only a fully recognized two-clause program grants the extra play.
        from land_type_effects import additional_land_plays
        return Definition(**base,abilities=frozenset(),land_type_effect=land_type_effect,
                          additional_land_plays=additional_land_plays(text))
    from equipment_land_search import parse as parse_equipment_land_search
    equipment_search=parse_equipment_land_search(text,types,subtypes)
    if equipment_search:
        return Definition(**base,abilities=frozenset(),attachment=equipment_search[0],
                          living_weapon=equipment_search[1],equipment_basic_search=True)
    from upkeep_token_rules import parse_enchanted, parse_scaled
    upkeep_tokens=parse_enchanted(text,types) or parse_scaled(text,types)
    if upkeep_tokens:
        return Definition(**base,abilities=frozenset(),upkeep_token_rule=upkeep_tokens)
    from combat_limits import parse as parse_combat_limits
    combat_limits=parse_combat_limits(text,name,types)
    if combat_limits:
        return Definition(**base,abilities=combat_limits[0],combat_limits=combat_limits[1])
    if dynamic_pt:
        if card.get('power')!='*' or card.get('toughness')!='*':
            return Definition(**base,abilities=frozenset(),supported=False,reason='Variable characteristic mismatch')
        return Definition(**base,abilities=dynamic_pt[0],dynamic_pt_color=dynamic_pt[1])
    # Whole-instruction grammar: choose a real keyword counter before entry.
    from keyword_counters import parse_entry_choice
    keyword_choices=parse_entry_choice(text,types)
    if keyword_choices:
        return Definition(**base,abilities=frozenset(),entry_keyword_choices=keyword_choices)
    from enchantment_abilities import compile as compile_enchantments
    enchantments=compile_enchantments(text,name,types,subtypes)
    if enchantments:
        program=enchantments.base
        return Definition(**base,abilities=program.keywords,triggers=program.triggers,
            static_effects=program.static_effects,activations=program.activations,devotion=program.devotion,
            attachment=enchantments.attachment,attachment_scale=enchantments.scale,
            role_events=enchantments.role_events,enchanted_draw=enchantments.enchanted_draw,
            attachment_draw=enchantments.attachment_draw,aura_graveyard_draw=enchantments.aura_graveyard_draw,
            damage_events=enchantments.damage_events,
            life_multiplier=program.life_multiplier,
            opponent_creatures_enter_tapped=program.opponent_creatures_enter_tapped,
            life_addition=program.life_addition,
            opponent_life_gain_becomes_loss=program.opponent_life_gain_becomes_loss,
            prevent_combat_damage_to_attackers=program.prevent_combat_damage_to_attackers,
            cost_reductions=program.cost_reductions,
            counter_replacements=program.counter_replacements,token_replacements=program.token_replacements,
            token_action_triggers=program.token_action_triggers,token_leave_triggers=program.token_leave_triggers,
            attack_watchers=program.attack_watchers,chosen_type_entry=program.chosen_type_entry,
            upkeep_attachment_counters=enchantments.upkeep_attachment_counters,
            entry_attachment_counters=enchantments.entry_attachment_counters,
            double_attachment_counters_upkeep=enchantments.double_attachment_counters_upkeep,
            living_weapon=enchantments.living_weapon,
            equipment_return_dying=enchantments.equipment_return_dying)
    from land_aura_exile import parse as parse_land_aura_exile
    land_exile=parse_land_aura_exile(text,types,subtypes)
    if land_exile:
        return Definition(**base,abilities=frozenset(),attachment=land_exile,aura_exile=True)
    # Unlike an "until" effect, two separately triggered exile/return abilities
    # can exile permanently if the source leaves before its ETB resolves.
    linked=re.fullmatch(
        r"When this (enchantment|artifact) enters, exile target creature( an opponent controls)?\.\n"
        r"When this \1 leaves the battlefield, return the exiled card to the battlefield under its owner's control\.",text)
    if linked and linked[1].title() in types:
        return Definition(**base,abilities=frozenset(),linked_exile='opponent' if linked[2] else 'any')
    scaled_mana=re.fullmatch(
        r'\{T\}: Add X mana of any one color, where X is the number of (enchantments|artifacts) you control\.',text)
    if scaled_mana and types.intersection({'Creature','Artifact','Enchantment'}):
        return Definition(**base,abilities=frozenset(),scaled_mana_tap={
            'enchantments':'Enchantment','artifacts':'Artifact'}[scaled_mana[1]])
    from discard_abilities import parse as parse_discard_abilities
    discard_ability=parse_discard_abilities(text,types)
    if discard_ability:
        return Definition(**base,abilities=frozenset(),attack_group_draw=discard_ability[0],
                          discard_token_ability=discard_ability[1])
    from attack_group_draw import parse as parse_attack_group_draw
    group_draw=parse_attack_group_draw(text,types)
    if group_draw:
        return Definition(**base,abilities=frozenset(),attack_group_draw=group_draw)
    from protection_abilities import parse as parse_protection
    protection=parse_protection(text,types)
    if protection:
        return Definition(**base,abilities=protection[0],sacrifice_protection=protection[1:])
    from attack_enchantment import parse as parse_attack_enchantment
    attack_enchantment=parse_attack_enchantment(text,types)
    if attack_enchantment:
        return Definition(**base,abilities=frozenset(),attack_nontoken_tokens=(attack_enchantment[0],),
                          sacrifice_team_boost=attack_enchantment[1])
    from mentor_abilities import parse as parse_mentor
    mentor_triggers=parse_mentor(text,types)
    if mentor_triggers is not None:
        return Definition(**base,abilities=frozenset(),mentor=True,triggers=mentor_triggers)
    from sacrifice_abilities import parse as parse_sacrifice_ability
    sacrifice=parse_sacrifice_ability(text,types)
    if sacrifice:
        return Definition(**base,abilities=frozenset(),sacrifice_ability=sacrifice)
    from regeneration_abilities import parse as parse_regeneration
    regeneration=parse_regeneration(text,types)
    if regeneration:
        program,subtype=regeneration
        return Definition(**base,abilities=program.keywords,static_effects=program.static_effects,
                          regenerate_subtype=subtype)
    from tribal_tap_tokens import parse as parse_tribal_tap_tokens
    tribal_tap=parse_tribal_tap_tokens(text,types)
    if tribal_tap:
        return Definition(**base,abilities=frozenset(),tribal_tap_tokens=tribal_tap)
    from advanced_abilities import station,history,equipped_attacks
    levels=station(text,types,subtypes)
    if levels:return Definition(**base,abilities=frozenset(),station=levels)
    activated=history(text)
    if activated and 'Creature' in types and (not activated[0].devotion or 'Enchantment' in types):
        program,ability=activated
        return Definition(**base,abilities=program.keywords,triggers=program.triggers,static_effects=program.static_effects,history_activation=ability,activations=program.activations,devotion=program.devotion)
    equipped=equipped_attacks(text,types,subtypes)
    if equipped:return Definition(**base,abilities=frozenset(),attachment=equipped[0],equipment_attacks=equipped[1])
    bestow=parse_bestow(text,types)
    if bestow:return Definition(**base,abilities=bestow[1],bestow=bestow)
    removal_program=parse_equipment_removals(text,types,subtypes)
    if removal_program:return Definition(**base,abilities=frozenset(),attachment=removal_program[0],ability_removals=removal_program[1])
    from umbra_armor import parse as parse_umbra_armor
    umbra=parse_umbra_armor(text,types,subtypes)
    if umbra:
        return Definition(**base,abilities=frozenset(),attachment=umbra,umbra_armor=True)
    attachment=parse_with_intrinsic(text,types,subtypes)
    if attachment:return Definition(**base,abilities=attachment[0],attachment=attachment[1])
    normalized=text.replace(name,'this creature') if name else text
    if ',' in name:
        normalized=re.sub(r'\b'+re.escape(name.split(',')[0])+r"(?= enters| attacks| isn't a creature|\'s power)",'this creature',normalized)
    attack_lines=[line for line in normalized.splitlines() if line.startswith('Whenever this creature attacks')]
    other_lines=[line for line in normalized.splitlines() if not line.startswith('Whenever this creature attacks')]
    entry_program=compile_abilities('\n'.join(other_lines)) if other_lines else None
    attacks=compile_attacks('\n'.join(attack_lines)) if attack_lines else None
    if entry_program and attacks and 'Creature' in types and (not entry_program.devotion or 'Enchantment' in types):
        return Definition(**base,abilities=entry_program.keywords|attacks[0],triggers=entry_program.triggers,
            static_effects=entry_program.static_effects,activations=entry_program.activations,devotion=entry_program.devotion,
            crew=attacks[1],saddle=attacks[2],attack_effects=attacks[3])
    # An enchantment-sourced activated/triggered ability on the stack is a
    # distinct target from a spell. The entire second instruction is required.
    # Reminder text was already removed by rule_text().
    lines=text.splitlines()
    if len(lines)==2 and {'Creature','Enchantment'}<=types:
        ability=re.fullmatch(
            r'((?:\{(?:[0-9]{1,2}|[WUBRGC])\})+), \{T\}: Copy target activated or triggered ability you control '
            r'from an enchantment source\. You may choose new targets for the copy\.',lines[1])
        if ability:
            base_program=compile_abilities(lines[0],name)
            if base_program and base_program.static_effects and not (
                    base_program.triggers or base_program.activations or base_program.devotion):
                return Definition(**base,abilities=base_program.keywords,
                                  static_effects=base_program.static_effects,
                                  enchantment_copy_cost=ability[1])
    program = compile_abilities(text,name)
    # The entry-time choice grammar must match the permanent type named by Oracle.
    if program and program.chosen_type_entry and not any(
        f"As this {kind.lower()} enters, choose a creature type." in text
        for kind in ("Artifact", "Enchantment") if kind in types):
        program = None
    if program is not None and ("Creature" in types or "Enchantment" in types or "Artifact" in types):
        if program.devotion and not {'Creature','Enchantment'}<=types:
            return Definition(**base,abilities=frozenset(),supported=False,reason='Unsupported devotion type transition')
        return Definition(**base,abilities=program.keywords,triggers=program.triggers,static_effects=program.static_effects,
                          activations=program.activations,devotion=program.devotion,life_multiplier=program.life_multiplier,
                          opponent_creatures_enter_tapped=program.opponent_creatures_enter_tapped,
                          life_addition=program.life_addition,
            opponent_life_gain_becomes_loss=program.opponent_life_gain_becomes_loss,
            prevent_combat_damage_to_attackers=program.prevent_combat_damage_to_attackers,
            cost_reductions=program.cost_reductions,
                          counter_replacements=program.counter_replacements,token_replacements=program.token_replacements,
                          token_action_triggers=program.token_action_triggers,token_leave_triggers=program.token_leave_triggers,
                          entry_counter_grants=program.entry_counter_grants,attack_watchers=program.attack_watchers,
                          chosen_type_entry=program.chosen_type_entry)
    attack_text=text.replace(name,'this creature') if name else text
    if ',' in name:
        short=name.split(',')[0]
        attack_text=re.sub(r'\b'+re.escape(short)+r"(?= attacks|\'s power)",'this creature',attack_text)
    attack_program=compile_attacks(attack_text)
    if attack_program:
        keywords,crew,saddle,effects=attack_program
        if (crew is not None and 'Vehicle' not in subtypes) or (saddle is not None and 'Mount' not in subtypes):
            return Definition(**base,abilities=frozenset(),supported=False,reason='Activation/type mismatch')
        if 'Creature' in types or 'Vehicle' in subtypes:
            return Definition(**base,abilities=keywords,crew=crew,saddle=saddle,attack_effects=effects)
    if name == "Kolodin, Triumph Caster":
        valid = text == KOLODIN and "Creature" in types
        return Definition(**base, abilities=frozenset(), supported=valid,
                          reason="" if valid else "Kolodin metadata/rules mismatch")
    if name == "Zurgo Helmsmasher":
        valid = text == ZURGO and "Creature" in types
        return Definition(**base, abilities=frozenset({"haste"}), supported=valid,
                          reason="" if valid else "Zurgo metadata/rules mismatch")
    if name == "Andúril, Flame of the West":
        valid = text == ANDURIL and "Artifact" in types and "Equipment" in subtypes
        return Definition(**base, abilities=frozenset(), supported=valid,
                          reason="" if valid else "Andúril metadata/rules mismatch")
    if name == "Nested Shambler":
        valid = text == NESTED_SHAMBLER and "Creature" in types
        return Definition(**base, abilities=frozenset(), supported=valid,
                          reason="" if valid else name + " metadata/rules mismatch")
    if name == "Brightfield Mustang":
        valid = text == MUSTANG and "Creature" in types and "Mount" in subtypes
        return Definition(**base, abilities=frozenset(), saddle=1, supported=valid,
                          reason="" if valid else "Mustang metadata/rules mismatch")
    abilities, crew, saddle = set(), None, None
    for raw in re.split(r"[,\n]", text.lower()):
        line = raw.strip().removesuffix(".").strip()
        if not line: continue
        if line in SIMPLE_ABILITIES:
            abilities.add(line)
            continue
        match = re.fullmatch(r"(crew|saddle) ([1-9][0-9]*)", line)
        if match:
            if match[1] == "crew" and "Vehicle" in subtypes: crew = int(match[2])
            elif match[1] == "saddle" and "Mount" in subtypes: saddle = int(match[2])
            else: return Definition(**base, abilities=frozenset(), supported=False, reason="Keyword/type mismatch")
            continue
        return Definition(**base, abilities=frozenset(), supported=False,
                          reason="Unsupported ability: " + raw.strip())
    if not ("Creature" in types or "Vehicle" in subtypes or "Planeswalker" in types):
        return Definition(**base, abilities=frozenset(), supported=False, reason="Unsupported permanent type")
    return Definition(**base, abilities=frozenset(abilities), crew=crew, saddle=saddle)


@dataclass
class Permanent:
    id: str
    definition: Definition
    controller: int
    tapped: bool = False
    fresh: bool = True
    saddled: bool = False
    animated: bool = False
    attached_to: str | None = None
    counters: int = 0
    attacking: int | None = None
    token: bool = False
    temporary_power: int = 0
    temporary_toughness: int = 0
    temporary_abilities: frozenset[str] = frozenset()
    entered_at: int = 0
    attachment_at: int = 0
    lost_abilities: dict[str,int] = field(default_factory=dict)
    temporary_ability_times: dict[str,int] = field(default_factory=dict)
    loyalty: int | None = None
    charge_counters: int = 0
    chosen_subtype: str = ''
    keyword_counters: frozenset[str] = frozenset()


@dataclass
class Game:
    battlefield: dict[str, Permanent] = field(default_factory=dict)
    events: list[dict] = field(default_factory=list)
    questions: list[dict] = field(default_factory=list)
    turn_player: int = 0
    phase: str = "main"
    mana: dict[int, int] = field(default_factory=lambda: {0:0, 1:0})
    life_totals: dict[int, int] = field(default_factory=lambda: {0:40, 1:40})
    _next_token: int = 0
    clock: int = 0

    def timestamp(self):
        self.clock+=1
        return self.clock

    def lose_opposing_abilities(self,controller,abilities):
        timestamp=self.timestamp();affected=[]
        for permanent in self.battlefield.values():
            if permanent.controller==controller:continue
            for ability in abilities:permanent.lost_abilities[ability]=timestamp
            affected.append(permanent.id)
        return affected

    def grant_temporary(self,permanent,ability):
        permanent.temporary_abilities=permanent.temporary_abilities|{ability}
        permanent.temporary_ability_times[ability]=self.timestamp()

    def emit(self, kind: str, **data):
        self.events.append({"kind":kind, **data})

    def devotion(self, controller, symbol):
        # Hybrid/Phyrexian symbols contribute once when they contain this color.
        return sum(symbol in part.split('/') for permanent in self.battlefield.values() if permanent.controller==controller
                   for part in re.findall(r'\{([^}]+)\}',permanent.definition.mana_cost))

    def creature(self, p: Permanent) -> bool:
        if p.definition.station:return p.charge_counters>=p.definition.station[-1][0]
        if p.definition.devotion:
            symbol,threshold=p.definition.devotion
            if self.devotion(p.controller,symbol)<threshold:return False
        return "Creature" in p.definition.types or ("Vehicle" in p.definition.subtypes and p.animated)

    def static_effects(self,source):
        effects=list(source.definition.static_effects)
        for threshold,effect,_ in source.definition.station:
            if source.charge_counters>=threshold and effect:
                effects.extend(effect if isinstance(effect,tuple) else (effect,))
        return effects

    def protected(self,permanent,colors):
        return any(self.has(permanent,'protection from '+color.lower()) for color in colors)

    def stats(self, p: Permanent) -> tuple[int, int]:
        if not self.creature(p):
            raise IllegalAction("Permanent is not currently a creature")
        bonus = sum(1 for x in self.battlefield.values()
                    if x.definition.name == "Andúril, Flame of the West" and x.attached_to == p.id)
        power_bonus, toughness_bonus = p.temporary_power, p.temporary_toughness
        for source in self.battlefield.values():
            if source.attached_to==p.id and source.definition.attachment:
                power_bonus+=source.definition.attachment[3];toughness_bonus+=source.definition.attachment[4]
            if source.attached_to==p.id and source.definition.attachment_counter_scale:
                # Known counter kinds share the same physical permanent.
                count=p.counters+p.charge_counters+(p.loyalty or 0)
                power,toughness=source.definition.attachment_counter_scale
                power_bonus+=power*count;toughness_bonus+=toughness*count
            if source.attached_to==p.id and source.definition.attachment_scale:
                power,toughness,types=source.definition.attachment_scale
                count=sum(x.controller==source.controller and bool(set(types)&x.definition.types) for x in self.battlefield.values())
                power_bonus+=power*count;toughness_bonus+=toughness*count
            for effect in self.static_effects(source):
                if not matches(effect.subject,source,p,True): continue
                if effect.requires_attachment and not any(
                    item.attached_to==p.id and item.definition.attachment and
                    item.definition.attachment[0] in ('aura','equipment')
                    for item in self.battlefield.values()):continue
                if effect.life_min and self.life_totals.get(source.controller,0)<effect.life_min:continue
                if effect.condition and not any(matches(effect.condition,source,x,self.creature(x)) for x in self.battlefield.values()): continue
                if effect.share_types:
                    multiplier=sum(other.id!=p.id and self.creature(other)
                                   and bool(p.definition.subtypes & other.definition.subtypes)
                                   for other in self.battlefield.values())
                else:
                    multiplier = (sum(matches(effect.count,source,x,self.creature(x)) for x in self.battlefield.values())
                                  if effect.count else 1)
                power_bonus += effect.power * multiplier
                toughness_bonus += effect.toughness * multiplier
        base_power,base_toughness=p.definition.power,p.definition.toughness
        if p.definition.self_artifact_enchantment_scale:
            count=sum(other.controller==p.controller and bool(
                {'Artifact','Enchantment'}&other.definition.types)
                for other in self.battlefield.values())
            dp,dt=p.definition.self_artifact_enchantment_scale
            base_power+=dp*count;base_toughness+=dt*count
        if p.definition.dynamic_pt_color:
            count=sum(x.controller==p.controller and p.definition.dynamic_pt_color in x.definition.colors
                      for x in self.battlefield.values())
            base_power=base_toughness=count
        return (base_power + p.counters + 3*bonus + power_bonus,
                base_toughness + p.counters + bonus + toughness_bonus)

    def ward_costs(self,p):
        granted=tuple(effect.ward_cost for source in self.battlefield.values() for effect in self.static_effects(source)
                     if effect.ward_cost and matches(effect.subject,source,p,self.creature(p)))
        roles=tuple('{1}' for source in self.battlefield.values()
                    if source.attached_to==p.id and source.definition.role=='Royal')
        return granted+roles

    def has(self, p: Permanent, ability: str) -> bool:
        # "Can't have or gain" is a continuous prohibition: even a later
        # Aura, equipment or temporary grant cannot restore the keyword.
        for source in self.battlefield.values():
            if any(effect.suppress==ability and
                   matches(effect.subject,source,p,self.creature(p))
                   for effect in self.static_effects(source)):
                return False
        grants=[]
        if any(p.charge_counters>=threshold and ability in keywords for threshold,_,keywords in p.definition.station):grants.append(p.entered_at)
        if ability in p.definition.abilities:grants.append(p.entered_at)
        if ability in p.keyword_counters:grants.append(p.entered_at)
        if ability in p.temporary_abilities:grants.append(p.temporary_ability_times.get(ability,p.entered_at))
        for source in self.battlefield.values():
            stamp=max(source.entered_at,source.attachment_at)
            if source.attached_to==p.id and source.definition.attachment and ability in source.definition.attachment[2]:
                grants.append(stamp)
            if any(effect.grant==ability and matches(effect.subject,source,p,self.creature(p))
                   and (not effect.requires_attachment or any(
                       item.attached_to==p.id and item.definition.attachment and
                       item.definition.attachment[0] in ('aura','equipment')
                       for item in self.battlefield.values()))
                   and (not effect.life_min or self.life_totals.get(source.controller,0)>=effect.life_min)
                   and (not effect.condition or any(matches(effect.condition,source,other,self.creature(other)) for other in self.battlefield.values()))
                   for effect in self.static_effects(source)):grants.append(stamp)
        if ability=='indestructible' and p.definition.name=='Zurgo Helmsmasher' and p.controller==self.turn_player:
            grants.append(p.entered_at)
        if ability=='haste' and ({'Mount','Vehicle'} & p.definition.subtypes):
            grants.extend(x.entered_at for x in self.battlefield.values() if x.controller==p.controller and x.definition.name=='Kolodin, Triumph Caster')
        return bool(grants) and max(grants)>p.lost_abilities.get(ability,-1)

    def must_attack(self, permanent):
        """Only an eligible creature can be required; the caller checks eligibility."""
        return self.creature(permanent) and (self.has(permanent,'must_attack') or permanent.definition.name=='Zurgo Helmsmasher' or any(
            effect.must_attack and matches(effect.subject,source,permanent,True)
            for source in self.battlefield.values() for effect in self.static_effects(source)))

    def enchanted(self, permanent):
        return any(p.attached_to==permanent.id and 'Enchantment' in p.definition.types
                   and 'Aura' in p.definition.subtypes for p in self.battlefield.values())

    def role_trigger(self, source):
        return dict(operation='create_role',effect='create Virtuous Role',role='Virtuous',
                    source=source.id,name=source.definition.name,controller=source.controller,
                    sourceColors=sorted(source.definition.colors))

    def aura_damage_triggers(self, dealt: list[dict], player_target: int) -> list[dict]:
        """Snapshot positive damage by enchanted sources before any sources die.

        Each Aura creates one trigger per simultaneous damage event. The Aura
        controller receives its own life/draw even when the host is controlled
        by another player. Keen-Sense-style opponents are relative to the Aura.
        """
        events=[]
        for aura in self.battlefield.values():
            if not aura.definition.damage_events or aura.attached_to not in self.battlefield:continue
            damage=[d for d in dealt if d['source']==aura.attached_to and d['amount']>0]
            if not damage:continue
            for rule in aura.definition.damage_events:
                if rule=='gain_damage':
                    amount=sum(d['amount'] for d in damage)
                    if amount:events.append(dict(operation='gain_life',effect='gain life equal to damage',
                        controller=aura.controller,source=aura.id,name=aura.definition.name,amount=amount))
                elif rule=='optional_draw_opponent':
                    players={player_target for d in damage if d['target'] is None and player_target!=aura.controller}
                    for opponent in sorted(players):
                        events.append(dict(operation='draw_cards',effect='may draw a card',optional=True,
                            controller=aura.controller,source=aura.id,name=aura.definition.name,amount=1,target=opponent))
                else:raise NeedsRules('Unknown Aura damage trigger')
        return events

    def combat_draw_triggers(self, identifier):
        creature=self.battlefield[identifier];result=[]
        for source in self.battlefield.values():
            if source.definition.enchanted_draw and source.controller==creature.controller and self.enchanted(creature):
                result.append(dict(operation='draw_cards',effect='draw a card',amount=1,controller=source.controller,
                                   source=source.id,name=source.definition.name,optional=False))
            if source.definition.attachment_draw and source.attached_to==identifier:
                # This Aura grants an ability to the creature; that creature's
                # controller controls its trigger, even across control changes.
                result.append(dict(operation='draw_cards',effect='draw a card',amount=1,controller=creature.controller,
                                   source=identifier,name=creature.definition.name,optional=True))
        return result

    def enter(self, permanent: Permanent):
        self.enter_batch([permanent])

    def enter_batch(self, permanents):
        if len({p.id for p in permanents})!=len(permanents):raise IllegalAction('Duplicate permanent ID')
        for permanent in permanents:
            if permanent.id in self.battlefield: raise IllegalAction("Duplicate permanent ID")
            if permanent.definition.entry_keyword_choices and (len(permanent.keyword_counters)!=1 or
                    not permanent.keyword_counters <= frozenset(permanent.definition.entry_keyword_choices)):
                raise NeedsRules('Legal keyword-counter choice required before entry')
            if permanent.definition.chosen_type_entry and not permanent.chosen_subtype:
                raise NeedsRules('Creature-type choice required before entry')
            if not permanent.definition.supported:
                self.questions.append({"card":permanent.definition.name, "blocking":True,
                    "reason":permanent.definition.reason,
                    "question":"How should this ability be implemented and tested: " + permanent.definition.reason + "?"})
                raise NeedsRules(permanent.definition.reason)
        # Entry replacements must exist on the battlefield before the event;
        # two permanents entering simultaneously cannot apply replacements
        # granted by either of the entering permanents.
        incumbents=tuple(self.battlefield.values())
        entry_counters={}
        for permanent in permanents:
            if 'Creature' in permanent.definition.types and any(
                source.controller!=permanent.controller and source.definition.opponent_creatures_enter_tapped
                for source in incumbents):permanent.tapped=True
            if 'Creature' in permanent.definition.types:
                bonus=sum(amount for source in incumbents
                          for selector,amount in source.definition.entry_counter_grants
                          if matches(selector,source,permanent,True))
                if bonus:entry_counters[permanent.id]=bonus
            permanent.entered_at=self.timestamp()
            if 'Planeswalker' in permanent.definition.types and permanent.loyalty is None:permanent.loyalty=permanent.definition.loyalty
            if permanent.attached_to:permanent.attachment_at=permanent.entered_at
            self.battlefield[permanent.id]=permanent
        # Enter-with counters are replacement effects, not delayed ETB triggers.
        # Use only pre-existing sources, never another simultaneous entrant.
        for permanent in permanents:
            bonus=entry_counters.get(permanent.id,0)
            if bonus:
                permanent.counters+=self.counter_amount(permanent.id,bonus,sources=incumbents)
        for permanent in permanents:
            self.emit("enters", id=permanent.id, name=permanent.definition.name,
                      controller=permanent.controller, types=sorted(permanent.definition.types),
                      subtypes=sorted(permanent.definition.subtypes))
            if 'enters' in permanent.definition.role_events:
                self.emit('trigger',**self.role_trigger(permanent))
            if permanent.definition.aura_exile:
                self.emit('trigger',operation='exile_until_aura_leaves',
                          source=permanent.id,name=permanent.definition.name,
                          controller=permanent.controller,sourceEntry=permanent.entered_at,
                          sourceColors=sorted(permanent.definition.colors))
            if permanent.definition.linked_exile:
                self.emit('trigger',operation='linked_exile_entry',
                          source=permanent.id,name=permanent.definition.name,
                          controller=permanent.controller,sourceEntry=permanent.entered_at,
                          targetRestriction=permanent.definition.linked_exile)
            if permanent.definition.living_weapon:
                self.emit('trigger',operation='living_weapon',
                          source=permanent.id,name=permanent.definition.name,
                          controller=permanent.controller,sourceEntry=permanent.entered_at)
            if permanent.definition.entry_attachment_counters and permanent.attached_to:
                self.emit('trigger',operation='enchanted_counters',effect='put counters on enchanted creature',
                          source=permanent.id,name=permanent.definition.name,controller=permanent.controller,
                          amount=permanent.definition.entry_attachment_counters)
            for watcher in list(self.battlefield.values()):
                if (watcher.definition.modal_role_choices
                        and watcher.controller==permanent.controller
                        and self.creature(permanent)
                        and (not permanent.token or watcher.id==permanent.id)):
                    self.emit('trigger',operation='create_chosen_role',
                        effect='create chosen Role attached to entering creature',
                        source=watcher.id,name=watcher.definition.name,
                        controller=watcher.controller,entering=permanent.id,
                        roleOptions=list(watcher.definition.modal_role_choices))
                for trigger in watcher.definition.triggers:
                    if trigger.event == "enters" and matches(trigger.subject,watcher,permanent,self.creature(permanent)):
                        self.emit("trigger",**event_data(trigger,watcher,permanent))
            # These are triggered abilities, modeled as immediate resolutions in this
            # focused prototype. The full engine must provide stack/priority.
            watched = any(x.id != permanent.id and x.controller == permanent.controller
                          and x.definition.name == "Kolodin, Triumph Caster"
                          for x in self.battlefield.values())
            if watched and "Mount" in permanent.definition.subtypes:
                permanent.saddled = True
                self.emit("trigger", source="Kolodin, Triumph Caster", effect="saddled", target=permanent.id)
            if watched and "Vehicle" in permanent.definition.subtypes:
                permanent.animated = True
                self.emit("trigger", source="Kolodin, Triumph Caster", effect="animated", target=permanent.id)


    def cast_triggers(self, spell, controller: int) -> list[dict]:
        """Gather spell-cast triggers at cast time, before the spell can resolve.

        The caller puts these above the spell on the priority stack. They remain
        independent even if the spell or the triggering permanent later leaves.
        """
        result=[]
        for watcher in self.battlefield.values():
            for trigger in watcher.definition.triggers:
                if cast_matches(trigger,watcher,spell,controller):
                    result.append(event_data(trigger,watcher,spell))
        return result

    def life_gain_triggers(self, controller: int, gained: int) -> list[dict]:
        """Snapshot one trigger per life-gain EVENT, never per life point.

        Trigger discovery happens after replacements have changed the amount.
        In particular, life lost is not life gained, and zero gain is no event.
        """
        if gained<=0:return []
        result=[]
        for source in self.battlefield.values():
            if source.controller!=controller:continue
            for trigger in source.definition.triggers:
                if trigger.event=='gain_life':
                    result.append(event_data(trigger,source,source))
        return result

    def upkeep_triggers(self, land_counts=None) -> list[dict]:
        """One trigger per eligible controlled permanent at upkeep start.

        Lands represented by the simulator's separate mana-permanent layer
        must be supplied by its controller, not inferred from this kernel.
        """
        land_counts=land_counts or {}
        triggers = []
        for p in self.battlefield.values():
            rule=p.definition.upkeep_token_rule
            if rule and (rule[0]=='each' or p.controller==self.turn_player):
                if rule[1]!='enchanted' or self.enchanted(p):
                    from dataclasses import asdict
                    triggers.append(dict(operation='upkeep_token_rule',effect='conditional upkeep tokens',
                        source=p.id,name=p.definition.name,controller=p.controller,event='upkeep',
                        condition=rule[1],countSubtype=rule[2],divisor=rule[3],
                        tokenSpec=dict(asdict(rule[4]),keywords=sorted(rule[4].keywords))))
            if p.controller != self.turn_player: continue
            if p.definition.upkeep_attachment_counters and p.attached_to in self.battlefield:
                triggers.append(dict(operation='enchanted_counters',effect='put counters on enchanted creature',
                    source=p.id,name=p.definition.name,controller=p.controller,
                    amount=p.definition.upkeep_attachment_counters))
            if p.definition.double_attachment_counters_upkeep and p.attached_to in self.battlefield:
                triggers.append(dict(operation='enchanted_double_counters',effect='double enchanted counters',
                    source=p.id,name=p.definition.name,controller=p.controller))
            for trigger in p.definition.triggers:
                if trigger.event == "upkeep":
                    if (trigger.lands_controlled_at_least and
                            land_counts.get(p.controller,0)<trigger.lands_controlled_at_least):
                        continue
                    triggers.append(event_data(trigger,p,p))
        return triggers

    def begin_combat_triggers(self) -> list[dict]:
        """Snapshot controlled beginning-of-combat abilities before attackers are chosen."""
        return [event_data(trigger,source,source)
                for source in self.battlefield.values() if source.controller==self.turn_player
                for trigger in source.definition.triggers if trigger.event=='begin_combat']

    def controlled_creature_above_base(self, controller: int) -> bool:
        # Current power includes counters and live continuous effects.
        return any(p.controller==controller and self.creature(p)
                   and self.stats(p)[0]>p.definition.power for p in self.battlefield.values())

    def end_step_triggers(self, life_gained: int) -> list[dict]:
        """Check gained-life conditions at the beginning of the end step only.

        Net life change is not a substitute for amount gained; sources can
        lose life and gain life in the same turn.
        """
        triggers=[]
        for permanent in self.battlefield.values():
            if permanent.controller!=self.turn_player:continue
            for ability in permanent.definition.triggers:
                if ability.event!='end_step' or life_gained<ability.life_gained_at_least:continue
                if ability.power_above_base_required and not self.controlled_creature_above_base(permanent.controller):continue
                triggers.append(event_data(ability,permanent,permanent))
        return triggers

    def death_triggers(self, ids: list[str]) -> list[dict]:
        """Inspect the battlefield immediately before one simultaneous death event.

        This is only the trigger discovery step, not stack placement or resolution.
        The caller must actually move all the affected creatures to a graveyard.
        """
        if len(ids) != len(set(ids)) or any(i not in self.battlefield for i in ids):
            raise IllegalAction("Invalid simultaneous death event")
        dead = [self.battlefield[i] for i in ids]
        if any(not self.creature(p) for p in dead):
            raise IllegalAction("Death trigger batch requires creatures")
        triggers = []
        for creature in dead:
            if creature.definition.name == "Nested Shambler":
                triggers.append({"source":creature.id,"name":"Nested Shambler","controller":creature.controller,
                                 "dead":creature.id,"effect":"create tapped Squirrels",
                                 "amount":max(0,self.stats(creature)[0])})
        for watcher in self.battlefield.values():
            for trigger in watcher.definition.triggers:
                for creature in dead:
                    if trigger.event == "dies" and matches(trigger.subject,watcher,creature,True):
                        event=event_data(trigger,watcher,creature)
                        if trigger.effect.operation=='damage_any_target':
                            # The source may leave before the trigger resolves. Preserve LKI.
                            event.update(lastLifelink=self.has(watcher,'lifelink'),
                                         lastDeathtouch=self.has(watcher,'deathtouch'))
                        triggers.append(event)
        return triggers

    def leave(self, permanent_id: str):
        p = self.battlefield.pop(permanent_id)
        for item in self.battlefield.values():
            if item.attached_to == permanent_id: item.attached_to = None
        self.emit("leaves", id=p.id, name=p.definition.name)

    def _tappers(self, permanent_id: str, ids: list[str], required: int):
        if len(set(ids)) != len(ids): raise IllegalAction("A creature cannot be tapped twice")
        if permanent_id in ids: raise IllegalAction("Crew and saddle require other creatures")
        creatures = []
        for identifier in ids:
            p = self.battlefield.get(identifier)
            if p is None or p.controller != self.battlefield[permanent_id].controller or p.tapped or not self.creature(p):
                raise IllegalAction("Crew/saddle requires untapped creatures you control")
            creatures.append(p)
        if sum(self.stats(p)[0]+p.definition.pilot_bonus for p in creatures) < required:
            raise IllegalAction("Insufficient total power")
        return creatures

    def crew(self, vehicle_id: str, ids: list[str], actor: int):
        v = self.battlefield[vehicle_id]
        if v.controller != actor or v.definition.crew is None: raise IllegalAction("No crew ability")
        tappers = self._tappers(vehicle_id, ids, v.definition.crew)
        for p in tappers: p.tapped = True
        v.animated = True
        self.emit("crew", target=vehicle_id, tappers=ids)

    def saddle(self, mount_id: str, ids: list[str], actor: int):
        mount = self.battlefield[mount_id]
        if actor != self.turn_player or self.phase != "main":
            raise IllegalAction("Saddle only as a sorcery")
        if mount.controller != actor or mount.definition.saddle is None or not self.creature(mount):
            raise IllegalAction("No saddle ability")
        tappers = self._tappers(mount_id, ids, mount.definition.saddle)
        for p in tappers: p.tapped = True
        mount.saddled = True
        self.emit("saddle", target=mount_id, tappers=ids)

    def equip(self, equipment_id: str, creature_id: str, actor: int):
        if actor != self.turn_player or self.phase != "main":
            raise IllegalAction("Equip only as a sorcery")
        equipment = self.battlefield[equipment_id]
        target = self.battlefield[creature_id]
        if equipment.controller != actor or equipment.definition.name != "Andúril, Flame of the West":
            raise IllegalAction("Equipment not controlled or unsupported")
        if target.controller != actor or not self.creature(target):
            raise IllegalAction("Equip requires a creature you control")
        if self.mana[actor] < 2: raise IllegalAction("Equip costs two generic mana")
        self.mana[actor] -= 2
        if equipment.attached_to!=target.id:
            equipment.attached_to = target.id
            equipment.attachment_at=self.timestamp()
        self.emit("equip", equipment=equipment_id, target=creature_id, mana=2)

    def token_leave_events(self, controller: int, count: int) -> list[dict]:
        """Snapshot watchers when controlled tokens leave, by any means."""
        if count<=0:return []
        result=[]
        for source in self.battlefield.values():
            if source.controller!=controller:continue
            for kind,loss,gain in source.definition.token_leave_triggers:
                if kind!='opponent_loss_gain':raise NeedsRules('Unknown token-leaves trigger')
                result.extend(dict(operation='lose_life',source=source.id,
                    name=source.definition.name,controller=source.controller,
                    amount=loss,gain=gain,effect='token leaves battlefield') for _ in range(count))
        return result

    def token_action_events(self, action: str, controller: int, count: int) -> list[dict]:
        """A separate stack trigger for each token actually created or sacrificed.

        Snapshot live sources now, so their queued abilities survive a later
        departure from the battlefield. Mere token death/exile is not a
        sacrifice, and replacement effects are counted before this event.
        """
        if action not in ('create','sacrifice') or count<=0:return []
        result=[]
        for source in self.battlefield.values():
            if source.controller!=controller:continue
            for watched,kind,amount in source.definition.token_action_triggers:
                if watched!=action:continue
                if kind!='opponent_loss':raise NeedsRules('Unsupported token-action trigger')
                result.extend(dict(operation='lose_life',source=source.id,
                    name=source.definition.name,controller=source.controller,amount=amount,
                    effect='opponent loses life from token action',tokenAction=action)
                    for _ in range(count))
        return result

    def token_amount(self, controller: int, amount: int, *, by_effect: bool = True) -> int:
        """Apply token replacements to one positive token-creation event.

        The number is calculated once per event before tokens are created.
        Doubling Season is effect-only and controller-scoped; Primal Vigor
        applies regardless of which player would create the tokens.
        """
        if amount<=0:return max(0,amount)
        for source in self.battlefield.values():
            for kind,value,scope,condition in source.definition.token_replacements:
                if scope=='controlled' and source.controller!=controller:continue
                if condition=='effect' and not by_effect:continue
                if kind=='creature_as':continue  # Characteristics are replaced separately.
                if kind!='double':raise NeedsRules('Unknown token replacement')
                amount*=value
        return amount

    def replace_creature_token_spec(self, controller: int, spec: dict) -> dict:
        """Apply token-characteristic replacements to a single creation event.

        The token count is handled by token_amount; changing a token's
        characteristics must not mutate its source template or make an
        opponent's tokens into Angels. A noncreature token is not affected.
        """
        result=dict(spec)
        if result.get('creature',True) is False:return result
        for source in self.battlefield.values():
            for kind,value,scope,condition in source.definition.token_replacements:
                if kind!='creature_as':continue
                if scope=='controlled' and source.controller!=controller:continue
                if condition not in ('any','effect'):raise NeedsRules('Unknown token replacement condition')
                result.update(value)
                result['land']=False
                result['enchantment']=False
                result['contribution_bonus']=0
        return result

    def counter_amount(self, target_id: str, amount: int, *,
                       counter_type: str = '+1/+1', by_effect: bool = True, sources=None) -> int:
        """Apply counters replacement effects to a single counter-placement event.

        +1/+1 counters and all-counter permanent effects have different
        scopes. Additional counters apply before doubling in the diagnostic
        policy; an agent can later choose another legal ordering.
        """
        if amount<=0:return max(0,amount)
        target=self.battlefield[target_id]
        creature=self.creature(target)
        additions=[];multipliers=[]
        for source in (self.battlefield.values() if sources is None else sources):
            for replacement in source.definition.counter_replacements:
                kind,value,scope=replacement[:3]
                condition=replacement[3] if len(replacement)>3 else 'any'
                if condition=='effect' and not by_effect:continue
                if scope in ('controlled_creature','controlled_permanent','controlled_subtypes') and source.controller!=target.controller:continue
                if scope=='controlled_subtypes' and not set(replacement[4]).intersection(target.definition.subtypes):continue
                if scope in ('controlled_creature','any_creature') and not creature:continue
                if scope!='controlled_permanent' and counter_type!='+1/+1':continue
                if kind not in ('plus','double'):raise NeedsRules('Unknown counter replacement')
                (additions if kind=='plus' else multipliers).append(value)
        for value in additions:amount+=value
        for value in multipliers:amount*=value
        return amount

    def attack(self, attacker_id: str, defending_player: int, defer=False):
        a = self.battlefield[attacker_id]
        if self.phase != "combat" or a.controller != self.turn_player or defending_player not in (0,1) or defending_player == a.controller:
            raise IllegalAction("Attacker/defender or phase invalid")
        if not self.creature(a) or a.tapped or self.has(a,"defender") or a.fresh and not self.has(a,"haste"):
            raise IllegalAction("Creature cannot attack")
        if not self.has(a,"vigilance"): a.tapped = True
        a.attacking = defending_player
        self.emit("attacks", id=a.id, defending=defending_player)
        if self.has(a,'flying'):
            for source in tuple(self.battlefield.values()):
                for relation,operation,amount in source.definition.attack_watchers:
                    if relation=='controller_defending' and source.controller!=defending_player:continue
                    self.emit('trigger',operation=operation,source=source.id,
                              name=source.definition.name,controller=source.controller,
                              target=a.id,amount=amount,
                              sourceColors=sorted(source.definition.colors),
                              effect=('remove flying from attacker' if operation=='attacker_loses_flying'
                                      else 'damage the attacking flying creature'))
        if 'attacks' in a.definition.role_events:
            self.emit('trigger',**self.role_trigger(a))
        # A Sorcerer Role grants the enchanted CREATURE an attack trigger.
        # It is independent of the Aura after triggering and uses that creature's controller.
        for aura in self.battlefield.values():
            if aura.attached_to==a.id and aura.definition.role=='Sorcerer':
                self.emit('trigger',operation='scry',effect='scry 1 from Sorcerer Role',
                          source=a.id,name=a.definition.name,controller=a.controller,amount=1)
        for operation,power,toughness,keyword in a.definition.attack_effects:
            if operation=='counter' and defer:
                self.emit('trigger',operation='self_counter',source=a.id,name=a.definition.name,controller=a.controller,effect='add counter',amount=power)
            elif operation=='counter':
                a.counters+=self.counter_amount(a.id,power)
                self.emit('trigger',source=a.id,effect='add +1/+1 counter',target=a.id)
            elif operation=='counter_power_tokens':
                last_power=self.stats(a)[0]
                if not defer: a.counters+=self.counter_amount(a.id,power)
                amount=max(0,self.stats(a)[0])
                spec=dict(asdict(keyword),amount=amount,keywords=sorted(keyword.keywords))
                self.emit('trigger',source=a.id,name=a.definition.name,controller=a.controller,
                          operation='counter_power_tokens' if defer else 'create_tokens',
                          counterAmount=power,lastPower=last_power,
                          effect='counter then create tokens equal to power',tokenSpec=spec)
            elif operation=='greatest_power_boost':
                if not defer:
                    amount=max((self.stats(other)[0] for other in self.battlefield.values()
                                if other.controller==a.controller and self.creature(other)),default=0)
                    a.temporary_power+=power*amount
                    a.temporary_toughness+=toughness*amount
                self.emit('trigger',source=a.id,name=a.definition.name,controller=a.controller,
                          operation='greatest_power_boost',effect='boost by greatest controlled power at resolution',
                          power=power,toughness=toughness)
            elif operation=='subtype_count_boost':
                count=sum(other.id!=a.id and other.controller==a.controller and keyword in other.definition.subtypes
                          for other in self.battlefield.values())
                if not defer:a.temporary_power+=power*count;a.temporary_toughness+=toughness*count
                self.emit('trigger',source=a.id,name=a.definition.name,controller=a.controller,target=a.id,
                    operation='subtype_count_boost',effect='temporary boost per controlled subtype',
                    power=power,toughness=toughness,subtype=keyword)
            elif operation=='attacking_subtype_boost':
                count=sum(other.id!=a.id and other.attacking is not None and
                          self.creature(other) and keyword in other.definition.subtypes
                          for other in self.battlefield.values())
                if not defer:
                    a.temporary_power+=power*count
                    a.temporary_toughness+=toughness*count
                self.emit('trigger',source=a.id,name=a.definition.name,controller=a.controller,
                          target=a.id,operation='attacking_subtype_boost',
                          effect='temporary bonus for each other attacking creature of a subtype',
                          power=power,toughness=toughness,subtype=keyword)
            elif operation=='attack_target_keywords':
                # Choose legal targets at trigger placement; later recheck at resolution.
                candidates=[other for other in self.battlefield.values()
                            if other.controller==a.controller and self.creature(other)
                            and other.definition.legendary==bool(power)
                            and not self.has(other,'shroud')
                            and not self.protected(other,a.definition.colors)]
                if candidates:
                    target=min(candidates,key=lambda other:other.id)
                    if not defer:
                        for ability in keyword:self.grant_temporary(target,ability)
                    self.emit('trigger',operation='grant_target_keywords',source=a.id,
                              name=a.definition.name,controller=a.controller,target=target.id,
                              legendary=bool(power),keywords=list(keyword),
                              sourceColors=sorted(a.definition.colors),
                              effect='grant keywords to a targeted controlled creature')
            elif operation=='attack_team_keywords':
                if defer:
                    self.emit('trigger',operation='grant_team_keywords',source=a.id,name=a.definition.name,
                              controller=a.controller,keywords=list(keyword),
                              effect='grant team combat keywords until end of turn')
                else:
                    for member in self.battlefield.values():
                        if member.controller==a.controller and self.creature(member):
                            for ability in keyword:self.grant_temporary(member,ability)
                    self.emit('trigger',source=a.id,effect='grant team keywords until end of turn',
                              keywords=list(keyword))
            elif operation=='saddled_boost' and a.saddled and defer:
                self.emit('trigger',operation='saddled_boost',source=a.id,name=a.definition.name,controller=a.controller,effect='saddled boost',power=power,toughness=toughness,keyword=keyword)
            elif operation=='saddled_boost' and a.saddled:
                a.temporary_power+=power;a.temporary_toughness+=toughness
                self.grant_temporary(a,keyword)
                self.emit('trigger',source=a.id,effect=f'+{power}/+{toughness} and {keyword} until end of turn',target=a.id)
        if a.definition.name == "Brightfield Mustang" and a.saddled:
            a.tapped = False
            a.counters += self.counter_amount(a.id,1)
            self.emit("trigger", source=a.id, effect="untap and add +1/+1 counter", target=a.id)
        # The controller of Equipment controls its attack trigger, even when
        # another player controls the equipped creature. It survives source removal.
        for equipment in tuple(self.battlefield.values()):
            if equipment.attached_to==a.id and equipment.definition.equipment_basic_search:
                self.emit('trigger',operation='equipment_basic_search',source=equipment.id,
                          name=equipment.definition.name,controller=equipment.controller,
                          effect='optional tapped basic-land search on equipped attack')
        # Tokens enter tapped; they do not trigger 'whenever this attacks' abilities.
        for equipment in list(self.battlefield.values()):
            if equipment.definition.name != "Andúril, Flame of the West" or equipment.attached_to != a.id:
                continue
            attacking = defending_player if a.definition.legendary and equipment.controller == a.controller else None
            if defer:
                self.emit('trigger',operation='create_tokens',source=equipment.id,name=equipment.definition.name,controller=equipment.controller,effect='two Spirits',tokenSpec=dict(amount=2,power=1,toughness=1,colors=['White'],subtypes=['Spirit'],keywords=['flying'],tapped=True,attacking=attacking is not None))
                continue
            ids = []
            spec=self.replace_creature_token_spec(equipment.controller,dict(
                power=1,toughness=1,colors=('White',),subtypes=('Spirit',),
                keywords=('flying',),tapped=True))
            for _ in range(self.token_amount(equipment.controller,2)):
                self._next_token += 1
                token_id = f"spirit-token-{self._next_token}"
                token = Definition(' '.join(spec['subtypes']),frozenset({'Creature'}),
                    frozenset(spec['subtypes']),False,spec['power'],spec['toughness'],
                    frozenset(spec['keywords']),colors=frozenset(spec['colors']))
                self.enter(Permanent(token_id,token,equipment.controller,tapped=True,attacking=attacking,token=True))
                ids.append(token_id)
            self.emit("trigger", source=equipment.id, effect="two tapped flying Spirit tokens",
                      tokens=ids, attacking=attacking)

    def cleanup(self):
        for p in self.battlefield.values():
            p.temporary_power=p.temporary_toughness=0
            p.temporary_abilities=frozenset()
            p.temporary_ability_times.clear();p.lost_abilities.clear()
            p.saddled = False
            p.animated = False
            p.attacking = None
        # An Equipment cannot remain attached to a Vehicle after it ceases to be a creature.
        for p in self.battlefield.values():
            target = self.battlefield.get(p.attached_to) if p.attached_to else None
            if target is not None and not self.creature(target):
                p.attached_to = None
        self.emit("cleanup")
