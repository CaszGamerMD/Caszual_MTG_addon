"""Whole-text attachment ability grammar."""
import re
from oracle_abilities import KEYWORDS

def parse(text,types,subtypes):
    mode='equipment' if 'Artifact' in types and 'Equipment' in subtypes else 'aura' if 'Enchantment' in types and 'Aura' in subtypes else ''
    if not mode:return None
    lines=text.splitlines();cost=None;abilities=set();power=toughness=0
    restriction=''
    if mode=='aura':
        if not lines:return None
        enchant=lines.pop(0)
        if enchant in ('Enchant creature','Enchant creature you control'):
            restriction='controller' if enchant=='Enchant creature you control' else ''
        else:
            land=re.fullmatch(r'Enchant (land|snow land|Mountain) you control',enchant)
            if not land:return None
            restriction={'land':'land:controller','snow land':'land:snow:controller',
                         'Mountain':'land:mountain:controller'}[land[1]]
    prefix='Equipped' if mode=='equipment' else 'Enchanted'
    if restriction.startswith('land:'):prefix='Enchanted land'
    for line in lines:
        line=line.strip()
        m=re.fullmatch(r'Equip ((?:\{(?:[0-9]{1,2}|[WUBRGC])\})+)',line)
        if m and mode=='equipment':cost=m[1];continue
        m=re.fullmatch((prefix if prefix=='Enchanted land' else prefix+' creature')+r' has (.+)\.',line)
        if m:
            keywords=set(re.split(r', | and ',m[1].replace(', and ', ', ')))
            if not keywords<=KEYWORDS:return None
            abilities.update(keywords);continue
        m=re.fullmatch(prefix+r' creature gets \+([0-9]+)/\+([0-9]+)(?: and has (.+))?\.',line) if prefix!='Enchanted land' else None
        if m:
            keywords=set(re.split(r', | and ',(m[3] or '').replace(', and ', ', ')))-{''}
            if not keywords<=KEYWORDS:return None
            abilities.update(keywords);power+=int(m[1]);toughness+=int(m[2]);continue
        return None
    if not abilities and not power and not toughness:return None
    if mode=='equipment' and cost is None:return None
    result=(mode,cost,frozenset(abilities),power,toughness)
    # Optional sixth element preserves the legacy five-field attachment layout.
    return result+((restriction,) if restriction else ())

def parse_bestow(text,types):
    """Keyword-only enchantment creatures with fixed enchanted-creature grants."""
    if not {'Creature','Enchantment'}<=types:return None
    lines=[line.strip() for line in text.splitlines() if line.strip()]
    if not lines:return None
    cost=re.fullmatch(r'Bestow ((?:\{(?:[0-9]{1,2}|[WUBRGC])\})+)',lines.pop(0))
    if not cost:return None
    intrinsic=set();enchanted=[]
    for line in lines:
        words={w.strip().lower() for w in line.split(',')}
        if words<=KEYWORDS-{'flash'}:intrinsic.update(words)
        else:enchanted.append(line)
    attachment=parse('\n'.join(['Enchant creature']+enchanted),{'Enchantment'},{'Aura'})
    if not attachment:return None
    return cost[1],frozenset(intrinsic),attachment

def parse_equipment_removals(text,types,subtypes):
    """Compose an equipment program with paid, temporary opposing ability loss."""
    if not {'Artifact'}<=types or 'Equipment' not in subtypes:return None
    lines=[];removals=[]
    for line in text.splitlines():
        line=line.strip()
        m=re.fullmatch(r'((?:\{(?:[0-9]{1,2}|[WUBRGC])\})+): Permanents your opponents control lose (.+) until end of turn\.',line)
        if not m:lines.append(line);continue
        abilities=frozenset(re.split(r', | and ',m[2]))
        if not abilities or not abilities<={'hexproof','indestructible'}:return None
        if all(part=='0' for part in re.findall(r'\{([^}]+)\}',m[1])):return None
        removals.append((m[1],abilities))
    attachment=parse('\n'.join(lines),types,subtypes)
    return (attachment,tuple(removals)) if attachment and removals else None


def parse_with_intrinsic(text,types,subtypes):
    """Compose source protection keywords with a complete attachment program.

    Source abilities and equipped-creature grants remain distinct; unsupported
    intrinsic keywords are rejected until their timing/activation is modeled.
    """
    intrinsic=set();rest=[]
    for line in text.splitlines():
        words={word.strip().lower() for word in re.split(r', | and ',line.replace(', and ', ', '))}
        if words and words<={'indestructible','hexproof'}:intrinsic.update(words)
        else:rest.append(line)
    attachment=parse('\n'.join(rest),types,subtypes)
    return (frozenset(intrinsic),attachment) if attachment else None
