"""Diagnostic mana accounting. Plans are pure; casting commits the returned pool."""
import re
from functools import lru_cache

COLORS = 'WUBRGC'
ZERO = (0,)*6

def production(text):
    """Whole unconditional tap ability; no ignored drawbacks or additional costs."""
    m = re.fullmatch(r'\{T\}: Add ((?:\{[WUBRGC]\})+)\.', text.strip())
    if not m: return None
    return tuple(m[1].count('{'+c+'}') for c in COLORS)

def requirements(cost, x=None):
    symbols = re.findall(r'\{([^{}]+)\}',cost)
    if not symbols or ''.join('{'+s+'}' for s in symbols) != cost: return None
    result=[]; generic=0
    for symbol in symbols:
        if len(symbol)==1 and symbol in COLORS: result.append(1<<COLORS.index(symbol))
        elif re.fullmatch(r'[WUBRG]/[WUBRG]',symbol) and symbol[0]!=symbol[2]:
            result.append((1<<COLORS.index(symbol[0]))|(1<<COLORS.index(symbol[2])))
        elif re.fullmatch(r'[0-9]{1,2}',symbol): generic+=int(symbol)
        elif symbol=='X' and type(x) is int and x>=0: generic+=x
        else: return None
    return tuple(sorted(result,key=int.bit_count)+[63]*generic)

def plan(cost, pool, sources, x=None):
    """Sources: (unique id, tuple of possible six-color production vectors)."""
    needs=requirements(cost,x)
    if needs is None: return {'paid':False}
    pool=tuple(pool)
    if len(pool)!=6 or any(type(n) is not int or n<0 for n in pool): raise ValueError('Invalid mana pool')
    if len({s[0] for s in sources})!=len(sources): return {'paid':False}
    @lru_cache(None)
    def solve(step,remaining,used):
        if step==len(needs): return (),remaining
        mask=needs[step]
        for color in range(6):
            if remaining[color] and mask&(1<<color):
                after=list(remaining);after[color]-=1
                answer=solve(step+1,tuple(after),used)
                if answer is not None: return answer
        for i,(identifier,options) in enumerate(sources):
            if used&(1<<i): continue
            for vector in options:
                if not any(vector[c] and mask&(1<<c) for c in range(6)): continue
                answer=solve(step,tuple(a+b for a,b in zip(remaining,vector)),used|(1<<i))
                if answer is not None:
                    chosen,left=answer
                    return (identifier,)+chosen,left
        return None
    # Avoid searching permutations when there cannot be enough mana in total.
    if sum(pool)+sum(max(map(sum,opts)) for _,opts in sources)<len(needs): return {'paid':False}
    answer=solve(0,pool,0)
    if answer is None: return {'paid':False}
    chosen,left=answer
    return {'paid':True,'sources':list(chosen),'pool':list(left)}
