"""Whole-text composition of simple land mana, entry conditions and triggers."""
import re
import mana_pool
from oracle_abilities import compile_abilities, Program

BITS={c:1<<i for i,c in enumerate('WUBRGC')}


def compile_land(raw, clean_text):
    if raw.get('types')!=['Land']:return None
    text=clean_text.replace(raw.get('name',''),'this land') if raw.get('name') else clean_text
    # Printed basic land types sometimes put their intrinsic mana in reminders.
    reminder=re.match(r'^\(\{T\}: Add (\{[WUBRGC]\}(?: or \{[WUBRGC]\})*)\.\)',raw.get('oracleText',''))
    lines=[line.strip() for line in text.splitlines() if line.strip()]
    if reminder:lines.append('{T}: Add '+reminder[1]+'.')
    mask=0;production=();entry='';tapped=False;rest=[];counter_ability='';counter_scope='all'
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
        team_counters=re.fullmatch(
            r'((?:\{(?:[0-9]+|[WUBRGC])\})+), \{T\}: Put a \+1/\+1 counter on each creature you control\.',line)
        if team_counters:
            if counter_ability or mana_pool.requirements(team_counters[1]) is None:return None
            counter_ability=team_counters[1]
            continue
        recent=re.fullmatch(r'\{T\}: Put a \+1/\+1 counter on each (white|blue|black|red|green) creature that entered this turn\.',line)
        if recent:
            if counter_ability:return None
            counter_ability='{0}';counter_scope='entered:'+recent[1].title()
            continue
        rest.append(line)
    if not mask and not production:return None
    program=compile_abilities('\n'.join(rest)) if rest else Program((),frozenset())
    # Land keywords and self-entry triggers can compose with mana and tapped
    # entry. Do not silently accept any other static/activated/replacement
    # program: its semantics may not be wired into land handling.
    if program is None:return None
    if rest:
        if any(line!='Indestructible' and not re.fullmatch(
                r'(?:When|Whenever) this land enters(?: the battlefield)?, .+',line)
               for line in rest):return None
        if any(t.event!='enters' or not t.subject.self_only for t in program.triggers):return None
        if program.keywords-{'indestructible'} or program.static_effects or program.activations:return None
        if program.devotion or program.cost_reductions or program.counter_replacements or program.token_replacements:return None
    return dict(kind='land',mask=mask,tapped=tapped,land_rule=entry,land_program=program,mana_production=production,land_counter_ability=counter_ability,land_counter_scope=counter_scope)
