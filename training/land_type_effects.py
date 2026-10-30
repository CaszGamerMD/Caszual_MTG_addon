"""Whole-Oracle basic land subtype replacement/addition, not name exceptions."""
import re

BASIC_TYPES=('Plains','Island','Swamp','Mountain','Forest')
PLURALS={'Plains':'Plains','Island':'Islands','Swamp':'Swamps','Mountain':'Mountains','Forest':'Forests'}


def parse(text, types):
    if not set(types).intersection({'Land','Enchantment','Creature','Artifact'}):
        return ()
    replacement=re.fullmatch(r'Nonbasic lands are (Plains|Islands|Swamps|Mountains|Forests)\.',text)
    if replacement:
        return ('nonbasic','replace',(next(k for k,v in PLURALS.items() if v==replacement[1]),))
    addition=re.fullmatch(r'Each land is a (Plains|Island|Swamp|Mountain|Forest) in addition to its other land types\.',text)
    if addition:
        return ('all','add',(addition[1],))
    return ()
