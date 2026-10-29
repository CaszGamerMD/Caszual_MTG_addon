"""Experimental event/continuous-effect kernel for a small set of real cards.

This is an isolated rules prototype: it does not implement priority, the stack,
combat damage, costs for casting spells, or the full turn simulator. Unknown
rules raise NeedsRules rather than being treated as blank.
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
import re
from attachments import parse as parse_attachment, parse_bestow, parse_equipment_removals
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
                    "trample", "haste", "defender", "reach", "deathtouch", "indestructible", "hexproof", "menace"}


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
    damage_events: tuple = ()
    life_multiplier: int = 1
    opponent_creatures_enter_tapped: bool = False
    life_addition: int = 0
    cost_reductions: tuple = ()
    counter_replacements: tuple = ()
    role: str = ""


def parse_card(card: dict) -> Definition:
    name = card.get("name", "")
    types = frozenset(card.get("types") or [])
    subtypes = frozenset(card.get("subTypes") or [])
    text = rule_text(card.get("oracleText") or "")
    try:
        power, toughness = int(card.get("power") or 0), int(card.get("toughness") or 0)
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
    if ("Creature" in types or "Vehicle" in subtypes or "Spacecraft" in subtypes) and any(card.get(stat) in (None, "") for stat in ("power", "toughness")):
        return Definition(**base, abilities=frozenset(), supported=False, reason="Missing or invalid fixed power/toughness")
    from enchantment_abilities import compile as compile_enchantments
    enchantments=compile_enchantments(text,name,types,subtypes)
    if enchantments:
        program=enchantments.base
        return Definition(**base,abilities=program.keywords,triggers=program.triggers,
            static_effects=program.static_effects,activations=program.activations,devotion=program.devotion,
            attachment=enchantments.attachment,attachment_scale=enchantments.scale,
            role_events=enchantments.role_events,enchanted_draw=enchantments.enchanted_draw,
            attachment_draw=enchantments.attachment_draw,damage_events=enchantments.damage_events,
            life_multiplier=program.life_multiplier,
            opponent_creatures_enter_tapped=program.opponent_creatures_enter_tapped,
            life_addition=program.life_addition,cost_reductions=program.cost_reductions,
            counter_replacements=program.counter_replacements)
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
    attachment=parse_attachment(text,types,subtypes)
    if attachment:return Definition(**base,abilities=frozenset(),attachment=attachment)
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
    program = compile_abilities(text,name)
    if program is not None and ("Creature" in types or "Enchantment" in types or "Artifact" in types):
        if program.devotion and not {'Creature','Enchantment'}<=types:
            return Definition(**base,abilities=frozenset(),supported=False,reason='Unsupported devotion type transition')
        return Definition(**base,abilities=program.keywords,triggers=program.triggers,static_effects=program.static_effects,
                          activations=program.activations,devotion=program.devotion,life_multiplier=program.life_multiplier,
                          opponent_creatures_enter_tapped=program.opponent_creatures_enter_tapped,
                          life_addition=program.life_addition,cost_reductions=program.cost_reductions,
                          counter_replacements=program.counter_replacements)
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
            if source.attached_to==p.id and source.definition.attachment_scale:
                power,toughness,types=source.definition.attachment_scale
                count=sum(x.controller==source.controller and bool(set(types)&x.definition.types) for x in self.battlefield.values())
                power_bonus+=power*count;toughness_bonus+=toughness*count
            for effect in self.static_effects(source):
                if not matches(effect.subject,source,p,True): continue
                if effect.life_min and self.life_totals.get(source.controller,0)<effect.life_min:continue
                if effect.condition and not any(matches(effect.condition,source,x,self.creature(x)) for x in self.battlefield.values()): continue
                multiplier = (sum(matches(effect.count,source,x,self.creature(x)) for x in self.battlefield.values())
                              if effect.count else 1)
                power_bonus += effect.power * multiplier
                toughness_bonus += effect.toughness * multiplier
        return (p.definition.power + p.counters + 3*bonus + power_bonus,
                p.definition.toughness + p.counters + bonus + toughness_bonus)

    def ward_costs(self,p):
        return tuple(effect.ward_cost for source in self.battlefield.values() for effect in self.static_effects(source)
                     if effect.ward_cost and matches(effect.subject,source,p,self.creature(p)))

    def has(self, p: Permanent, ability: str) -> bool:
        grants=[]
        if any(p.charge_counters>=threshold and ability in keywords for threshold,_,keywords in p.definition.station):grants.append(p.entered_at)
        if ability in p.definition.abilities:grants.append(p.entered_at)
        if ability in p.temporary_abilities:grants.append(p.temporary_ability_times.get(ability,p.entered_at))
        for source in self.battlefield.values():
            stamp=max(source.entered_at,source.attachment_at)
            if source.attached_to==p.id and source.definition.attachment and ability in source.definition.attachment[2]:
                grants.append(stamp)
            if any(effect.grant==ability and matches(effect.subject,source,p,self.creature(p))
                   and (not effect.life_min or self.life_totals.get(source.controller,0)>=effect.life_min)
                   and (not effect.condition or any(matches(effect.condition,source,other,self.creature(other)) for other in self.battlefield.values()))
                   for effect in self.static_effects(source)):grants.append(stamp)
        if ability=='indestructible' and p.definition.name=='Zurgo Helmsmasher' and p.controller==self.turn_player:
            grants.append(p.entered_at)
        if ability=='haste' and ({'Mount','Vehicle'} & p.definition.subtypes):
            grants.extend(x.entered_at for x in self.battlefield.values() if x.controller==p.controller and x.definition.name=='Kolodin, Triumph Caster')
        return bool(grants) and max(grants)>p.lost_abilities.get(ability,-1)

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
            if not permanent.definition.supported:
                self.questions.append({"card":permanent.definition.name, "blocking":True,
                    "reason":permanent.definition.reason,
                    "question":"How should this ability be implemented and tested: " + permanent.definition.reason + "?"})
                raise NeedsRules(permanent.definition.reason)
        # Entry replacements must exist on the battlefield before the event;
        # two permanents entering simultaneously cannot apply replacements
        # granted by either of the entering permanents.
        incumbents=tuple(self.battlefield.values())
        for permanent in permanents:
            if 'Creature' in permanent.definition.types and any(
                source.controller!=permanent.controller and source.definition.opponent_creatures_enter_tapped
                for source in incumbents):permanent.tapped=True
            permanent.entered_at=self.timestamp()
            if 'Planeswalker' in permanent.definition.types and permanent.loyalty is None:permanent.loyalty=permanent.definition.loyalty
            if permanent.attached_to:permanent.attachment_at=permanent.entered_at
            self.battlefield[permanent.id]=permanent
        for permanent in permanents:
            self.emit("enters", id=permanent.id, name=permanent.definition.name,
                      controller=permanent.controller, types=sorted(permanent.definition.types),
                      subtypes=sorted(permanent.definition.subtypes))
            if 'enters' in permanent.definition.role_events:
                self.emit('trigger',**self.role_trigger(permanent))
            for watcher in list(self.battlefield.values()):
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

    def upkeep_triggers(self) -> list[dict]:
        """One trigger per supported permanent controlled by the active player."""
        triggers = []
        for p in self.battlefield.values():
            if p.controller != self.turn_player: continue
            for trigger in p.definition.triggers:
                if trigger.event == "upkeep":
                    triggers.append(event_data(trigger,p,p))
        return triggers

    def end_step_triggers(self, life_gained: int) -> list[dict]:
        """Check gained-life conditions at the beginning of the end step only.

        Net life change is not a substitute for amount gained; sources can
        lose life and gain life in the same turn.
        """
        triggers=[]
        for permanent in self.battlefield.values():
            if permanent.controller!=self.turn_player:continue
            for ability in permanent.definition.triggers:
                if ability.event=='end_step' and life_gained>=ability.life_gained_at_least:
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
                        triggers.append(event_data(trigger,watcher,creature))
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

    def counter_amount(self, target_id: str, amount: int) -> int:
        """Apply supported +1/+1 counter replacements to a positive event.

        The affected controller chooses the legal maximal result here:
        additive effects before doubling effects. A separate choice policy
        may select another ordering later.
        """
        if amount<=0:return max(0,amount)
        target=self.battlefield[target_id]
        if not self.creature(target):return amount
        additions=[];multipliers=[]
        for source in self.battlefield.values():
            for kind,value,scope in source.definition.counter_replacements:
                if scope!='controlled_creature' or source.controller!=target.controller:continue
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
        if 'attacks' in a.definition.role_events:
            self.emit('trigger',**self.role_trigger(a))
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
            elif operation=='subtype_count_boost':
                count=sum(other.id!=a.id and other.controller==a.controller and keyword in other.definition.subtypes
                          for other in self.battlefield.values())
                if not defer:a.temporary_power+=power*count;a.temporary_toughness+=toughness*count
                self.emit('trigger',source=a.id,name=a.definition.name,controller=a.controller,target=a.id,
                    operation='subtype_count_boost',effect='temporary boost per controlled subtype',
                    power=power,toughness=toughness,subtype=keyword)
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
        # Tokens enter tapped; they do not trigger 'whenever this attacks' abilities.
        for equipment in list(self.battlefield.values()):
            if equipment.definition.name != "Andúril, Flame of the West" or equipment.attached_to != a.id:
                continue
            attacking = defending_player if a.definition.legendary and equipment.controller == a.controller else None
            if defer:
                self.emit('trigger',operation='create_tokens',source=equipment.id,name=equipment.definition.name,controller=equipment.controller,effect='two Spirits',tokenSpec=dict(amount=2,power=1,toughness=1,colors=['White'],subtypes=['Spirit'],keywords=['flying'],tapped=True,attacking=attacking is not None))
                continue
            ids = []
            for _ in range(2):
                self._next_token += 1
                token_id = f"spirit-token-{self._next_token}"
                token = Definition("Spirit",frozenset({"Creature"}),frozenset({"Spirit"}),False,1,1,frozenset({"flying"}),colors=frozenset({"White"}))
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
