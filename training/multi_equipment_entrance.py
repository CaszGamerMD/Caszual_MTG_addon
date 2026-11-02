"""ETB/attack triggered multi-Equipment attachment with target selection.

All target Equipment are selected when the trigger enters the stack; control
of the attached artifacts is never changed by attachment.
"""
import re


def parse(text,name,types):
    if 'Creature' not in types:return False
    subject='(?:this creature|'+re.escape(name)+')'
    return bool(re.fullmatch(
        rf'Whenever {subject} enters or attacks, you may attach any number of '
        r'target Equipment to it\.',text))
