"""Search paired-seed Garbo policies for a legitimate rules-based win against Wilds.

All games are diagnostic, not learning-eligible. Win by turn-limit life score is
reported separately and never satisfies the first-real-win goal.
"""
import argparse
import json
from pathlib import Path
from collections import Counter
import simulator as s
import gauntlet
from garbo_policy import GoblinPlan

def check_decks(rules,deck_pair):
    coverage=[]
    for deck in deck_pair:
        identity=set(deck['commanders'][0].get('colorIdentity',[]))
        blocked=[]
        for role in ('commanders','mainboard'):
            for card in deck[role]:
                if s.import_diagnostic_card(rules,card,0,'coverage',identity).kind=='unsupported':
                    blocked.append(card['name'])
        coverage.append(dict(name=deck['name'],unsupported=blocked))
    if any(c['unsupported'] for c in coverage):
        raise RuntimeError('Unsupported deck cards cannot count toward the goal: '+str(coverage))
    return coverage

def run(rules,garbo,wilds,seeds,turns=10,out=None):
    if len(seeds)<2 or len(seeds)!=len(set(seeds)):raise ValueError('Need distinct seeds')
    coverage=check_decks(rules,(garbo,wilds))
    result=dict(schemaVersion=1,goal='garbo_first_game_rules_win',
                deckIds=[garbo['sourceDeckId'],wilds['sourceDeckId']],
                coverage=coverage,turnLimitPerPlayer=turns,learningEligible=False,
                notice='Two-player incomplete-rules diagnostic only; no AI promotion.',
                rows=[],profiles={},firstActualWin=None)
    for plan in ('baseline','swarm','counterpunch'):
        summary=Counter()
        for index,seed in enumerate(seeds):
            seat=index%2
            decks=[garbo,wilds] if seat==0 else [wilds,garbo]
            policies=[s.Policy(),s.Policy()]
            if plan!='baseline':policies[seat]=GoblinPlan(plan=plan)
            report=s.diagnose(rules,decks,seed,turns,policies=tuple(policies))
            decision=gauntlet.adjudicate(report,seat)
            winner=(decision['basis']=='game_rules' and decision['winner']==seat
                    and report['result']=='win')
            scores=decision['scores']
            row=dict(plan=plan,seed=seed,garboSeat=seat,
                     outcome=decision['outcome'],basis=decision['basis'],realWin=winner,
                     garboTurn=report['turnsStarted'][seat],
                     score=scores,
                     lifeMargin=(scores[seat]-scores[1-seat] if len(scores)==2 else None),
                     blockedReasons=decision['invalidReasons'],
                     runtimeQuestions=report['rulesProgress']['runtimeQuestions'],
                     openingMulligans=report['openingMulligans'][seat],
                     attacks=sum(e['kind']=='attack_group' and e.get('actor')==seat
                                 for e in report['events']),
                     casts=sum(e['kind']=='cast' and e.get('actor')==seat
                               for e in report['events']))
            result['rows'].append(row)
            summary['realWins']+=int(winner)
            summary['scoreWins']+=int(decision['outcome']=='win' and
                                      decision['basis']=='turn_limit_life_score')
            summary['losses']+=int(decision['outcome']=='loss')
            summary['ties']+=int(decision['outcome']=='tie')
            summary['blocked']+=int(decision['outcome']=='blocked')
            print('GARBO_GAME '+json.dumps(row),flush=True)
            if winner and result['firstActualWin'] is None:
                result['firstActualWin']=dict(plan=plan,seed=seed,garboSeat=seat,
                                              garboTurn=row['garboTurn'])
                if out:s.export_review(out/'first-garbo-rules-win.json',report)
                print('GARBO_FIRST_RULES_WIN '+json.dumps(result['firstActualWin']),flush=True)
            if out:s.write_json(out/'results.json',result)
        result['profiles'][plan]=dict(summary)
        if out:s.write_json(out/'results.json',result)
    print('GARBO_SUMMARY '+json.dumps(dict(firstActualWin=result['firstActualWin'],
                                         profiles=result['profiles'],games=len(result['rows']))),flush=True)
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--garbo',type=Path,required=True)
    p.add_argument('--wilds',type=Path,required=True)
    p.add_argument('--seed',type=int,default=5254666)
    p.add_argument('--games',type=int,default=6)
    p.add_argument('--turns',type=int,default=10)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    with s.RulesBridge() as rules:
        run(rules,json.loads(a.garbo.read_text()),json.loads(a.wilds.read_text()),
            list(range(a.seed,a.seed+a.games)),a.turns,a.out)
if __name__=='__main__':main()
