"""Compare baseline, Goblin-swarm and Zurgo commander clock on held-out seeds.

Each seed has the same 100-card decks, shuffle, and alternating Garbo seat.
Wilds always retains the same default policy. The final scoreboard separates
actual rule wins, turn-10 life-score wins, ties, and blocked results.
This is a diagnostic experiment, not production Commander learning.
"""
from __future__ import annotations
import argparse
import json
from collections import Counter
from pathlib import Path
from statistics import mean
import gauntlet
import simulator as s
from garbo_policy import GoblinPlan
from garbo_clock import CommanderClockPolicy

PROFILES=('baseline','swarm','commander-clock')

def actual_win(decision, report, seat):
    return (decision['outcome']=='win' and decision['basis']=='game_rules'
            and decision['winner']==seat and report['result']=='win')

def summarized(rows):
    valid=[r for r in rows if not r['invalidReasons']]
    actual=[r for r in valid if r['actualWin']]
    return dict(games=len(rows),valid=len(valid),blocked=len(rows)-len(valid),
        actualWins=len(actual),
        commanderDamageWins=sum(r['commanderDamageWin'] for r in actual),
        otherRuleWins=sum(not r['commanderDamageWin'] for r in actual),
        turnLimitScoreWins=sum(r['turnLimitScoreWin'] for r in valid),
        losses=sum(r['outcome']=='loss' for r in valid),
        ties=sum(r['outcome']=='tie' for r in valid),
        meanActualWinTurn=round(mean(r['garboTurn'] for r in actual),2) if actual else None,
        fastestActualWinTurn=min((r['garboTurn'] for r in actual),default=None),
        meanFinalCommanderDamage=round(mean(r['commanderDamage'] for r in valid),2) if valid else None,
        meanLifeMargin=round(mean(r['lifeMargin'] for r in valid),2) if valid else None,
        resultsAsFirst=sum(r['actualWin'] and r['garboSeat']==0 for r in valid),
        resultsAsSecond=sum(r['actualWin'] and r['garboSeat']==1 for r in valid))

def coverage(rules,decks):
    found=[]
    for deck in decks:
        unsupported=[]
        identity=set(deck['commanders'][0].get('colorIdentity',[]))
        for role in ('commanders','mainboard'):
            for raw in deck[role]:
                if s.import_diagnostic_card(rules,raw,0,'coverage',identity).kind=='unsupported':
                    unsupported.append(raw['name'])
        found.append(dict(deck=deck['name'],sourceDeckId=deck['sourceDeckId'],
                          unsupported=unsupported,playableCopies=100-sum(
                              c['quantity'] for role in ('commanders','mainboard')
                              for c in deck[role] if c['name'] in unsupported)))
    if any(v['unsupported'] for v in found):
        raise RuntimeError('Both full decks must parse before strategy testing: '+repr(found))
    return found

def run(rules,garbo,wilds,seeds,turns=10,out=None):
    if not seeds or len(set(seeds))!=len(seeds):raise ValueError('Need distinct seeds')
    coverage_report=coverage(rules,[garbo,wilds])
    output=dict(schemaVersion=1,kind='matched-commander-clock-study',
        deckIds=[garbo['sourceDeckId'],wilds['sourceDeckId']],
        coverage=coverage_report,seeds=seeds,turnLimitPerPlayer=turns,
        profiles=PROFILES,learningEligible=False,productionEligible=False,
        notice='Partial two-player Commander diagnostic. A policy is not promoted solely on diagnostic results.',
        matches=[],summary={},pairedSeedComparisons=[])
    first_replays=set()
    for plan in PROFILES:
        for index,seed in enumerate(seeds):
            garbo_seat=index%2
            decks=[garbo,wilds] if garbo_seat==0 else [wilds,garbo]
            policies=[s.Policy(),s.Policy()]
            if plan=='swarm':policies[garbo_seat]=GoblinPlan(plan='swarm')
            if plan=='commander-clock':policies[garbo_seat]=CommanderClockPolicy()
            report=s.diagnose(rules,decks,seed,turns,policies=tuple(policies))
            verdict=gauntlet.adjudicate(report,garbo_seat)
            is_actual=actual_win(verdict,report,garbo_seat)
            scores=verdict['scores']
            last=report['events'][-1]['state']['players']
            damage=(last[1-garbo_seat].get('commanderDamage') or {}).get(
                str(garbo_seat)+'-commander',0)
            eligible=(verdict['outcome']!='blocked' and not verdict['invalidReasons'])
            row=dict(plan=plan,seed=seed,garboSeat=garbo_seat,
                outcome=verdict['outcome'],adjudication=verdict['basis'],
                actualWin=is_actual,commanderDamageWin=bool(is_actual and damage>=21),
                turnLimitScoreWin=(eligible and verdict['outcome']=='win'
                                   and verdict['basis']=='turn_limit_life_score'),
                garboTurn=report['turnsStarted'][garbo_seat],
                commanderDamage=damage,score=scores,
                lifeMargin=(scores[garbo_seat]-scores[1-garbo_seat]
                            if len(scores)==2 else None),
                runtimeQuestions=report['rulesProgress']['runtimeQuestions'],
                invalidReasons=verdict['invalidReasons'],
                garboMulligans=report['openingMulligans'][garbo_seat],
                garboCasts=sum(e.get('actor')==garbo_seat and e['kind']=='cast'
                               for e in report['events']),
                garboAttacks=sum(e.get('actor')==garbo_seat and e['kind']=='attack_group'
                                 for e in report['events']))
            output['matches'].append(row)
            print('CLOCK_GAME '+json.dumps(row),flush=True)
            if is_actual and plan not in first_replays:
                first_replays.add(plan)
                if out:s.export_review(out/(plan+'-first-real-win.json'),report)
            if out:s.write_json(out/'results.json',output)
        output['summary'][plan]=summarized([r for r in output['matches'] if r['plan']==plan])
        print('CLOCK_PROFILE '+json.dumps(dict(plan=plan,**output['summary'][plan])),flush=True)
        if out:s.write_json(out/'results.json',output)
    for seed in seeds:
        bundle={r['plan']:r for r in output['matches'] if r['seed']==seed}
        if set(bundle)==set(PROFILES):
            original,swarm,clock=(bundle[p] for p in PROFILES)
            output['pairedSeedComparisons'].append(dict(seed=seed,
                baselineActualWin=original['actualWin'],
                swarmActualWin=swarm['actualWin'],
                clockActualWin=clock['actualWin'],
                commanderDamageDeltaVsBaseline=clock['commanderDamage']-original['commanderDamage'],
                commanderDamageDeltaVsSwarm=clock['commanderDamage']-swarm['commanderDamage'],
                clockCreatesWin=clock['actualWin'] and not original['actualWin'],
                clockTurnsSaved=(original['garboTurn']-clock['garboTurn']
                                 if original['actualWin'] and clock['actualWin'] else None)))
    if out:s.write_json(out/'results.json',output)
    print('CLOCK_SUMMARY '+json.dumps(dict(seedCount=len(seeds),
        totalGames=len(output['matches']),profiles=output['summary'],
        newRealWins=sum(x['clockCreatesWin'] for x in output['pairedSeedComparisons']))),flush=True)
    return output

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--garbo',type=Path,required=True)
    p.add_argument('--wilds',type=Path,required=True)
    p.add_argument('--seed',type=int,required=True)
    p.add_argument('--games',type=int,default=6)
    p.add_argument('--turns',type=int,default=10)
    p.add_argument('--out',type=Path,required=True)
    args=p.parse_args()
    if args.games<2 or args.games%2:raise ValueError('Use an even game count')
    with s.RulesBridge() as rules:
        run(rules,json.loads(args.garbo.read_text()),json.loads(args.wilds.read_text()),
            list(range(args.seed,args.seed+args.games)),args.turns,args.out)
if __name__=='__main__':
    main()
