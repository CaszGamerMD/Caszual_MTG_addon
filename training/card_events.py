"""Experimental event/continuous-effect kernel for a small set of real cards.

This is an isolated rules prototype: it does not implement priority, the stack,
combat damage, costs for casting spells, or the full turn simulator. Unknown
rules raise NeedsRules rather than being treated as blank.
"""
from __future__ import annotations
from dataclasses import dataclass, field
import re
from oracle_abilities import Trigger, StaticEffect, compile_abilities, matches, event_data


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
                    "trample", "haste", "defender", "reach", "deathtouch", "indestructible"}


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
    base = dict(name=name, types=types, subtypes=subtypes,
                legendary="Legendary" in (card.get("superTypes") or []), power=power, toughness=toughness,
                colors=frozenset(card.get("colors") or []))
    if ("Creature" in types or "Vehicle" in subtypes) and (power < 0 or toughness <= 0):
        return Definition(**base, abilities=frozenset(), supported=False, reason="Missing or invalid fixed power/toughness")
    program = compile_abilities(text,name)
    if program is not None and ("Creature" in types or "Enchantment" in types):
        return Definition(**base,abilities=program.keywords,triggers=program.triggers,static_effects=program.static_effects)
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
    if not ("Creature" in types or "Vehicle" in subtypes):
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


@dataclass
class Game:
    battlefield: dict[str, Permanent] = field(default_factory=dict)
    events: list[dict] = field(default_factory=list)
    questions: list[dict] = field(default_factory=list)
    turn_player: int = 0
    phase: str = "main"
    mana: dict[int, int] = field(default_factory=lambda: {0:0, 1:0})
    _next_token: int = 0

    def emit(self, kind: str, **data):
        self.events.append({"kind":kind, **data})

    def creature(self, p: Permanent) -> bool:
        return "Creature" in p.definition.types or ("Vehicle" in p.definition.subtypes and p.animated)

    def stats(self, p: Permanent) -> tuple[int, int]:
        if not self.creature(p):
            raise IllegalAction("Permanent is not currently a creature")
        bonus = sum(1 for x in self.battlefield.values()
                    if x.definition.name == "Andúril, Flame of the West" and x.attached_to == p.id)
        power_bonus = toughness_bonus = 0
        for source in self.battlefield.values():
            for effect in source.definition.static_effects:
                if not matches(effect.subject,source,p,True): continue
                if effect.condition and not any(matches(effect.condition,source,x,self.creature(x)) for x in self.battlefield.values()): continue
                multiplier = (sum(matches(effect.count,source,x,self.creature(x)) for x in self.battlefield.values())
                              if effect.count else 1)
                power_bonus += effect.power * multiplier
                toughness_bonus += effect.toughness * multiplier
        return (p.definition.power + p.counters + 3*bonus + power_bonus,
                p.definition.toughness + p.counters + bonus + toughness_bonus)

    def has(self, p: Permanent, ability: str) -> bool:
        if ability in p.definition.abilities: return True
        if any(effect.grant == ability and matches(effect.subject,source,p,self.creature(p))
               for source in self.battlefield.values() for effect in source.definition.static_effects):
            return True
        if ability == "indestructible" and p.definition.name == "Zurgo Helmsmasher" and p.controller == self.turn_player:
            return True
        if ability == "haste" and ({"Mount","Vehicle"} & p.definition.subtypes):
            return any(x.controller == p.controller and x.definition.name == "Kolodin, Triumph Caster"
                       for x in self.battlefield.values())
        return False

    def enter(self, permanent: Permanent):
        if permanent.id in self.battlefield: raise IllegalAction("Duplicate permanent ID")
        if not permanent.definition.supported:
            self.questions.append({"card":permanent.definition.name, "blocking":True,
                "reason":permanent.definition.reason,
                "question":"How should this ability be implemented and tested: " + permanent.definition.reason + "?"})
            raise NeedsRules(permanent.definition.reason)
        self.battlefield[permanent.id] = permanent
        self.emit("enters", id=permanent.id, name=permanent.definition.name,
                  controller=permanent.controller, types=sorted(permanent.definition.types),
                  subtypes=sorted(permanent.definition.subtypes))
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

    def upkeep_triggers(self) -> list[dict]:
        """One trigger per supported permanent controlled by the active player."""
        triggers = []
        for p in self.battlefield.values():
            if p.controller != self.turn_player: continue
            for trigger in p.definition.triggers:
                if trigger.event == "upkeep":
                    triggers.append(event_data(trigger,p,p))
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
        if sum(self.stats(p)[0] for p in creatures) < required:
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
        equipment.attached_to = target.id
        self.emit("equip", equipment=equipment_id, target=creature_id, mana=2)

    def attack(self, attacker_id: str, defending_player: int):
        a = self.battlefield[attacker_id]
        if self.phase != "combat" or a.controller != self.turn_player or defending_player not in (0,1) or defending_player == a.controller:
            raise IllegalAction("Attacker/defender or phase invalid")
        if not self.creature(a) or a.tapped or self.has(a,"defender") or a.fresh and not self.has(a,"haste"):
            raise IllegalAction("Creature cannot attack")
        if not self.has(a,"vigilance"): a.tapped = True
        a.attacking = defending_player
        self.emit("attacks", id=a.id, defending=defending_player)
        if a.definition.name == "Brightfield Mustang" and a.saddled:
            a.tapped = False
            a.counters += 1
            self.emit("trigger", source=a.id, effect="untap and add +1/+1 counter", target=a.id)
        # Tokens enter tapped; they do not trigger 'whenever this attacks' abilities.
        for equipment in list(self.battlefield.values()):
            if equipment.definition.name != "Andúril, Flame of the West" or equipment.attached_to != a.id:
                continue
            attacking = defending_player if a.definition.legendary and equipment.controller == a.controller else None
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
            p.saddled = False
            p.animated = False
            p.attacking = None
        # An Equipment cannot remain attached to a Vehicle after it ceases to be a creature.
        for p in self.battlefield.values():
            target = self.battlefield.get(p.attached_to) if p.attached_to else None
            if target is not None and not self.creature(target):
                p.attached_to = None
        self.emit("cleanup")
