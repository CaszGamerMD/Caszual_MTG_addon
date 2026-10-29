"""Strict reveal/filter instructions and printed mana values, independent of names."""
import re

def parse(text):
    m=re.fullmatch(r'reveal the top (one|two|three|four|five|six|seven|eight|nine|ten|[1-9][0-9]*) cards of your library\. Put all ([A-Z][a-z]+) creature cards with mana value ([0-9]+) or less from among them onto the battlefield and the rest on the bottom of your library in a random order\.',text)
    if not m:return None
    count={'one':1,'two':2,'three':3,'four':4,'five':5,'six':6,'seven':7,'eight':8,'nine':9,'ten':10}.get(m[1])
    return (count or int(m[1]),m[2],int(m[3]))

def mana_value(cost):
    """Mana value outside the stack; X is zero. Unknown syntax stays unknown."""
    if not cost:return 0
    parts=re.findall(r'\{([^}]+)\}',cost)
    if ''.join('{'+part+'}' for part in parts)!=cost:return None
    result=0
    for part in parts:
        if part.isdecimal():result+=int(part)
        elif part in ('X','Y','Z'):continue
        elif part in ('W','U','B','R','G','C','S'):result+=1
        elif re.fullmatch(r'[WUBRG]/[WUBRG](?:/P)?|[WUBRG]/P',part):result+=1
        elif re.fullmatch(r'2/[WUBRG]',part):result+=2
        else:return None
    return result
