"""Complete modal Role-creation trigger grammar, not card-name dispatch.

Only Roles with implemented static and granted triggered abilities are valid.
An optional choice among supported Role tokens is chosen at trigger placement.
"""
import re

SUPPORTED_ROLES=('Royal','Sorcerer','Monster')

def parse(text,name,types):
    if 'Creature' not in types:return ()
    # Oracle wording may use either the complete self name or a unique short
    # name. Never normalize arbitrary creature names.
    normalized=text.replace(name,'this creature')
    if name:
        short=name.split(',')[0]
        normalized=re.sub(r'^Whenever '+re.escape(short)+r'(?= or another nontoken creature)',
                          'Whenever this creature',normalized)
    lines=normalized.splitlines()
    if not re.fullmatch(
        r'Whenever this creature or another nontoken creature (?:enters|enters the battlefield) under your control, choose one [—-]',
        lines[0] if lines else ''):
        return ()
    choices=[]
    for line in lines[1:]:
        m=re.fullmatch(r'[•*] Create a ([A-Z][a-z]+) Role token attached to that creature\.',line.strip())
        if not m or m[1] not in SUPPORTED_ROLES or m[1] in choices:return ()
        choices.append(m[1])
    return tuple(choices) if len(choices)>=2 else ()
