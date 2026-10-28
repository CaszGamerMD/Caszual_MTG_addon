"""Strict, composable Oracle grammar. No card-name dispatch or guessed remainder."""
from dataclasses import dataclass
import re

@dataclass(frozen=True)
class Selector:
    relation: str = 'any'
    other: bool = False
    self_only: bool = False
    creature: bool = False
    subtype: str = ''
    color: str = ''

@dataclass(frozen=True)
class StaticEffect:
    subject: Selector
    power: int
    toughness: int
    count: Selector | None = None
    condition: Selector | None = None

@dataclass(frozen=True)
class Effect:
    operation: str
    amount: int
    recipient: str = 'controller'
    gain: int = 0

@dataclass(frozen=True)
class Trigger:
    event: str
    subject: Selector
    effect: Effect

@dataclass(frozen=True)
class Program:
    triggers: tuple[Trigger, ...]
    keywords: frozenset[str]
    static_effects: tuple[StaticEffect, ...] = ()

def static_effect(text):
    m=re.fullmatch(r'(Other )?(?:(white|blue|black|red|green) )?[Cc]reatures you control get \+([0-9]+)/\+([0-9]+)\.',text)
    if m: return StaticEffect(Selector(relation='controller',other=bool(m[1]),creature=True,
                                      color=(m[2] or '').title()),int(m[3]),int(m[4]))
    m=re.fullmatch(r'Other ([A-Z][a-z]+) you control get \+([0-9]+)/\+([0-9]+)\.',text)
    if m:
        irregular={'Allies':'Ally','Faeries':'Faerie','Zombies':'Zombie','Harpies':'Harpy',
                   'Mercenaries':'Mercenary','Elves':'Elf','Dwarves':'Dwarf','Wolves':'Wolf',
                   'Werewolves':'Werewolf','Mice':'Mouse','Oxen':'Ox','Fungi':'Fungus',
                   'Fish':'Fish','Merfolk':'Merfolk','Sheep':'Sheep'}
        subtype=irregular.get(m[1])
        if subtype is None and m[1].endswith('s') and not m[1].endswith(('ies','ves','ses','xes','ches','shes')):
            subtype=m[1][:-1]
        if subtype: return StaticEffect(Selector(relation='controller',other=True,subtype=subtype),int(m[2]),int(m[3]))
        return None  # Unrecognized inflection must not become an invented type.
    m=re.fullmatch(r'This creature gets \+([0-9]+)/\+([0-9]+) for each other ([A-Z][a-z]+) on the battlefield\.',text)
    if m: return StaticEffect(Selector(self_only=True),int(m[1]),int(m[2]),count=Selector(other=True,subtype=m[3]))
    m=re.fullmatch(r'This creature gets \+([0-9]+)/\+([0-9]+) as long as you control another (white|blue|black|red|green) creature\.',text)
    if m: return StaticEffect(Selector(self_only=True),int(m[1]),int(m[2]),
                             condition=Selector(relation='controller',other=True,creature=True,color=m[3].title()))
    return None

KEYWORDS = {'flash','flying','first strike','double strike','lifelink','vigilance',
            'trample','haste','defender','reach','deathtouch','indestructible'}

def selector(text):
    if text == 'this creature': return Selector(self_only=True,creature=True)
    if text in ('this creature or another creature','this creature or another creature you control'):
        return Selector(relation='controller' if text.endswith('you control') else 'any',creature=True)
    m=re.fullmatch(r'(a|another) (creature|[A-Z][a-z]+(?: creature)?) you control',text)
    if not m: return None
    noun=m[2]
    return Selector(relation='controller',other=m[1]=='another',
                    creature=noun=='creature' or noun.endswith(' creature'),
                    subtype='' if noun=='creature' else noun.split()[0])

def effect(text):
    m=re.fullmatch(r'(each opponent|target player) loses ([1-9][0-9]*) life(?: and you gain ([1-9][0-9]*) life)?\.',text)
    if m: return Effect('lose_life',int(m[2]),m[1],int(m[3] or 0))
    m=re.fullmatch(r'this (?:creature|enchantment|permanent) deals ([1-9][0-9]*) damage to each opponent\.',text)
    if m: return Effect('damage',int(m[1]),'each opponent')
    m=re.fullmatch(r'scry ([1-9][0-9]*)\.',text)
    if m: return Effect('scry',int(m[1]))
    return None

def compile_abilities(text, name=''):
    """Consume every paragraph. Unsupported text rejects the whole program.

    A name is used only to normalize an Oracle self-reference, never to select
    behavior. Keywords and trigger/effect combinations compose independently.
    """
    if name: text=text.replace(name,'this creature')
    triggers=[]; keywords=set(); static_effects=[]
    for line in text.splitlines():
        line=line.strip()
        if not line: continue
        words=[w.strip().lower() for w in line.split(',')]
        if all(w in KEYWORDS for w in words):
            keywords.update(words); continue
        static=static_effect(line)
        if static:
            static_effects.append(static); continue
        m=re.fullmatch(r'(?:When|Whenever) (.+) (enters(?: the battlefield)?|dies), (.+)',line)
        if not m: return None
        subject=selector(m[1]); action=effect(m[3])
        if subject is None or action is None: return None
        event='dies' if m[2]=='dies' else 'enters'
        # Scry on death needs a new resolution implementation, not just parsing.
        if event=='dies' and action.operation=='scry': return None
        triggers.append(Trigger(event,subject,action))
    return Program(tuple(triggers),frozenset(keywords),tuple(static_effects)) if triggers or static_effects else None

def matches(subject, source, entered, is_creature):
    return ((not subject.self_only or source.id==entered.id)
        and (not subject.other or source.id!=entered.id)
        and (subject.relation!='controller' or source.controller==entered.controller)
        and (not subject.creature or is_creature)
        and (not subject.color or subject.color in entered.definition.colors)
        and (not subject.subtype or subject.subtype in entered.definition.subtypes))

def event_data(trigger, source, subject):
    e=trigger.effect
    label={'lose_life':f'{e.recipient} loses {e.amount} life',
           'damage':f'deal {e.amount} damage to each opponent','scry':'scry'}[e.operation]
    if e.gain: label+=f'; controller gains {e.gain} life'
    return {'source':source.id,'name':source.definition.name,'controller':source.controller,
            'effect':label,'operation':e.operation,'recipient':e.recipient,
            'amount':e.amount,'gain':e.gain,
            ('entered' if trigger.event=='enters' else 'dead'):subject.id}
