"""Reproduce the first Garbo win and identify observed public win condition.

This is an incomplete-rules two-player diagnostic, not Commander certification.
"""
from pathlib import Path
import json
import simulator as s
import gauntlet
from garbo_policy import GoblinPlan

def run(out):
    decks=[json.loads((s.HERE/'decks'/name).read_text()) for name in (
        '5254666-garbo-gobbos.json','5189995-enchantments.json')]
    findings=[]
    with s.RulesBridge() as rules:
        for plan in ('baseline','swarm','counterpunch'):
            policies=(s.Policy(),s.Policy()) if plan=='baseline' else (GoblinPlan(plan=plan),s.Policy())
            report=s.diagnose(rules,decks,5254666,10,policies=policies)
            decision=gauntlet.adjudicate(report,0)
            if not (report['result']=='win' and decision['basis']=='game_rules' and decision['winner']==0):
                raise RuntimeError('Previously observed win did not reproduce: '+plan+str(decision))
            final=report['events'][-1]['state']['players']
            commander_damage=final[1].get('commanderDamage',{})
            events=[dict(kind=e['kind'],actor=e.get('actor'),
                        message=e.get('message'),details=e.get('details'))
                    for e in report['events']
                    if e['kind'] in ('result','attack_group','group_damage',
                                    'commander_damage','cast')]
            finding=dict(plan=plan,seed=5254666,garboSeat=0,
                         garboWinTurn=report['turnsStarted'][0],
                         turns=report['turnsStarted'],
                         garboLife=final[0]['life'],wildsLife=final[1]['life'],
                         wildsCommanderDamage=commander_damage,
                         result=report['result'],
                         runtimeQuestions=report['rulesProgress']['runtimeQuestions'],
                         evidence=events)
            findings.append(finding)
            s.export_review(out/(plan+'.json'),report)
            print('GARBO_REPLAY '+json.dumps({k:v for k,v in finding.items() if k!='evidence'}),flush=True)
    s.write_json(out/'postmortem.json',dict(schemaVersion=1,
        findings=findings,goal='compare_same_seed_win_routes',
        note='Observed simulator event traces, not independent Commander rules validation'))
    return findings

if __name__=='__main__':
    run(s.HERE/'reports/garbo-first-win-postmortem')
