"""Strict, composable Oracle grammar. No card-name dispatch or guessed remainder."""
from dataclasses import dataclass, asdict
import re

@dataclass(frozen=True)
class TokenSpec:
    amount: int
    power: int
    toughness: int
    colors: tuple[str, ...]
    subtypes: tuple[str, ...]
    keywords: frozenset[str]
    tapped: bool = False
    land: bool = False
    enchantment: bool = False
    attacking: bool = False
    contribution_bonus: int = 0
    temporary_haste: bool = False
    must_attack_this_combat: bool = False

def parse_token_creation(text):
    """A whole standalone instruction, not a substring stripped of extra rules."""
    attacking="that's tapped and attacking" in text
    if attacking:text=text.replace(" creature token that's tapped and attacking."," creature token.").replace(" creature tokens that are tapped and attacking."," creature tokens.")
    m=re.fullmatch(r'Create (a|an|one|two|three|four|[1-9][0-9]*) (tapped )?([0-9]+)/([1-9][0-9]*) (white|blue|black|red|green|colorless)(?: and (white|blue|black|red|green))? ([A-Z][a-z]+(?: [A-Z][a-z]+)*) (land |enchantment )?creature tokens?(?: with (.+))?\.',text)
    if not m: return None
    abilities=frozenset(re.split(r', | and ',m[9] or ''))-{''}
    if not abilities <= KEYWORDS-{'flash'}: return None
    if m[5]=='colorless' and m[6]: return None
    amount={'a':1,'an':1,'one':1,'two':2,'three':3,'four':4}.get(m[1])
    if amount is None: amount=int(m[1])
    return TokenSpec(amount,int(m[3]),int(m[4]),tuple(c.title() for c in (m[5],m[6]) if c and c!='colorless'),
                     tuple(m[7].split()),abilities,bool(m[2]) or attacking,m[8]=='land ',m[8]=='enchantment ',attacking)

@dataclass(frozen=True)
class Selector:
    relation: str = 'any'
    other: bool = False
    self_only: bool = False
    creature: bool = False
    subtype: str = ''
    color: str = ''
    legendary: bool | None = None
    spell_type: str = ''
    permanent_type: str = ''
    chosen_subtype: bool = False  # Resolve the source's entry-time creature-type choice.
    attacking: bool = False  # Check current combat participation, not tapped status.
    excluded_subtype: str = ''  # A non-Human filter must exclude all Human creatures.
    self_or_controlled_subtype: str = ''

@dataclass(frozen=True)
class StaticEffect:
    subject: Selector
    power: int
    toughness: int
    count: Selector | None = None
    condition: Selector | None = None
    grant: str = ''
    ward_cost: str = ''
    life_min: int = 0
    suppress: str = ''  # Continuous 'can't have or gain' overrides all grants.
    share_types: bool = False  # Count other creatures sharing any creature subtype.
    must_attack: bool = False  # Continuous requirement: attack each combat if able.
    requires_attachment: bool = False  # Enchanted/equipped creature only.

@dataclass(frozen=True)
class Effect:
    operation: str
    amount: int
    recipient: str = 'controller'
    gain: int = 0
    token: TokenSpec | None = None
    controller_loss: int = 0
    library_filter: tuple = ()
    steps: tuple = ()
    optional: bool = False
    counter_subtype: str = ""
    counter_subtypes: tuple = ()
    alternate_amount: int = 0
    boost_toughness: int = 0
    boost_keyword: str = ''

@dataclass(frozen=True)
class Trigger:
    event: str
    subject: Selector
    effect: Effect
    life_gained_at_least: int = 0
    lands_controlled_at_least: int = 0
    min_counters: int = 0
    power_above_base_required: bool = False

@dataclass(frozen=True)
class Program:
    triggers: tuple[Trigger, ...]
    keywords: frozenset[str]
    static_effects: tuple[StaticEffect, ...] = ()
    activations: tuple = ()
    devotion: tuple = ()
    life_multiplier: int = 1
    opponent_creatures_enter_tapped: bool = False
    life_addition: int = 0
    cost_reductions: tuple = ()
    counter_replacements: tuple = ()
    token_replacements: tuple = ()
    token_action_triggers: tuple = ()
    token_leave_triggers: tuple = ()
    entry_counter_grants: tuple = ()
    attack_watchers: tuple = ()
    chosen_type_entry: bool = False
    opponent_life_gain_becomes_loss: bool = False
    prevent_combat_damage_to_attackers: bool = False

def static_effect(text):
    attached=re.fullmatch(r'Creatures you control that are enchanted or equipped have ([a-z ]+)\.',text)
    if attached:
        if attached[1] not in KEYWORDS-{'flash'}:return None
        return StaticEffect(Selector(relation='controller',creature=True),0,0,
                            grant=attached[1],requires_attachment=True)
    # Enchantment creatures form a type intersection, not a creature subtype.
    typed=re.fullmatch(r'(Other )?enchantment creatures you control get \+([0-9]+)/\+([0-9]+)\.',text)
    if typed:
        return StaticEffect(Selector(relation='controller',other=bool(typed[1]),
                                     creature=True,permanent_type='Enchantment'),
                            int(typed[2]),int(typed[3]))
    opposing=re.fullmatch(r'Creatures your opponents control get ([+-][0-9]+)/([+-][0-9]+)\.',text)
    if opposing:
        return StaticEffect(Selector(relation='opponent',creature=True),int(opposing[1]),int(opposing[2]))
    attacking_anthem=re.fullmatch(
        r'Attacking (?:non-([A-Z][a-z]+) )?creatures you control get \+([0-9]+)/\+([0-9]+) and have (.+)\.',text)
    if attacking_anthem:
        traits={part.strip() for part in re.split(r', | and ',attacking_anthem[4])}
        if not traits or not traits<=KEYWORDS-{'flash'}:return None
        subject=Selector(relation='controller',creature=True,attacking=True,
                         excluded_subtype=attacking_anthem[1] or '')
        return (StaticEffect(subject,int(attacking_anthem[2]),int(attacking_anthem[3])),)+tuple(
            StaticEffect(subject,0,0,grant=trait) for trait in sorted(traits))
    must=re.fullmatch(r'(Other )?([A-Z][a-z]+) creatures( you control)? attack each combat if able\.',text)
    if must:
        return StaticEffect(Selector(relation='controller' if must[3] else 'any',
                             other=bool(must[1]),creature=True,subtype=must[2]),
                            0,0,must_attack=True)
    chosen=re.fullmatch(r'Creatures you control of the chosen type get \+([0-9]+)/\+([0-9]+)\.',text)
    if chosen:
        return StaticEffect(Selector(relation='controller',creature=True,chosen_subtype=True),
                            int(chosen[1]),int(chosen[2]))
    # A continuous prohibition is not a temporary timestamped ability loss:
    # the keyword cannot be granted again while this source is present.
    denial=re.fullmatch(r"Creatures your opponents control lose (.+) and can't have or gain \1\.",text)
    if denial:
        if denial[1] not in KEYWORDS:return None
        return StaticEffect(Selector(relation='opponent',creature=True),0,0,suppress=denial[1])
    # Coat-style global bonuses count each *other creature* once, even if it
    # shares multiple creature types; opposing creatures also participate.
    shared=re.fullmatch(r'Each creature gets \+([1-9][0-9]*)/\+([1-9][0-9]*) for each other creature on the battlefield that shares at least one creature type with it\.',text)
    if shared:
        return StaticEffect(Selector(creature=True),int(shared[1]),int(shared[2]),share_types=True)
    # Global lords affect matching creature types even when an opponent
    # controls them. Landwalk is a blocking restriction evaluated at declare
    # blockers, not a stat bonus or a change to land ownership.
    lord=re.fullmatch(
        r'Other ([A-Z][a-z]+) get \+([0-9]+)/\+([0-9]+) and have ((?:plains|island|swamp|mountain|forest)walk)\.',
        text)
    if lord:
        plurals={'Faeries':'Faerie','Elves':'Elf','Wolves':'Wolf','Mice':'Mouse',
                 'Allies':'Ally','Zombies':'Zombie','Merfolk':'Merfolk',
                 'Oxen':'Ox','Fish':'Fish'}
        plural=lord[1]
        subtype=plurals.get(plural)
        if subtype is None and plural.endswith('s') and not plural.endswith(('ies','ves','ses','xes','ches','shes')):
            subtype=plural[:-1]
        if subtype is None:return None
        subject=Selector(relation='any',other=True,creature=True,subtype=subtype)
        return (StaticEffect(subject,int(lord[2]),int(lord[3])),
                StaticEffect(subject,0,0,grant=lord[4]))
    subtype_stats=re.fullmatch(
        r'Other ([A-Z][a-z]+) creatures you control get \+([0-9]+)/\+([0-9]+)\.',text)
    if subtype_stats:
        return StaticEffect(Selector(relation='controller',other=True,creature=True,
                                     subtype=subtype_stats[1]),
                            int(subtype_stats[2]),int(subtype_stats[3]))
    subtype_anthem=re.fullmatch(r'Other ([A-Z][a-z]+) creatures you control get \+([0-9]+)/\+([0-9]+) and have (.+)\.',text)
    if subtype_anthem:
        traits={w.strip() for w in re.split(r', | and ',subtype_anthem[4])}
        if not traits or not traits<=KEYWORDS:return None
        subject=Selector(relation='controller',other=True,creature=True,subtype=subtype_anthem[1])
        return (StaticEffect(subject,int(subtype_anthem[2]),int(subtype_anthem[3])),)+tuple(
            StaticEffect(subject,0,0,grant=word) for word in sorted(traits))
    # Independent continuous effects; double-tribe creatures only receive each
    # granted keyword once.
    groups=re.fullmatch(
        r'([A-Z][a-z]+) you control and ([A-Z][a-z]+) you control have (.+)\.',text)
    if groups:
        traits={w.strip() for w in re.split(r', | and ',groups[3].replace(', and ', ', '))}
        if not traits or not traits<=KEYWORDS:return None
        plurals={'Faeries':'Faerie','Elves':'Elf','Wolves':'Wolf','Mice':'Mouse',
                 'Allies':'Ally','Zombies':'Zombie','Merfolk':'Merfolk',
                 'Oxen':'Ox','Fish':'Fish'}
        def singular(word):
            if word in plurals:return plurals[word]
            if word.endswith('s') and not word.endswith(('ies','ves','ses','xes','ches','shes')):return word[:-1]
            return None
        first,second=singular(groups[1]),singular(groups[2])
        if not first or not second:return None
        return tuple(StaticEffect(Selector(relation='controller',creature=True,subtype=kind),
                                  0,0,grant=word)
                     for kind in dict.fromkeys((first,second)) for word in sorted(traits))
    # Multiple creature-type groups in one anthem share the same controller
    # restriction; a creature with both types gets the keyword only once.
    two_tribes=re.fullmatch(r'(Other )?([A-Z][a-z]+) and ([A-Z][a-z]+) you control have (.+)\.',text)
    if two_tribes:
        traits={word.strip() for word in re.split(r', | and ',two_tribes[4])}
        if not traits or not traits<=KEYWORDS:return None
        irregular={'Faeries':'Faerie','Elves':'Elf','Wolves':'Wolf','Mice':'Mouse',
                   'Allies':'Ally','Zombies':'Zombie','Merfolk':'Merfolk','Oxen':'Ox',
                   'Fish':'Fish','Orcs':'Orc','Goblins':'Goblin'}
        def singular(word):
            if word in irregular:return irregular[word]
            if word.endswith('s') and not word.endswith(('ies','ves','ses','xes','ches','shes')):
                return word[:-1]
            return None
        kinds=tuple(dict.fromkeys((singular(two_tribes[2]),singular(two_tribes[3]))))
        if not all(kinds):return None
        return tuple(StaticEffect(Selector(relation='controller',other=bool(two_tribes[1]),
                                           creature=True,subtype=kind),0,0,grant=trait)
                     for kind in kinds for trait in sorted(traits))
    subtype_keyword=re.fullmatch(r'(Other )?([A-Z][a-z]+)s you control have (.+)\.',text)
    # "Creatures you control" is the older general keyword-anthem grammar.
    # Never treat "Creatures" as an unknown creature subtype.
    if subtype_keyword and subtype_keyword[2]!='Creature':
        traits={w.strip() for w in re.split(r', | and ',subtype_keyword[3])}
        if not traits or not traits<=KEYWORDS:return None
        subject=Selector(relation='controller',other=bool(subtype_keyword[1]),
                         creature=True,subtype=subtype_keyword[2])
        return tuple(StaticEffect(subject,0,0,grant=word) for word in sorted(traits))
    stat_conditional=re.fullmatch(r'This creature gets \+([0-9]+)/\+([0-9]+) as long as you have ([1-9][0-9]*) or more life\.',text)
    if stat_conditional:
        return StaticEffect(Selector(self_only=True,creature=True),int(stat_conditional[1]),int(stat_conditional[2]),life_min=int(stat_conditional[3]))
    life_conditional=re.fullmatch(r'As long as you have ([1-9][0-9]*) or more life, this creature gets \+([0-9]+)/\+([0-9]+) and has (.+)\.',text)
    if life_conditional:
        words={part.strip() for part in re.split(r', | and ',life_conditional[4])}
        if not words or not words<=KEYWORDS:return None
        selector=Selector(self_only=True,creature=True)
        minimum=int(life_conditional[1])
        return (StaticEffect(selector,int(life_conditional[2]),int(life_conditional[3]),life_min=minimum),)+tuple(
            StaticEffect(selector,0,0,grant=word,life_min=minimum) for word in sorted(words))
    combined=re.fullmatch(r'(Creatures you control) get \+([0-9]+)/\+([0-9]+) and have (.+)\.',text)
    if combined:
        words=set(re.split(r', | and ',combined[4]))
        if not words or not words<=KEYWORDS:return None
        subject=Selector(relation='controller',creature=True)
        return (StaticEffect(subject,int(combined[2]),int(combined[3])),)+tuple(StaticEffect(subject,0,0,grant=w) for w in sorted(words))
    multi=re.fullmatch(r'Creatures you control have (.+)\.',text)
    if multi and (',' in multi[1] or ' and ' in multi[1] or 'protection from ' in multi[1]):
        clause=multi[1].replace(' and from ',', protection from ').replace(', and ',', ').replace(' and ',', ')
        words=[w.strip() for w in clause.split(',')]
        allowed=KEYWORDS|{'protection from '+c for c in ('white','blue','black','red','green')}
        if all(w in allowed for w in words):
            return tuple(StaticEffect(Selector(relation='controller',creature=True),0,0,grant=w) for w in words)
        return None
    cost=r'((?:\{(?:[0-9]{1,2}|[WUBRGC])\})+)'
    intrinsic=re.fullmatch(r'Ward '+cost,text)
    if intrinsic:return StaticEffect(Selector(self_only=True),0,0,ward_cost=intrinsic[1])
    m=re.fullmatch(r'(Legendary|Nonlegendary) creatures you control get \+([0-9]+)/\+([0-9]+)(?: and have ward '+cost+r')?\.',text)
    if m:return StaticEffect(Selector(relation='controller',creature=True,legendary=m[1]=='Legendary'),
                             int(m[2]),int(m[3]),ward_cost=m[4] or '')
    m=re.fullmatch(r'(Other )?(?:([Ww]hite|[Bb]lue|[Bb]lack|[Rr]ed|[Gg]reen) )?[Cc]reatures you control have (flying|first strike|double strike|lifelink|vigilance|trample|haste|defender|reach|deathtouch|indestructible|hexproof|menace)\.',text)
    if m: return StaticEffect(Selector(relation='controller',other=bool(m[1]),creature=True,color=(m[2] or '').title()),0,0,grant=m[3])
    m=re.fullmatch(r'(Other )?(?:([Ww]hite|[Bb]lue|[Bb]lack|[Rr]ed|[Gg]reen) )?[Cc]reatures you control get \+([0-9]+)/\+([0-9]+)\.',text)
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
            'trample','haste','defender','reach','deathtouch','indestructible','hexproof','menace',
            'plainswalk','islandwalk','swampwalk','mountainwalk','forestwalk','shroud','fear'}

def selector(text):
    if text == 'this creature': return Selector(self_only=True,creature=True)
    if text in ('this land','this artifact','this enchantment','this permanent'):return Selector(self_only=True)
    if text in ('this creature or another creature','this creature or another creature you control'):
        return Selector(relation='controller' if text.endswith('you control') else 'any',creature=True)
    m=re.fullmatch(r'(a|another) (creature|[A-Z][a-z]+(?: creature)?) you control',text)
    if not m:
        if text=='a creature an opponent controls':return Selector(relation='opponent',creature=True)
        return None
    noun=m[2]
    return Selector(relation='controller',other=m[1]=='another',
                    creature=noun=='creature' or noun.endswith(' creature'),
                    subtype='' if noun=='creature' else noun.split()[0])

def effect(text):
    any_target=re.fullmatch(r'you may have (?:it|this creature) deal ([1-9][0-9]*) damage to any target\.',text)
    if any_target:return Effect('damage_any_target',int(any_target[1]),optional=True)
    if text=='each opponent loses life equal to the number of tapped creatures you control.':
        return Effect('opponent_loss_tapped_creatures',0,'each opponent')
    may=re.fullmatch(r'you may (create .+)',text)
    if may:
        spec=parse_token_creation(may[1][0].upper()+may[1][1:])
        if spec:return Effect('create_tokens',spec.amount,token=spec,optional=True)
        return None
    tutor=re.fullmatch(r'you may search your library for a ([A-Z][a-z]+) card, reveal that card, put it into your hand, then shuffle\.',text)
    if tutor:
        return Effect('optional_subtype_search_hand',0,library_filter=('subtype',tutor[1]))
    return_graveyard=re.fullmatch(r'you may return target ([A-Z][a-z]+) card from your graveyard to your hand\.',text)
    if return_graveyard:
        return Effect('return_graveyard',1,optional=True,
                      library_filter=('subtype',return_graveyard[1]))
    if text=='each opponent may search their library for a basic land card, put it onto the battlefield tapped, then shuffle.':
        return Effect('opponent_optional_basic_search',0,'each opponent')
    if text=="return a land you control to its owner's hand.":return Effect('return_controlled_land',1)
    gain=re.fullmatch(r'you gain ([1-9][0-9]*) life\.',text)
    if gain:return Effect('gain_life',int(gain[1]))
    drawn=re.fullmatch(r'(?:you )?draw (a|one|two|three|[1-9][0-9]*) cards?\.',text)
    if drawn:return Effect('draw_cards',{'a':1,'one':1,'two':2,'three':3}.get(drawn[1],int(drawn[1]) if drawn[1].isdigit() else 0))
    from library_effects import parse
    library_filter=parse(text)
    if library_filter:return Effect('reveal_creatures',library_filter[0],library_filter=library_filter)
    token=parse_token_creation(text[:1].upper()+text[1:])
    if token: return Effect('create_tokens',token.amount,token=token)
    tribal=re.fullmatch(r'put (a|[1-9][0-9]*) \+1/\+1 counters? on each ([A-Z][a-z]+) you control\.',text)
    if tribal:return Effect('add_counters',1 if tribal[1]=='a' else int(tribal[1]),'controlled subtype',counter_subtype=tribal[2])
    m=re.fullmatch(r'put (a|[1-9][0-9]*) \+1/\+1 counters? on each creature you control\.',text)
    if m: return Effect('add_counters',1 if m[1]=='a' else int(m[1]),'controlled creatures')
    m=re.fullmatch(r'(each opponent|target player) loses ([1-9][0-9]*) life(?: and you gain ([1-9][0-9]*) life)?\.',text)
    if m: return Effect('lose_life',int(m[2]),m[1],int(m[3] or 0))
    m=re.fullmatch(r'this (?:creature|enchantment|permanent) deals ([1-9][0-9]*) damage to each opponent and each creature and planeswalker they control\.',text)
    if m:return Effect('damage_board',int(m[1]),'opposing board')
    m=re.fullmatch(r'this (?:creature|enchantment|permanent) deals ([1-9][0-9]*) damage to each opponent\.',text)
    if m: return Effect('damage',int(m[1]),'each opponent')
    m=re.fullmatch(r'(scry|surveil) ([1-9][0-9]*)\.',text)
    if m: return Effect(m[1],int(m[2]))
    milled=re.fullmatch(r'(you mill|each opponent mills|each player mills) (a|one|two|three|four|five|six|seven|eight|nine|ten|[1-9][0-9]*) cards?\.',text)
    if milled:
        word=milled[2]
        count={'a':1,'one':1,'two':2,'three':3,'four':4,'five':5,'six':6,'seven':7,'eight':8,'nine':9,'ten':10}.get(word)
        if count is None:count=int(word)
        return Effect('mill_cards',count,recipient={
            'you mill':'controller','each opponent mills':'each opponent',
            'each player mills':'each player'}[milled[1]])
    # Consume the entire ordered instruction; a partially understood clause
    # must never be treated as a successful parse.
    if text.endswith('.'):
        clauses=re.split(r' and (?=(?:you )?(?:gain |draw ))',text[:-1])
        if len(clauses)>1:
            steps=tuple(effect(clause+'.') for clause in clauses)
            if all(step is not None and step.operation in ('gain_life','draw_cards') for step in steps):
                return Effect('ordered_effects',0,steps=steps)
    return None

def compile_abilities(text, name=''):
    """Consume every paragraph. Unsupported text rejects the whole program.

    A name is used only to normalize an Oracle self-reference, never to select
    behavior. Keywords and trigger/effect combinations compose independently.
    """
    if name:
        text=text.replace(name,'this creature')
        # Many Oracle texts shorten a multiword name to its first word.
        # Normalize that reference only in a self-counter instruction.
        if ' ' in name:
            short=name.split(' ',1)[0].rstrip(',')
            text=re.sub(r'(?<= on )'+re.escape(short)+r'(?=\.| instead\.)','this creature',text)
        if ',' in name:
            text=re.sub(r'\b'+re.escape(name.split(',')[0])+r"(?= isn't a creature| enters| attacks|\'s power)",'this creature',text)
    triggers=[]; keywords=set(); static_effects=[];activations=[];devotion=();life_multiplier=1;opponent_creatures_enter_tapped=False;life_addition=0;cost_reductions=[];counter_replacements=[];token_replacements=[];token_action_triggers=[];token_leave_triggers=[];entry_counter_grants=[];attack_watchers=[];chosen_type_entry=False;opponent_life_gain_becomes_loss=False;prevent_combat_damage_to_attackers=False
    for line in text.splitlines():
        line=line.strip()
        if not line: continue
        if line in ('As this enchantment enters, choose a creature type.',
                    'As this artifact enters, choose a creature type.'):
            if chosen_type_entry:return None
            chosen_type_entry=True
            continue
        flying_attacks=re.fullmatch(
            r'Whenever a creature with flying attacks( you)?, (it loses flying until end of turn|this enchantment deals ([1-9][0-9]*) damage to it)\.',
            line)
        if flying_attacks:
            # Attack triggers require the attacked player's identity. No
            # opponent-specific card names are embedded in this grammar.
            if flying_attacks[1]:
                if flying_attacks[3] is None:return None
                attack_watchers.append(('controller_defending','attacker_damage',int(flying_attacks[3])))
            else:
                if flying_attacks[3] is not None:return None
                attack_watchers.append(('any','attacker_loses_flying',0))
            continue
        entry_counters=re.fullmatch(
            r'Each other ([A-Z][a-z]+) creature you control enters with (an|one|two|three|[1-9][0-9]*) additional \+1/\+1 counters? on it\.',
            line)
        if entry_counters:
            word=entry_counters[2]
            number={'an':1,'one':1,'two':2,'three':3}.get(word) or int(word)
            entry_counter_grants.append((Selector(relation='controller',other=True,creature=True,subtype=entry_counters[1]),number))
            continue
        condition=re.fullmatch(r"As long as your devotion to (white|blue|black|red|green) is less than (one|two|three|four|five|six|seven|eight|nine|[1-9][0-9]*), this creature isn't a creature\.",line)
        if condition:
            if devotion:return None
            threshold={'one':1,'two':2,'three':3,'four':4,'five':5,'six':6,'seven':7,'eight':8,'nine':9}.get(condition[2])
            devotion=({'white':'W','blue':'U','black':'B','red':'R','green':'G'}[condition[1]],threshold or int(condition[2]))
            continue
        addition=re.fullmatch(r'If you would gain life, you gain that much life plus ([1-9][0-9]*) instead\.',line)
        if addition:
            if life_addition:return None
            life_addition=int(addition[1]);continue
        if line=='If an opponent would gain life, that player loses that much life instead.':
            if opponent_life_gain_becomes_loss:return None
            opponent_life_gain_becomes_loss=True;continue
        if line=='Prevent all combat damage that would be dealt to attacking creatures you control.':
            if prevent_combat_damage_to_attackers:return None
            prevent_combat_damage_to_attackers=True;continue
        if line=='Creatures your opponents control enter tapped.':
            if opponent_creatures_enter_tapped:return None
            opponent_creatures_enter_tapped=True;continue
        if line=='If you would gain life, you gain twice that much life instead.':
            if life_multiplier!=1:return None
            life_multiplier=2;continue
        token_leave=re.fullmatch(r'Whenever a token you control leaves the battlefield, each opponent loses ([1-9][0-9]*) life and you gain ([1-9][0-9]*) life\.',line)
        if token_leave:
            token_leave_triggers.append(('opponent_loss_gain',int(token_leave[1]),int(token_leave[2])))
            continue
        token_action=re.fullmatch(r'Whenever you create or sacrifice a token, each opponent loses ([1-9][0-9]*) life\.',line)
        if token_action:
            token_action_triggers.extend((action,'opponent_loss',int(token_action[1])) for action in ('create','sacrifice'))
            continue
        creature_as=re.fullmatch(
            r'If one or more creature tokens would be created under your control, that many ([1-9][0-9]*)/([1-9][0-9]*) (white|blue|black|red|green)(?: and (white|blue|black|red|green))? ([A-Z][a-z]+(?: [A-Z][a-z]+)*) creature tokens?(?: with (.+))? are created instead\.',line)
        if creature_as:
            grants=frozenset(re.split(r', | and ',creature_as[6] or ''))-{''}
            if not grants <= KEYWORDS-{'flash'}:return None
            token_replacements.append(('creature_as',dict(
                power=int(creature_as[1]),toughness=int(creature_as[2]),
                colors=tuple(c.title() for c in (creature_as[3],creature_as[4]) if c),
                subtypes=tuple(creature_as[5].split()),keywords=tuple(sorted(grants))),
                'controlled','any'))
            continue
        token_controller=re.fullmatch(r'If an effect would create one or more tokens under your control, it creates twice that many of those tokens instead\.',line)
        if token_controller:
            token_replacements.append(('double',2,'controlled','effect'))
            continue
        token_global=re.fullmatch(r'If one or more tokens would be created, twice that many of those tokens are created instead\.',line)
        if token_global:
            token_replacements.append(('double',2,'any','any'))
            continue
        subtype_replacement=re.fullmatch(
            r'If one or more \+1/\+1 counters would be put on an? ((?:[A-Z][a-z]+(?:, [A-Z][a-z]+)*,? or [A-Z][a-z]+)|[A-Z][a-z]+) you control, that many plus one \+1/\+1 counters are put on it instead\.',
            line)
        if subtype_replacement:
            names=tuple(name for name in re.split(r',? or |, ',subtype_replacement[1]) if name)
            if not names or len(set(names))!=len(names):return None
            counter_replacements.append(('plus',1,'controlled_subtypes','any',names))
            continue
        counter_permanent=re.fullmatch(r'If an effect would put one or more counters on a permanent you control, it puts twice that many of those counters on that permanent instead\.',line)
        if counter_permanent:
            counter_replacements.append(('double',2,'controlled_permanent','effect'))
            continue
        counter_global=re.fullmatch(r'If one or more \+1/\+1 counters would be put on a creature, twice that many \+1/\+1 counters are put on that creature instead\.',line)
        if counter_global:
            counter_replacements.append(('double',2,'any_creature'))
            continue
        counter=re.fullmatch(r'If one or more \+1/\+1 counters would be put on a creature you control, (twice that many|that many plus one) \+1/\+1 counters are put on (?:it|that creature) instead\.',line)
        if counter:
            counter_replacements.append(('double' if counter[1]=='twice that many' else 'plus',2 if counter[1]=='twice that many' else 1,'controlled_creature'))
            continue
        discount=re.fullmatch(r'([A-Z][a-z]+(?: and [A-Za-z]+)?) spells you cast cost \{([1-9][0-9]*)\} less to cast\.',line)
        repeated=re.fullmatch(r'([A-Z][a-z]+) spells and ([A-Z][a-z]+) spells you cast cost \{([1-9][0-9]*)\} less to cast\.',line)
        if discount or repeated:
            words=tuple(word.lower() for word in (
                discount[1].split(' and ') if discount else (repeated[1],repeated[2])))
            allowed={'white','blue','black','red','green','colorless',
                     'artifact','enchantment','creature','instant','sorcery','planeswalker','aura','equipment'}
            # These are grammar categories, not per-card allowances.
            subtypes={'goblin','rogue','elf','faerie','squirrel','zombie','vampire','warrior',
                      'wizard','shaman','knight','dragon','merfolk','human','soldier','spirit'}
            if not words or not set(words)<=allowed|subtypes:return None
            filters=tuple('subtype:'+word if word in subtypes else word for word in words)
            cost_reductions.append((filters,int(discount[2] if discount else repeated[3])))
            continue
        activated=re.fullmatch(r'((?:\{(?:[0-9]+|[WUBRGC])\})+): (Create .+)',line)
        if activated:
            spec=parse_token_creation(activated[2])
            if not spec or all(part=='0' for part in re.findall(r'\{([^}]+)\}',activated[1])):return None
            activations.append((activated[1],spec));continue
        blocking_limit=re.fullmatch(
            r"This creature can't be blocked by creatures with power ([1-9][0-9]*) or greater\.",
            line)
        if blocking_limit:
            # This marker has no meaning outside block declaration. Its
            # numeric threshold is tested against current blocker power.
            keywords.add('block_power_below_'+blocking_limit[1]);continue
        words=[w.strip().lower() for w in line.split(',')]
        if all(w in KEYWORDS for w in words):
            keywords.update(words); continue
        static=static_effect(line)
        if static:
            static_effects.extend(static if isinstance(static,tuple) else (static,)); continue
        damage_mill=re.fullmatch(
            r'Whenever this creature deals combat damage to a player, (each (?:player|opponent) mills (?:a|one|two|three|four|five|six|seven|eight|nine|ten|[1-9][0-9]*) cards?\.)',
            line)
        if damage_mill:
            action=effect(damage_mill[1])
            if action is None or action.operation!='mill_cards':return None
            triggers.append(Trigger('combat_damage',Selector(self_only=True,creature=True),action))
            continue
        damage_hand=re.fullmatch(
            r'Whenever this creature deals damage to (a player|an opponent), you may put (?:a|an) ([A-Z][a-z]+) (creature|permanent) card from your hand onto the battlefield\.',
            line)
        if damage_hand:
            # Not hard-coded to Goblins; classify the type of eligible card.
            action=Effect('optional_put_hand_permanent',0,optional=True,
                          library_filter=('subtype',damage_hand[2],damage_hand[3]))
            triggers.append(Trigger('deals_player_damage',Selector(self_only=True,creature=True),action))
            continue
        counter_hit=re.fullmatch(
            r'Whenever a creature you control with a \+1/\+1 counter on it deals combat damage to a player, that player discards a card\.',
            line)
        if counter_hit:
            triggers.append(Trigger('combat_damage',Selector(relation='controller',creature=True),
                                    Effect('discard',1,'damaged player'),min_counters=1))
            continue
        combat=re.fullmatch(r'Whenever a ([A-Z][a-z]+) deals combat damage to a player, that player discards a card\.',line)
        if combat:
            triggers.append(Trigger('combat_damage',Selector(creature=True,subtype=combat[1]),Effect('discard',1,'damaged player')))
            continue
        life_event=re.fullmatch(r'Whenever you gain life, (.+)',line)
        if life_event:
            action=effect(life_event[1])
            if action is None or action.operation not in ('lose_life','gain_life','draw_cards','add_counters'):
                return None
            triggers.append(Trigger('gain_life',Selector(self_only=True),action))
            continue
        casting=re.fullmatch(r'Whenever you cast (?:a|an) (?:(enchantment|artifact|creature|instant|sorcery|planeswalker|noncreature) )?spell, (.+)',line)
        if casting:
            action=effect(casting[2])
            if action is None:return None
            triggers.append(Trigger('cast',Selector(relation='controller',spell_type=casting[1] or 'any'),action))
            continue
        endstep=re.fullmatch(r'At the beginning of your end step, if you gained ([1-9][0-9]*) or more life this turn, (.+)',line)
        if endstep:
            action=effect(endstep[2])
            if action is None:return None
            triggers.append(Trigger('end_step',Selector(self_only=True),action,int(endstep[1])))
            continue
        buffed_endstep=re.fullmatch(
            r'At the beginning of your end step, if you control a creature with power greater than its base power, (create .+)',line)
        if buffed_endstep:
            action=effect(buffed_endstep[1])
            if action is None or action.operation!='create_tokens':return None
            triggers.append(Trigger('end_step',Selector(self_only=True),action,
                                    power_above_base_required=True))
            continue
        endstep_any=re.fullmatch(r'At the beginning of your end step, (.+)',line)
        if endstep_any:
            action=effect(endstep_any[1])
            if action is None:return None
            triggers.append(Trigger('end_step',Selector(self_only=True),action))
            continue
        combat_tokens=re.fullmatch(r'At the beginning of combat on your turn, (create .+)',line)
        if combat_tokens:
            action=effect(combat_tokens[1])
            if action is None or action.operation!='create_tokens':return None
            triggers.append(Trigger('begin_combat',Selector(self_only=True),action))
            continue
        combat_boost=re.fullmatch(
            r'At the beginning of combat on your turn, target enchanted creature or enchantment creature you control gets \+([0-9]+)/\+([0-9]+) and gains ([a-z ]+) until end of turn\.',line)
        if combat_boost:
            if combat_boost[3] not in KEYWORDS-{'flash'}:return None
            triggers.append(Trigger('begin_combat',Selector(self_only=True),
                Effect('combat_target_boost',int(combat_boost[1]),
                       recipient='enchanted_or_enchantment',boost_toughness=int(combat_boost[2]),
                       boost_keyword=combat_boost[3])))
            continue
        upkeep=re.fullmatch(r'At the beginning of your upkeep, (.+)',line)
        if upkeep:
            clause=upkeep[1]
            lands=re.fullmatch(r'if you control (one|two|three|four|five|six|seven|eight|nine|[1-9][0-9]*) or more lands, (.+)',clause)
            if lands:
                count={'one':1,'two':2,'three':3,'four':4,'five':5,'six':6,
                       'seven':7,'eight':8,'nine':9}.get(lands[1])
                if count is None:count=int(lands[1])
                action=effect(lands[2])
                if action is None:return None
                triggers.append(Trigger('upkeep',Selector(self_only=True),action,
                                        lands_controlled_at_least=count))
                continue
            loss=re.fullmatch(r'you lose ([1-9][0-9]*) life and (create .+)',clause)
            action=effect(loss[2] if loss else clause)
            if action is None: return None
            if loss:
                if action.operation!='create_tokens': return None
                action=Effect(action.operation,action.amount,token=action.token,controller_loss=int(loss[1]))
            triggers.append(Trigger('upkeep',Selector(self_only=True),action))
            continue
        conditional_death=re.fullmatch(
            r'Whenever another creature you control dies, put a \+1/\+1 counter on this creature\. If that creature was an? ([A-Z][a-z]+) or ([A-Z][a-z]+), put two \+1/\+1 counters on this creature instead\.',
            line)
        if conditional_death:
            triggers.append(Trigger('dies',Selector(relation='controller',other=True,creature=True),
                Effect('self_counter',1,counter_subtypes=(conditional_death[1],conditional_death[2]),
                       alternate_amount=2)))
            continue
        to_graveyard=re.fullmatch(
            r'Whenever an? ([A-Z][a-z]+|enchantment) you control is put into a graveyard from the battlefield, (you may )?put a \+1/\+1 counter on this creature\.',
            line)
        if to_graveyard:
            scope=to_graveyard[1]
            death_subject=Selector(relation='controller',permanent_type='Enchantment') if scope=='enchantment' else Selector(relation='controller',subtype=scope)
            triggers.append(Trigger('graveyard',death_subject,
                                    Effect('self_counter',1,optional=bool(to_graveyard[2]))))
            continue
        m=re.fullmatch(r'(?:When|Whenever) (.+) (enters(?: the battlefield)?|dies), (.+)',line)
        if not m: return None
        subject=selector(m[1])
        clause=m[3]
        if subject and subject.self_only and clause.startswith('it deals '):clause='this creature deals '+clause[len('it deals '):]
        action=effect(clause)
        if subject is None or action is None: return None
        event='dies' if m[2]=='dies' else 'enters'
        if action.operation=='create_tokens' and not subject.self_only:
            return None  # Repeating token engines need bounded stack/loop handling.
        triggers.append(Trigger(event,subject,action))
    if chosen_type_entry != any(e.subject.chosen_subtype for e in static_effects):return None
    return Program(tuple(triggers),frozenset(keywords),tuple(static_effects),tuple(activations),devotion,life_multiplier,opponent_creatures_enter_tapped,life_addition,tuple(cost_reductions),tuple(counter_replacements),tuple(token_replacements),tuple(token_action_triggers),tuple(token_leave_triggers),tuple(entry_counter_grants),tuple(attack_watchers),chosen_type_entry,opponent_life_gain_becomes_loss,prevent_combat_damage_to_attackers) if triggers or static_effects or activations or devotion or life_multiplier!=1 or opponent_creatures_enter_tapped or life_addition or cost_reductions or counter_replacements or token_replacements or token_action_triggers or token_leave_triggers or entry_counter_grants or attack_watchers or opponent_life_gain_becomes_loss or prevent_combat_damage_to_attackers or keywords else None

def matches(subject, source, entered, is_creature):
    return ((not subject.self_only or source.id==entered.id)
        and (not subject.other or source.id!=entered.id)
        and (not subject.self_or_controlled_subtype or source.id==entered.id or
             (source.controller==entered.controller and subject.self_or_controlled_subtype in entered.definition.subtypes))
        and (subject.relation!='controller' or source.controller==entered.controller)
        and (subject.relation!='opponent' or source.controller!=entered.controller)
        and (not subject.creature or is_creature)
        and (subject.legendary is None or subject.legendary==entered.definition.legendary)
        and (not subject.color or subject.color in entered.definition.colors)
        and (not subject.subtype or subject.subtype in entered.definition.subtypes)
        and (not subject.permanent_type or subject.permanent_type in entered.definition.types)
        and (not subject.chosen_subtype or bool(source.chosen_subtype) and source.chosen_subtype in entered.definition.subtypes)
        and (not subject.attacking or entered.attacking is not None)
        and (not subject.excluded_subtype or subject.excluded_subtype not in entered.definition.subtypes))

def cast_matches(trigger, source, spell, controller):
    if trigger.event!='cast' or source.controller!=controller:return False
    kind=trigger.subject.spell_type
    types=set(spell.printed_types)
    if kind=='any':return True
    if kind=='noncreature':return 'Creature' not in types
    return kind.title() in types

def event_data(trigger, source, subject):
    e=trigger.effect
    labels={'return_controlled_land':'return a controlled land to its owner hand','gain_life':f'controller gains {e.amount} life','draw_cards':f'controller draws {e.amount} cards',
            'reveal_creatures':f'reveal {e.amount} cards and put matching creatures onto the battlefield',
            'damage_board':f'deal {e.amount} damage to opposing player and board','lose_life':f'{e.recipient} loses {e.amount} life',
            'damage':f'deal {e.amount} damage to each opponent','scry':'scry','surveil':'surveil','mill_cards':'move top library cards to graveyards','discard':'damaged player discards a card',
            'damage_any_target':f'may deal {e.amount} damage to any target',
            'add_counters':f'put {e.amount} +1/+1 counters on each {e.counter_subtype or "creature"} you control',
            'create_tokens':f'create {e.amount} creature tokens',
            'opponent_optional_basic_search':'each opponent may find a tapped basic land and shuffle',
            'optional_subtype_search_hand':'controller may tutor a subtype card to hand and shuffle',
            'return_graveyard':'controller may return target subtype card from graveyard to hand',
            'exile_top_cast_permission':'exile the top library card and grant a temporary matching creature cast permission',
            'self_counter':'put +1/+1 counters on the source',
            'combat_target_boost':'target enchanted or enchantment creature gets a temporary bonus and keyword',
            'optional_put_hand_permanent':'controller may put a matching permanent card from hand onto the battlefield',
            'opponent_loss_tapped_creatures':'each opponent loses life equal to controlled tapped creatures'}
    label='; then '.join(f'{part.operation} {part.amount}' for part in e.steps) if e.operation=='ordered_effects' else labels[e.operation]
    if e.controller_loss: label=f'controller loses {e.controller_loss} life; '+label
    if e.gain: label+=f'; controller gains {e.gain} life'
    return {'source':source.id,'name':source.definition.name,'controller':source.controller,
            'effect':label,'operation':e.operation,'recipient':e.recipient,'sourceColors':sorted(source.definition.colors),
            'counterSubtype':e.counter_subtype,'counterSubtypes':e.counter_subtypes,'alternateAmount':e.alternate_amount,
            'boostToughness':e.boost_toughness,'boostKeyword':e.boost_keyword,
            **({'deadSubtypes':sorted(subject.definition.subtypes)} if trigger.event in ('dies','graveyard') else {}),
            'amount':e.amount,'gain':e.gain,'controllerLoss':e.controller_loss,'event':trigger.event,
            'optional':e.optional,
            **({'minLands':trigger.lands_controlled_at_least} if trigger.lands_controlled_at_least else {}),
            **({'requiresBuffedCreature':True} if trigger.power_above_base_required else {}),
            **({'tokenSpec':dict(asdict(e.token),keywords=sorted(e.token.keywords))} if e.token else {}),
            **({'libraryFilter':e.library_filter} if e.library_filter else {}),
            **({'steps':[{'operation':step.operation,'amount':step.amount,'recipient':step.recipient,'gain':step.gain} for step in e.steps]} if e.steps else {}),
            {'enters':'entered','dies':'dead','upkeep':'permanent','end_step':'permanent','cast':'spell','gain_life':'permanent','deals_player_damage':'damageSource','combat_damage':'damageSource','graveyard':'dead','begin_combat':'permanent'}[trigger.event]:subject.id}
