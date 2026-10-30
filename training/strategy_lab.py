"""Experimental real-deck strategy A/B; never promote diagnostic scores to rules-trained AI.

For each seed, both variants see the same physical decks and shuffle sequence.
Only the controlled deck's public-observation decision weights change. Every
invalid/question-blocked game stays out of the strategy comparison.
"""
from __future__ import annotations
import argparse
import json
import math
import subprocess
from dataclasses import replace
from pathlib import Path
from statistics import mean

import gauntlet
import simulator as s

# Hand-designed hypotheses to test, NOT learned champions.
PROFILE_DELTAS = {
    'tempo': {'damage': 2.5, 'haste': 0.8, 'evasion': 0.6,
              'draw': 0.15, 'cost': -0.25, 'pass': -1.0,
              'toughness': -0.15, 'survive': -0.2},
    'patient': {'survive': 1.0, 'toughness': 0.45, 'draw': 0.5,
                'damage': -0.6, 'cost': 0.1, 'life': 0.15},
}


def policy_for(profile):
    if profile == 'baseline':
        return s.Policy()
    if profile not in PROFILE_DELTAS:
        raise ValueError('Unknown experimental strategy')
    values={k:v for k,v in zip(s.FEATURES,s.Policy().weights)}
    for key,delta in PROFILE_DELTAS[profile].items():
        values[key] += delta
    weights=tuple(values[k] for k in s.FEATURES)
    return replace(s.Policy(),weights=weights,version=1)


def results_for(matches, deck_id, profile):
    """No credit for a paused, unsupported, or rules-question match."""
    rows=[]
    for match in matches:
        if match['outcome']=='blocked':
            rows.append(dict(seed=match['seed'],profile=profile,status='blocked',
                             invalidReasons=match['invalidReasons']))
            continue
        seat=match['focalSeat'] if deck_id==5189995 else 1-match['focalSeat']
        deck_won = match['winner'] == seat
        is_tie = match['winner'] is None
        rule_win=bool(deck_won and match['adjudication']=='game_rules')
        turns=match.get('turnsStarted', match['telemetry'].get('turnsStarted'))[seat]
        rows.append(dict(seed=match['seed'],profile=profile,
            status='tie' if is_tie else 'win' if deck_won else 'loss',
            ruleWin=rule_win,actualWinTurn=turns if rule_win else None,
            scoreWin=bool(deck_won and match['adjudication']=='turn_limit_life_score'),
            turnLimit=match['adjudication']=='turn_limit_life_score',
            first=seat==0,life=match['scores'][seat],
            lifeMargin=match['scores'][seat]-match['scores'][1-seat],
            runtimeQuestions=match['telemetry']['runtimeQuestionCount'],
            lands=match['telemetry']['landDropsBySeat'][seat],
            casts=match['telemetry']['spellsCastBySeat'][seat],
            attacks=match['telemetry']['attacksBySeat'][seat],
            mulligans=match['telemetry']['openingMulligans'][seat]))
    return rows


def summarize(rows):
    clean=[x for x in rows if x['status']!='blocked']
    wins=[x for x in clean if x['status']=='win']
    rule_wins=[x for x in wins if x['ruleWin']]
    return dict(games=len(rows),valid=len(clean),blocked=len(rows)-len(clean),
        wins=len(wins),losses=sum(x['status']=='loss' for x in clean),
        ties=sum(x['status']=='tie' for x in clean),
        ruleWins=len(rule_wins),scoreWins=sum(x['scoreWin'] for x in wins),
        averageRealWinTurn=round(mean(x['actualWinTurn'] for x in rule_wins),3)
                              if rule_wins else None,
        fastestRealWinTurn=min((x['actualWinTurn'] for x in rule_wins),default=None),
        averageLifeMargin=round(mean(x['lifeMargin'] for x in clean),3) if clean else None,
        averageMulligans=round(mean(x['mulligans'] for x in clean),3) if clean else None)


def compare(baseline, candidate):
    """Win count is primary. Win turn only breaks ties in game-rules wins."""
    if (len(baseline)!=len(candidate) or
        [r['seed'] for r in baseline]!=[r['seed'] for r in candidate]):
        raise ValueError('Matched strategy comparisons require identical seeds/order')
    a,b=summarize(baseline),summarize(candidate)
    if a['blocked'] or b['blocked']:
        return dict(validComparison=False,reason='Rules-blocked match; no policy promotion',
                    baseline=a,candidate=b,promote=False)
    # Retain sample-size and win-loss protection. Clock-score wins are lower
    # evidence than wins from actual game rules.
    key=lambda row:(row['wins'],row['ruleWins'],
        -(row['averageRealWinTurn'] if row['averageRealWinTurn'] is not None else 10000),
        row['averageLifeMargin'])
    return dict(validComparison=True,baseline=a,candidate=b,
                promote=False,  # incomplete Commander model forbids promotion
                provisionalImprovement=key(b)>key(a),
                notes='Candidate ranking is a diagnostic hypothesis only, not trained or rules-certified.')


def run(rules,focal,opponent,baseline_report,games=4,profile='tempo',seed=5189995):
    if games<2 or games%2 or profile=='baseline':raise ValueError('Use even games and a candidate profile')
    if baseline_report['engineCommit']!=subprocess.check_output(
           ['git','rev-parse','HEAD'],text=True,cwd=s.ROOT).strip():
        raise ValueError('Baseline and candidate must share exact engine commit')
    matches=baseline_report['matches'][:games]
    if len(matches)!=games or any(r['seed']!=seed+i for i,r in enumerate(matches)):
        raise ValueError('No same-seed baseline matches')
    results=dict(schemaVersion=1,engineCommit=baseline_report['engineCommit'],
        profile=profile,deckIds=[focal['sourceDeckId'],opponent['sourceDeckId']],
        seeds=[seed+i for i in range(games)],diagnostic=True,learningEligible=False,
        notice='Policy hypotheses only. No legal Commander certification or strategy promotion.',
        comparisons={},matchData=[])
    candidate=policy_for(profile)
    for controlled_deck in (focal,opponent):
        target=controlled_deck['sourceDeckId']
        candidate_matches=[]
        for i in range(games):
            baseline_row=matches[i]
            seat=i%2 if target==focal['sourceDeckId'] else 1-i%2
            decks=[focal,opponent] if i%2==0 else [opponent,focal]
            policies=[s.Policy(),s.Policy()]
            policies[seat]=candidate
            report=s.diagnose(rules,decks,seed+i,10,policies=tuple(policies))
            verdict=gauntlet.adjudicate(report,i%2)
            # If a newly encountered unsupported card remains, block rather than score.
            if any(d['unsupportedCards'] for d in baseline_report['coverage']):
                verdict=dict(outcome='blocked',winner=None,basis='invalid',
                             scores=verdict['scores'],invalidReasons=['unsupported_in_deck'])
            stats=gauntlet.match_telemetry(report)
            candidate_matches.append(dict(seed=seed+i,focalSeat=i%2,
                outcome=verdict['outcome'],winner=verdict['winner'],
                adjudication=verdict['basis'],scores=verdict['scores'],
                turnsStarted=report['turnsStarted'],invalidReasons=verdict['invalidReasons'],
                telemetry=stats))
        base_rows=results_for(matches,target,'baseline')
        candidate_rows=results_for(candidate_matches,target,profile)
        results['comparisons'][str(target)]=compare(base_rows,candidate_rows)
        results['matchData'].append(dict(deckId=target,baseline=base_rows,candidate=candidate_rows))
        print('STRATEGY_COMPARE '+json.dumps(dict(deckId=target,**results['comparisons'][str(target)])),flush=True)
    return results


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--focal',type=Path,required=True)
    parser.add_argument('--opponent',type=Path,required=True)
    parser.add_argument('--baseline',type=Path,required=True)
    parser.add_argument('--games',type=int,default=4)
    parser.add_argument('--seed',type=int,default=5189995)
    parser.add_argument('--profile',choices=tuple(PROFILE_DELTAS),default='tempo')
    parser.add_argument('--out',type=Path,required=True)
    a=parser.parse_args()
    with s.RulesBridge() as rules:
        report=run(rules,json.loads(a.focal.read_text()),json.loads(a.opponent.read_text()),
                   json.loads(a.baseline.read_text()),a.games,a.profile,a.seed)
    s.write_json(a.out,report)
    print('STRATEGY_DONE '+json.dumps(dict(comparisons=report['comparisons'],
        games=len(report['matchData'])*a.games),sort_keys=True))


if __name__=='__main__':
    main()
