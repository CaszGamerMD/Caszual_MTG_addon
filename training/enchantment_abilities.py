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


def compile(text, name, types, subtypes):
    if name:
        text=text.replace(name,'this creature')
        short=name.split(',')[0].split(' of ')[0]
        if short!=name:
            text=re.sub(r'\b'+re.escape(short)+r'(?= enters| attacks)', 'this creature',text)
    rest=[];scale=();role_events=();enchanted_draw=False;attachment_draw=False
    mode='equipment' if 'Artifact' in types and 'Equipment' in subtypes else 'aura' if 'Enchantment' in types and 'Aura' in subtypes else ''
    for line in text.splitlines():
        line=line.strip()
        if not line:continue
        if line=='Whenever this creature enters or attacks, create a Virtuous Role token attached to another target creature you control.':
            if role_events or mode or 'Creature' not in types:return None
            role_events=('enters','attacks');continue
        if line=='Whenever an enchanted creature you control deals combat damage to a player, draw a card.':
            if enchanted_draw or mode:return None
            enchanted_draw=True;continue
        if line=='Enchanted creature has "Whenever this creature deals combat damage to a player, you may draw a card."':
            if attachment_draw or mode!='aura':return None
            attachment_draw=True;continue
        m=re.fullmatch(r'(Enchanted|Equipped) creature gets \+([1-9][0-9]*)/\+([1-9][0-9]*) for each (enchantment|artifact and/or enchantment) you control(?: and has (first strike))?\.',line)
        if m:
            if scale or mode!=('aura' if m[1]=='Enchanted' else 'equipment'):return None
            scale=(int(m[2]),int(m[3]),('Enchantment',) if m[4]=='enchantment' else ('Artifact','Enchantment'))
            if m[5]:rest.append(m[1]+' creature has '+m[5]+'.')
            continue
        rest.append(line)
    if not (scale or role_events or enchanted_draw or attachment_draw):return None
    if mode:
        # A temporary +1/+1 instruction lets the existing strict attachment
        # parser validate every remaining line, even a zero-static-bonus Aura.
        prefix='Enchanted' if mode=='aura' else 'Equipped'
        attachment=parse_attachment('\n'.join(rest+[prefix+' creature gets +1/+1.']),types,subtypes)
        if not attachment:return None
        attachment=attachment[:3]+(attachment[3]-1,attachment[4]-1)
        return EnchantmentProgram(Program((),frozenset()),attachment,scale,attachment_draw=attachment_draw)
    base=compile_abilities('\n'.join(rest)) if rest else Program((),frozenset())
    if base is None:return None
    return EnchantmentProgram(base,role_events=role_events,enchanted_draw=enchanted_draw)
