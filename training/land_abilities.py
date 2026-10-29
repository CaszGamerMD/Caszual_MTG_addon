"""Whole-text composition of simple land mana, entry conditions and triggers."""
import re
from oracle_abilities import compile_abilities, Program

BITS={c:1<<i for i,c in enumerate('WUBRGC')}


def compile_land(raw, clean_text):
    if raw.get('types')!=['Land']:return None
    text=clean_text.replace(raw.get('name',''),'this land') if raw.get('name') else clean_text
    # Printed basic land types sometimes put their intrinsic mana in reminders.
    reminder=re.match(r'^\(\{T\}: Add (\{[WUBRGC]\}(?: or \{[WUBRGC]\})*)\.\)',raw.get('oracleText',''))
    lines=[line.strip() for line in text.splitlines() if line.strip()]
    if reminder:lines.append('{T}: Add '+reminder[1]+'.')
    mask=0;production=();entry='';tapped=False;rest=[]
    for line in lines:
        fixed=re.fullmatch(r'\{T\}: Add ((?:\{[WUBRGC]\}){2,})\.',line)
        if fixed:
            if mask or production:return None
            production=tuple(fixed[1].count('{'+c+'}') for c in 'WUBRGC')
            continue
        mana=re.fullmatch(r'\{T\}: Add (\{[WUBRGC]\}(?: or \{[WUBRGC]\})*)\.',line)
        if mana:
            if mask or production:return None
            mask=sum(BITS[c] for c in set(re.findall(r'\{([WUBRGC])\}',mana[1])))
            continue
        if line in ('This land enters tapped.','this land enters tapped.'):
            if entry or tapped:return None
            tapped=True;continue
        reveal=re.fullmatch(r"As this land enters, you may reveal (?:a|an) ([A-Z][a-z]+)(?: or ([A-Z][a-z]+))? card from your hand\. If you don't, this land enters tapped\.",line)
        pay=re.fullmatch(r"As this land enters, you may pay ([1-9][0-9]*) life\. If you don't, it enters tapped\.",line)
        check=re.fullmatch(r'This land enters tapped unless you control (?:a|an) (Plains|Island|Swamp|Mountain|Forest) or (?:a|an) (Plains|Island|Swamp|Mountain|Forest)\.',line)
        if reveal or pay or check:
            if entry or tapped:return None
            if reveal:entry='reveal_types:'+','.join(x for x in reveal.groups() if x)
            elif pay:entry='pay_life:'+pay[1]
            else:entry='has_type:'+check[1]+','+check[2]
            continue
        rest.append(line)
    if not mask and not production:return None
    program=compile_abilities('\n'.join(rest)) if rest else Program((),frozenset())
    # Restrict land composition to complete self-entry triggers; other permanent
    # rule families must be wired into land handling before accepting them.
    if program is None or (rest and (not program.triggers or any(t.event!='enters' or not t.subject.self_only for t in program.triggers))):return None
    if rest and any(not re.fullmatch(r'(?:When|Whenever) this land enters(?: the battlefield)?, .+',line) for line in rest):return None
    return dict(kind='land',mask=mask,tapped=tapped,land_rule=entry,land_program=program,mana_production=production)
