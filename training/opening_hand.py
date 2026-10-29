"""Pure early-game evaluator for friendly Commander opening sevens."""
from itertools import permutations
import mana_pool

FRIENDLY_MULLIGAN_LIMIT=16
PROACTIVE={"creature","vehicle","enchantment","spell","token_spell",
           "mana_artifact","equipment","planeswalker","station","artifact","x_spell"}

def _cost(card):
    if card.kind not in PROACTIVE:return None
    text=card.mana_cost.replace("{X}","{1}") if card.kind=="x_spell" else card.mana_cost
    needs=mana_pool.requirements(text)
    return text if needs is not None and len(needs)<=3 else None

def _sources(card):
    if card.mana_production and len(card.mana_production)==6:
        return (tuple(card.mana_production),)
    mask=card.mask
    definition=card.event_definition
    if definition and "Land" in definition.types:
        for subtype,bit in (("Plains",1),("Island",2),("Swamp",4),("Mountain",8),("Forest",16)):
            if subtype in definition.subtypes:mask|=bit
    return tuple(tuple(int(i==color) for i in range(6))
                 for color in range(6) if mask&(1<<color))

def _tapped(card,earlier,hand):
    rule=card.land_rule
    if rule=="two_other_lands":return len(earlier)<2
    if rule=="two_basics":return sum(bool(c.basic_land) for c in earlier)<2
    if rule.startswith("has_type:"):
        kinds=set(rule.split(":",1)[1].split(","))
        return not any(kinds.intersection(c.land_subtypes) for c in earlier)
    if rule.startswith("reveal_types:"):
        kinds=set(rule.split(":",1)[1].split(","))
        return not any(c.id!=card.id and kinds.intersection(c.land_subtypes) for c in hand)
    if rule.startswith("pay_life:"):return False
    return bool(card.enters_tapped)

def _pay(cost,sources):
    return mana_pool.plan(cost,[0]*6,sources)["paid"]

def assess(hand):
    """Check a feasible 3-land, 2-spell schedule across turns 1, 2, 3.

    No library peeking; only own seven known cards. The same turn cannot
    spend the same mana source on two different spells.
    """
    hand=tuple(hand)
    lands=tuple(c for c in hand if c.kind=="land")
    spells=tuple((c,cost) for c in hand if c.kind!="land"
                 if (cost:=_cost(c)) is not None)
    result={"keep":False,"lands":len(lands),"early":len(spells),"castable":0}
    if not 3<=len(lands)<=4 or len(spells)<2:return result
    for order in permutations(lands,3):
        turns=[]
        for turn in range(3):
            now=order[:turn]+(() if _tapped(order[turn],order[:turn],hand) else (order[turn],))
            turns.append([(land.id,_sources(land)) for land in now if _sources(land)])
        result["castable"]=max(result["castable"],
            sum(any(_pay(cost,available) for available in turns) for _,cost in spells))
        if result["castable"]<2:continue
        for i,(_,first) in enumerate(spells):
            for _,second in spells[i+1:]:
                for a in range(3):
                    if not _pay(first,turns[a]):continue
                    for b in range(a,3):
                        if _pay(first+second,turns[a]) if a==b else _pay(second,turns[b]):
                            return dict(result,keep=True)
    return result

def fallback(hand):
    """After several free attempts, accept a functional rather than perfect curve.

    Two to five lands and at least one affordable early board-development
    spell are enough to avoid an unplayable one-land safety-cap hand.
    """
    lands=[c for c in hand if c.kind=="land"]
    if not 2<=len(lands)<=5:return False
    candidates=[cost for c in hand if c.kind!="land"
                if (cost:=_cost(c)) is not None]
    if not candidates:return False
    from itertools import combinations
    for n in (2,3):
        for group in combinations(lands,min(n,len(lands))):
            sources=[(c.id,_sources(c)) for c in group if _sources(c)]
            if any(_pay(cost,sources) for cost in candidates):
                return True
    return False
