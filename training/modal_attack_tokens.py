"""Strict, reusable modal attack-trigger token instructions.

All clauses must be recognized.  Modes are selected as triggers are put on the
stack; the dynamic number X is evaluated only as the trigger resolves.
"""
import re
from oracle_abilities import KEYWORDS

COLORS={'white','blue','black','red','green'}

PATTERN=re.compile(
    r'(?P<static>[A-Z][a-z]+(?:, [a-z]+)*)\n'
    r'Whenever you attack, choose one (?:—|-)\n'
    r'[•*] Create a tapped and attacking X/X (?P<dcolor>white|blue|black|red|green) '
    r'(?P<dtype>[A-Z][a-z]+) creature token with (?P<dkeyword>[a-z ]+), '
    r'where X is the greatest power among other attacking creatures\.\n'
    r'[•*] Create X (?P<vpower>[0-9]+)/(?P<vtoughness>[0-9]+) '
    r'(?P<vcolor>white|blue|black|red|green) (?P<vtype>[A-Z][a-z]+) '
    r'creature tokens with (?P<vkeyword>[a-z ]+), '
    r'where X is the number of other attacking creatures\.'
)

def parse(text,types):
    if 'Creature' not in types:return ()
    m=PATTERN.fullmatch(text)
    if m is None:return ()
    keywords=frozenset(part.lower() for part in m['static'].split(', '))
    if not keywords or not keywords<=KEYWORDS:return ()
    if any(m[key] not in KEYWORDS for key in ('dkeyword','vkeyword')):return ()
    first=dict(amount=1,power=0,toughness=0,colors=(m['dcolor'].title(),),
               subtypes=(m['dtype'],),keywords=(m['dkeyword'],),tapped=True,attacking=True)
    second=dict(amount=0,power=int(m['vpower']),toughness=int(m['vtoughness']),
                colors=(m['vcolor'].title(),),subtypes=(m['vtype'],),
                keywords=(m['vkeyword'],),tapped=False,attacking=False)
    return (keywords,(first,second))
