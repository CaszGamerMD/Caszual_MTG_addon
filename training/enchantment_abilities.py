"""Whole-text composition for enchantment counts, Virtuous Roles and combat draw."""
from dataclasses import dataclass
import re
from oracle_abilities import Program, compile_abilities
from attachments import parse as parse_attachment


@dataclass(frozen=True)
class EnchantmentProgram:
    base: Program
    attachment: tuple = ()
    scale: tuple = ()
    role_events: tuple = ()
    enchanted_draw: bool = False
    attachment_draw: bool = False
    damage_events: tuple = ()
    upkeep_attachment_counters: int = 0
    entry_attachment_counters: int = 0
    double_attachment_counters_upkeep: bool = False
    aura_graveyard_draw: bool = False
    living_weapon: bool = False
    equipment_return_dying: bool = False


def compile(text, name, types, subtypes):
    if name:
        text=text.replace(name,'this creature')
        short=name.split(',')[0].split(' of ')[0]
        if short!=name:
            text=re.sub(r'\b'+re.escape(short)+r'(?= enters| attacks)', 'this creature',text)
    rest=[];scale=();role_events=();enchanted_draw=False;attachment_draw=False;damage_events=[];upkeep_attachment_counters=0;entry_attachment_counters=0;double_attachment_counters_upkeep=False;aura_graveyard_draw=False;entry_token_lines=[]
    mode='equipment' if 'Artifact' in types and 'Equipment' in subtypes else 'aura' if 'Enchantment' in types and 'Aura' in subtypes else ''
    living_weapon=False;equipment_return_dying=False
    for line in text.splitlines():
        line=line.strip()
        if not line:continue
        if line=="Whenever equipped creature dies, return it to its owner's hand.":
            if mode!='equipment' or equipment_return_dying:return None
            equipment_return_dying=True
            continue
        if line=='Living weapon':
            if mode!='equipment' or living_weapon:return None
            living_weapon=True
            continue
        if mode=='aura' and line.startswith('When this Aura enters, create '):
            # Aura ETB is a normal triggered ability: the token is created
            # only after the trigger resolves, even if the Aura has left.
            normalized='When this enchantment enters, '+line[len('When this Aura enters, '):]
            entry=compile_abilities(normalized)
            if not entry or len(entry.triggers)!=1 or entry.triggers[0].effect.operation!='create_tokens':
                return None
            entry_token_lines.append(normalized)
            continue
        if line=='When this Aura is put into a graveyard from the battlefield, draw a card.':
            if mode!='aura' or aura_graveyard_draw:return None
            aura_graveyard_draw=True
            continue
        if line=='Whenever this creature enters or attacks, create a Virtuous Role token attached to another target creature you control.':
            if role_events or mode or 'Creature' not in types:return None
            role_events=('enters','attacks');continue
        if line=='Whenever an enchanted creature you control deals combat damage to a player, draw a card.':
            if enchanted_draw or mode:return None
            enchanted_draw=True;continue
        if line=='Enchanted creature has "Whenever this creature deals combat damage to a player, you may draw a card."':
            if attachment_draw or mode!='aura':return None
            attachment_draw=True;continue
        entry=re.fullmatch(r'When this Aura enters, put a \+1/\+1 counter on enchanted creature\.',line)
        if entry:
            if mode!='aura' or entry_attachment_counters:return None
            entry_attachment_counters=1;continue
        if line=='At the beginning of your upkeep, double the number of +1/+1 counters on enchanted creature.':
            if mode!='aura' or double_attachment_counters_upkeep:return None
            double_attachment_counters_upkeep=True;continue
        upkeep=re.fullmatch(r'At the beginning of your upkeep, put (a|one|two|three|[1-9][0-9]*) \+1/\+1 counters? on enchanted creature\.',line)
        if upkeep:
            if mode!='aura' or upkeep_attachment_counters:return None
            upkeep_attachment_counters={'a':1,'one':1,'two':2,'three':3}.get(upkeep[1]) or int(upkeep[1])
            continue
        if line=='Whenever enchanted creature deals damage, you gain that much life.':
            if mode!='aura' or 'gain_damage' in damage_events:return None
            damage_events.append('gain_damage');continue
        if line=='Whenever enchanted creature deals damage to an opponent, you may draw a card.':
            if mode!='aura' or 'optional_draw_opponent' in damage_events:return None
            damage_events.append('optional_draw_opponent');continue
        m=re.fullmatch(
            r'(Enchanted|Equipped) creature gets \+([1-9][0-9]*)/\+([1-9][0-9]*) for each '
            r'(artifact|creature|enchantment)(?: and/or (artifact|creature|enchantment))? you control'
            r'(?: and has (first strike))?\.',line)
        if m:
            if scale or mode!=('aura' if m[1]=='Enchanted' else 'equipment'):return None
            requested=(m[4],)+((m[5],) if m[5] else ())
            if len(set(requested))!=len(requested):return None
            # Any permanent matching either printed type contributes only once.
            scale=(int(m[2]),int(m[3]),tuple(word.title() for word in requested))
            if m[6]:rest.append(m[1]+' creature has '+m[6]+'.')
            continue
        rest.append(line)
    if not (scale or role_events or enchanted_draw or attachment_draw or damage_events or upkeep_attachment_counters or entry_attachment_counters or double_attachment_counters_upkeep or aura_graveyard_draw or entry_token_lines or living_weapon or equipment_return_dying):return None
    if mode:
        # A temporary +1/+1 instruction lets the existing strict attachment
        # parser validate every remaining line, even a zero-static-bonus Aura.
        prefix='Enchanted' if mode=='aura' else 'Equipped'
        attachment=parse_attachment('\n'.join(rest+[prefix+' creature gets +1/+1.']),types,subtypes)
        if not attachment:return None
        attachment=attachment[:3]+(attachment[3]-1,attachment[4]-1)+attachment[5:]
        base=compile_abilities('\n'.join(entry_token_lines)) if entry_token_lines else Program((),frozenset())
        if base is None:return None
        return EnchantmentProgram(base,attachment,scale,attachment_draw=attachment_draw,damage_events=tuple(damage_events),upkeep_attachment_counters=upkeep_attachment_counters,entry_attachment_counters=entry_attachment_counters,
                                  double_attachment_counters_upkeep=double_attachment_counters_upkeep,aura_graveyard_draw=aura_graveyard_draw,
                                  living_weapon=living_weapon,equipment_return_dying=equipment_return_dying)
    base=compile_abilities('\n'.join(rest)) if rest else Program((),frozenset())
    if base is None:return None
    return EnchantmentProgram(base,role_events=role_events,enchanted_draw=enchanted_draw)
