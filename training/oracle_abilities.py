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

@dataclass(frozen=True)
class Trigger:
    event: str
    subject: Selector
    effect: Effect
    life_gained_at_least: int = 0

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

def static_effect(text):
    subtype_anthem=re.fullmatch(r'Other ([A-Z][a-z]+) creatures you control get \+([0-9]+)/\+([0-9]+) and have (.+)\.',text)
    if subtype_anthem:
        traits={w.strip() for w in re.split(r', | and ',subtype_anthem[4])}
        if not traits or not traits<=KEYWORDS:return None
        subject=Selector(relation='controller',other=True,creature=True,subtype=subtype_anthem[1])
        return (StaticEffect(subject,int(subtype_anthem[2]),int(subtype_anthem[3])),)+tuple(
            StaticEffect(subject,0,0,grant=word) for word in sorted(traits))
    subtype_keyword=re.fullmatch(r'([A-Z][a-z]+)s you control have (.+)\.',text)
    # "Creatures you control" is the older general keyword-anthem grammar.
    # Never treat "Creatures" as an unknown creature subtype.
    if subtype_keyword and subtype_keyword[1]!='Creature':
        traits={w.strip() for w in re.split(r', | and ',subtype_keyword[2])}
        if not traits or not traits<=KEYWORDS:return None
        subject=Selector(relation='controller',creature=True,subtype=subtype_keyword[1])
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
            'trample','haste','defender','reach','deathtouch','indestructible','hexproof','menace'}

def selector(text):
    if text == 'this creature': return Selector(self_only=True,creature=True)
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
    if text=='each opponent may search their library for a basic land card, put it onto the battlefield tapped, then shuffle.':
        return Effect('opponent_optional_basic_search',0,'each opponent')
    gain=re.fullmatch(r'you gain ([1-9][0-9]*) life\.',text)
    if gain:return Effect('gain_life',int(gain[1]))
    drawn=re.fullmatch(r'(?:you )?draw (a|one|two|three|[1-9][0-9]*) cards?\.',text)
    if drawn:return Effect('draw_cards',{'a':1,'one':1,'two':2,'three':3}.get(drawn[1],int(drawn[1]) if drawn[1].isdigit() else 0))
    from library_effects import parse
    library_filter=parse(text)
    if library_filter:return Effect('reveal_creatures',library_filter[0],library_filter=library_filter)
    token=parse_token_creation(text[:1].upper()+text[1:])
    if token: return Effect('create_tokens',token.amount,token=token)
    m=re.fullmatch(r'put (a|[1-9][0-9]*) \+1/\+1 counters? on each creature you control\.',text)
    if m: return Effect('add_counters',1 if m[1]=='a' else int(m[1]),'controlled creatures')
    m=re.fullmatch(r'(each opponent|target player) loses ([1-9][0-9]*) life(?: and you gain ([1-9][0-9]*) life)?\.',text)
    if m: return Effect('lose_life',int(m[2]),m[1],int(m[3] or 0))
    m=re.fullmatch(r'this (?:creature|enchantment|permanent) deals ([1-9][0-9]*) damage to each opponent and each creature and planeswalker they control\.',text)
    if m:return Effect('damage_board',int(m[1]),'opposing board')
    m=re.fullmatch(r'this (?:creature|enchantment|permanent) deals ([1-9][0-9]*) damage to each opponent\.',text)
    if m: return Effect('damage',int(m[1]),'each opponent')
    m=re.fullmatch(r'scry ([1-9][0-9]*)\.',text)
    if m: return Effect('scry',int(m[1]))
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
        if ',' in name:
            text=re.sub(r'\b'+re.escape(name.split(',')[0])+r"(?= isn't a creature| enters| attacks|\'s power)",'this creature',text)
    triggers=[]; keywords=set(); static_effects=[];activations=[];devotion=();life_multiplier=1;opponent_creatures_enter_tapped=False;life_addition=0;cost_reductions=[];counter_replacements=[];token_replacements=[];token_action_triggers=[];token_leave_triggers=[]
    for line in text.splitlines():
        line=line.strip()
        if not line: continue
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
        token_controller=re.fullmatch(r'If an effect would create one or more tokens under your control, it creates twice that many of those tokens instead\.',line)
        if token_controller:
            token_replacements.append(('double',2,'controlled','effect'))
            continue
        token_global=re.fullmatch(r'If one or more tokens would be created, twice that many of those tokens are created instead\.',line)
        if token_global:
            token_replacements.append(('double',2,'any','any'))
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
        words=[w.strip().lower() for w in line.split(',')]
        if all(w in KEYWORDS for w in words):
            keywords.update(words); continue
        static=static_effect(line)
        if static:
            static_effects.extend(static if isinstance(static,tuple) else (static,)); continue
        combat=re.fullmatch(r'Whenever a ([A-Z][a-z]+) deals combat damage to a player, that player discards a card\.',line)
        if combat:
            triggers.append(Trigger('combat_damage',Selector(creature=True,subtype=combat[1]),Effect('discard',1,'damaged player')))
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
        upkeep=re.fullmatch(r'At the beginning of your upkeep, (.+)',line)
        if upkeep:
            clause=upkeep[1]
            loss=re.fullmatch(r'you lose ([1-9][0-9]*) life and (create .+)',clause)
            action=effect(loss[2] if loss else clause)
            if action is None: return None
            if loss:
                if action.operation!='create_tokens': return None
                action=Effect(action.operation,action.amount,token=action.token,controller_loss=int(loss[1]))
            triggers.append(Trigger('upkeep',Selector(self_only=True),action))
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
    return Program(tuple(triggers),frozenset(keywords),tuple(static_effects),tuple(activations),devotion,life_multiplier,opponent_creatures_enter_tapped,life_addition,tuple(cost_reductions),tuple(counter_replacements),tuple(token_replacements),tuple(token_action_triggers),tuple(token_leave_triggers)) if triggers or static_effects or activations or devotion or life_multiplier!=1 or opponent_creatures_enter_tapped or life_addition or cost_reductions or counter_replacements or token_replacements or token_action_triggers or token_leave_triggers else None

def matches(subject, source, entered, is_creature):
    return ((not subject.self_only or source.id==entered.id)
        and (not subject.other or source.id!=entered.id)
        and (subject.relation!='controller' or source.controller==entered.controller)
        and (subject.relation!='opponent' or source.controller!=entered.controller)
        and (not subject.creature or is_creature)
        and (subject.legendary is None or subject.legendary==entered.definition.legendary)
        and (not subject.color or subject.color in entered.definition.colors)
        and (not subject.subtype or subject.subtype in entered.definition.subtypes))

def cast_matches(trigger, source, spell, controller):
    if trigger.event!='cast' or source.controller!=controller:return False
    kind=trigger.subject.spell_type
    types=set(spell.printed_types)
    if kind=='any':return True
    if kind=='noncreature':return 'Creature' not in types
    return kind.title() in types

def event_data(trigger, source, subject):
    e=trigger.effect
    labels={'gain_life':f'controller gains {e.amount} life','draw_cards':f'controller draws {e.amount} cards',
            'reveal_creatures':f'reveal {e.amount} cards and put matching creatures onto the battlefield',
            'damage_board':f'deal {e.amount} damage to opposing player and board','lose_life':f'{e.recipient} loses {e.amount} life',
            'damage':f'deal {e.amount} damage to each opponent','scry':'scry',
            'add_counters':f'put {e.amount} +1/+1 counters on each creature you control',
            'create_tokens':f'create {e.amount} creature tokens',
            'opponent_optional_basic_search':'each opponent may find a tapped basic land and shuffle'}
    label='; then '.join(f'{part.operation} {part.amount}' for part in e.steps) if e.operation=='ordered_effects' else labels[e.operation]
    if e.controller_loss: label=f'controller loses {e.controller_loss} life; '+label
    if e.gain: label+=f'; controller gains {e.gain} life'
    return {'source':source.id,'name':source.definition.name,'controller':source.controller,
            'effect':label,'operation':e.operation,'recipient':e.recipient,'sourceColors':sorted(source.definition.colors),
            'amount':e.amount,'gain':e.gain,'controllerLoss':e.controller_loss,'event':trigger.event,
            **({'tokenSpec':dict(asdict(e.token),keywords=sorted(e.token.keywords))} if e.token else {}),
            **({'libraryFilter':e.library_filter} if e.library_filter else {}),
            **({'steps':[{'operation':step.operation,'amount':step.amount,'recipient':step.recipient,'gain':step.gain} for step in e.steps]} if e.steps else {}),
            {'enters':'entered','dies':'dead','upkeep':'permanent','end_step':'permanent','cast':'spell'}[trigger.event]:subject.id}
