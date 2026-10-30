"""Whole-Oracle basic land subtype replacement/addition, not name exceptions."""
import re

BASIC_TYPES=('Plains','Island','Swamp','Mountain','Forest')
PLURALS={'Plains':'Plains','Island':'Islands','Swamp':'Swamps','Mountain':'Mountains','Forest':'Forests'}


def additional_land_plays(text):
    m=re.fullmatch(
        r'You may play (an|one|two|three|[1-9][0-9]*) additional lands? on each of your turns\\.\\n'
        r'Lands you control (?:are|have) every basic land type in addition to their other types\\.',text)
    return {'an':1,'one':1,'two':2,'three':3}.get(m[1],int(m[1]) if m[1].isdigit() else 0) if m else 0


def parse(text, types):
    if not set(types).intersection({'Land','Enchantment','Creature','Artifact'}):
        return ()
    # Whole-text composition: additional land plays plus all five basic types.
    # Neither part is granted if any other Oracle instruction remains unparsed.
    basics=re.fullmatch(
        r'(?:You may play (an|one|two|three|[1-9][0-9]*) additional lands? on each of your turns\\.\\n)?'
        r'Lands you control (?:are|have) every basic land type in addition to their other types\\.',text)
    if basics:return ('controller','add',BASIC_TYPES)
    replacement=re.fullmatch(r'Nonbasic lands are (Plains|Islands|Swamps|Mountains|Forests)\.',text)
    if replacement:
        return ('nonbasic','replace',(next(k for k,v in PLURALS.items() if v==replacement[1]),))
    addition=re.fullmatch(r'Each land is a (Plains|Island|Swamp|Mountain|Forest) in addition to its other land types\.',text)
    if addition:
        return ('all','add',(addition[1],))
    return ()
