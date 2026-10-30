"""Reproducible focal-deck diagnostics with balanced starts and explicit gaps."""
import argparse
from collections import Counter
import gzip
import hashlib
import json
import subprocess
from pathlib import Path

import simulator as s
from question_batches import build_report


def engine_source_hashes():
    paths=list((s.ROOT/'training').glob('*.py'))+[s.HERE/'java/RulesBridge.java']
    paths.extend(s.ROOT/('src/main/java/dev/casz/caszualmtg/'+name+'.java') for name in
                 ('CommanderOracle','CommanderMana','CommanderSimpleCards','CommanderSimpleSpells'))
    return {str(p.relative_to(s.ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}


def adjudicate(report, focal_seat):
    """Fail closed on rules questions, unsupported encounters and incomplete games.

    A score from a paused or question-blocked game must never enter win-rate
    accounting, even if a winner or a turn-limit life score was also recorded.
    """
    progress=report.get('rulesProgress') or {}
    reasons=[]
    if progress.get('runtimeQuestions'):
        reasons.append('runtime_rules_question')
    if progress.get('unsupportedEncountered') or progress.get('unsupportedCommanders'):
        reasons.append('unsupported_card_encountered')
    if any(q.get('blocking') for q in report.get('questions',[]) if isinstance(q,dict)
           and str(q.get('id','')).startswith('runtime-')):
        if 'runtime_rules_question' not in reasons:
            reasons.append('runtime_rules_question')
    if not report.get('events') or len(report['events'][-1].get('state',{}).get('players',[])) != 2:
        reasons.append('missing_final_state')
        scores=[]
    else:
        scores=[p['life'] for p in report['events'][-1]['state']['players']]
    if reasons:
        return dict(outcome='blocked',winner=None,basis='invalid',scores=scores,invalidReasons=reasons)
    winner=report.get('winner')
    if report['result']=='win' and winner in (0,1):
        basis='game_rules'
    elif report['result']=='draw' and winner is None:
        basis='game_rules'
    elif report['result']=='diagnostic_window_complete':
        winner=None if scores[0]==scores[1] else int(scores[1]>scores[0])
        basis='turn_limit_life_score'
    else:
        return dict(outcome='blocked',winner=None,basis='incomplete',scores=scores,
                    invalidReasons=['incomplete_or_inconsistent_result'])
    return dict(outcome='tie' if winner is None else 'win' if winner==focal_seat else 'loss',
                winner=winner,basis=basis,scores=scores,invalidReasons=[])



def match_telemetry(report):
    """Observable actions only; no hidden AI knowledge or fabricated legality checks."""
    events=report.get('events',[])
    kinds=Counter(e.get('kind') for e in events)
    by_seat=lambda kind: [sum(e.get('kind')==kind and e.get('actor')==seat
                              for e in events) for seat in (0,1)]
    progress=report.get('rulesProgress') or {}
    questions=progress.get('runtimeQuestions',[])
    return dict(
        openingMulligans=list(report.get('openingMulligans',[])),
        landDropsBySeat=by_seat('land'),
        spellsCastBySeat=by_seat('cast'),
        activationsBySeat=[sum(e.get('actor')==seat and
                                (e.get('kind')=='activate' or str(e.get('kind','')).startswith('activate_'))
                                for e in events) for seat in (0,1)],
        attacksBySeat=[sum(e.get('actor')==seat and e.get('kind') in ('attack','attack_group')
                           for e in events) for seat in (0,1)],
        priorityPassesBySeat=by_seat('priority_pass'),
        turnsStarted=list(report.get('turnsStarted',[])),
        turnsCompleted=list(report.get('turnsCompleted',[])),
        eventCounts=dict(kinds),
        resolutionLogEvents=sum(kinds.get(kind,0) for kind in ('resolve','trigger','stack_resolve')),
        runtimeQuestionCount=len(questions),
        # This is a subset of observed engine complaints, not proof of legality.
        observedLegalityQuestions=[q for q in questions
            if any(term in str(q).lower() for term in ('illegal','invariant','no legal action'))],
    )


def run(rules, focal, opponents, games=10, turns=10, seed=5189995, out=None):
    if games < 2 or games % 2 or turns < 1:
        raise ValueError('Use a positive even number of games and positive turn limit')
    if not opponents or any(s.deck_fingerprint(d) == s.deck_fingerprint(focal) for d in opponents):
        raise ValueError('At least one distinct opponent is required')
    questions = {}
    coverage = []
    for deck in [focal, *opponents]:
        unsupported = []
        playable = 0
        identity = set(deck['commanders'][0].get('colorIdentity', []))
        for role in ('commanders', 'mainboard'):
            for raw in deck[role]:
                card = s.import_diagnostic_card(rules, raw, 0, 'coverage', identity)
                if card.kind != 'unsupported':
                    playable += raw['quantity']
                    continue
                parsed = s.parse_event_card(raw)
                audit = s.audit_card(rules, raw)
                reason = parsed.reason or audit.get('reason') or 'Unsupported card program'
                q = s.question(raw, reason, deck['name'])
                entry = questions.setdefault(q['id'], dict(q, decks=[], occurrences=[], encounterGames=[]))
                entry['decks'].append(deck['name'])
                entry['occurrences'].append(dict(deckId=deck['sourceDeckId'], role=role, quantity=raw['quantity']))
                unsupported.append(raw['name'])
        coverage.append(dict(deckId=deck['sourceDeckId'], deck=deck['name'], playableOf100=playable,
                             unsupportedCards=unsupported,
                             commanderSupported=deck['commanders'][0]['name'] not in unsupported))

    summary = dict(schemaVersion=1, focalDeck=focal['name'], focalDeckId=focal['sourceDeckId'],
                   engineCommit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=s.ROOT,text=True).strip(),
                   engineWorkingTreeDirty=bool(subprocess.check_output(['git','status','--porcelain'],cwd=s.ROOT,text=True).strip()),
                   engineSourceHashes=engine_source_hashes(),
                   gamesPerOpponent=games, turnsPerPlayer=turns, baseSeed=seed,
                   scoring=dict(metric='remaining_life',atTurnLimit='higher_score_wins',equalScores='tie',normalResultsTakePrecedence=True),
                   learningEligible=False, productionEligible=False, coverage=coverage,
                   notice='Incomplete-rules diagnostic only. Unsupported cards remain unplayable; these rates do not measure actual Commander deck strength. Completed turn windows are decided by remaining life total; equal scores are ties.',
                   matchups=[], matches=[], runtimeQuestions=[])
    packed = []
    for opponent_index, opponent in enumerate(opponents):
        results = Counter()
        encountered = set()
        first = Counter()
        for game_index in range(games):
            focal_seat = game_index % 2
            selected = [focal, opponent] if focal_seat == 0 else [opponent, focal]
            game_seed = seed + opponent_index * games + game_index
            report = s.diagnose(rules, selected, game_seed, turns)
            match_id = str(opponent['sourceDeckId']) + '-' + str(game_index + 1)
            assert not report['learningEligible']
            assert all(n <= turns for n in report['turnsStarted'])
            decision=adjudicate(report,focal_seat)
            if any(item['unsupportedCards'] for item in coverage if item['deckId'] in report['deckIds']):
                decision=dict(outcome='blocked',winner=None,basis='invalid',scores=decision['scores'],
                              invalidReasons=sorted(set(decision['invalidReasons']+['unsupported_card_in_deck'])))
            outcome=decision['outcome']
            results[outcome] += 1
            results['turn_limit'] += int(decision['basis']=='turn_limit_life_score')
            first['focalFirst' if focal_seat == 0 else 'opponentFirst'] += 1
            gaps = report['rulesProgress']['unsupportedEncountered']
            encountered.update(gaps)
            for q in questions.values():
                if q['card'] in gaps or (q['card'] in report['rulesProgress']['unsupportedCommanders']
                                         and any(o['deckId'] in report['deckIds'] for o in q['occurrences'])):
                    q['encounterGames'].append(match_id)
            runtime_count=len(report['rulesProgress']['runtimeQuestions'])
            for q in report['questions'][-runtime_count:] if runtime_count else []:
                summary['runtimeQuestions'].append(dict(match=match_id, **q))
            final = report['events'][-1]['state']['players']
            row = dict(id=match_id, opponent=opponent['name'], seed=game_seed, focalSeat=focal_seat,
                       focalPlayedFirst=focal_seat == 0, outcome=outcome, result=report['result'],
                       winner=decision['winner'], engineWinner=report.get('winner'), adjudication=decision['basis'],
                       scores=decision['scores'], scoreMetric='remaining_life', turnsCompleted=report['turnsCompleted'],
                       focalLife=final[focal_seat]['life'], opponentLife=final[1-focal_seat]['life'],
                       rulesProgress=report['rulesProgress'],invalidReasons=decision['invalidReasons'],
                       telemetry=match_telemetry(report))
            summary['matches'].append(row)
            packed.append(dict(id=match_id, adjudication=decision, replay=s.pack_replay(report)))
            if out and opponent_index==0 and game_index==0:
                s.export_review(out/'first-match.json',report)
            print(json.dumps({k:row[k] for k in ('id','opponent','outcome','turnsCompleted','focalLife','opponentLife')}), flush=True)
        wins, losses = results['win'], results['loss']
        summary['matchups'].append(dict(opponent=opponent['name'], opponentId=opponent['sourceDeckId'],
              games=games, wins=wins, losses=losses, ties=results['tie'], turnLimit=results['turn_limit'], blocked=results['blocked'],
              winRateAllGames=wins/games, tieRate=results['tie']/games, winRateDecisive=wins/(wins+losses) if wins+losses else None,
              firstPlayerCounts=dict(first), unsupportedEncountered=sorted(encountered)))
        if out:
            s.write_json(out/'summary.json', summary)
            s.write_json(out/'questions.json', dict(unsupportedCardQuestions=list(questions.values()), runtimeQuestions=summary['runtimeQuestions']))
    totals = Counter(row['outcome'] for row in summary['matches'])
    summary['totals'] = dict(games=len(summary['matches']), wins=totals['win'], losses=totals['loss'],
                            ties=totals['tie'], turnLimit=sum(row['adjudication']=='turn_limit_life_score' for row in summary['matches']), blocked=totals['blocked'],
                            tieRate=totals['tie']/len(summary['matches']),
                            winRateAllGames=totals['win']/len(summary['matches']))
    summary['questionCounts'] = dict(unsupportedCards=len(questions),
          focalUnsupportedCards=sum(any(o['deckId']==focal['sourceDeckId'] for o in q['occurrences']) for q in questions.values()),
          runtime=len(summary['runtimeQuestions']))
    if out:
        s.write_json(out/'summary.json', summary)
        s.write_json(out/'questions.json', dict(unsupportedCardQuestions=list(questions.values()), runtimeQuestions=summary['runtimeQuestions']))
        s.write_json(out/'question-batches.json',build_report(list(questions.values()),focal['sourceDeckId']))
        (out/'replays.json.gz').write_bytes(gzip.compress(json.dumps(packed,ensure_ascii=False,separators=(',',':')).encode(),mtime=0))
    return summary


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--focal',type=Path,required=True)
    parser.add_argument('--opponents',type=Path,nargs='+',required=True)
    parser.add_argument('--games',type=int,default=10)
    parser.add_argument('--turns',type=int,default=10)
    parser.add_argument('--seed',type=int,default=5189995)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    with s.RulesBridge() as rules:
        summary=run(rules,json.loads(args.focal.read_text()),[json.loads(p.read_text()) for p in args.opponents],
                    args.games,args.turns,args.seed,args.out)
    print(json.dumps(dict(totals=summary['totals'],questions=summary['questionCounts'])))


if __name__=='__main__':
    main()
