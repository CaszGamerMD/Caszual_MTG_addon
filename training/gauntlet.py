"""Reproducible focal-deck diagnostics with balanced starts and explicit gaps."""
import argparse
from collections import Counter
import gzip
import hashlib
import json
import subprocess
from pathlib import Path

import simulator as s


def engine_source_hashes():
    paths=list((s.ROOT/'training').glob('*.py'))+[s.HERE/'java/RulesBridge.java']
    paths.extend(s.ROOT/('src/main/java/dev/casz/caszualmtg/'+name+'.java') for name in
                 ('CommanderOracle','CommanderMana','CommanderSimpleCards','CommanderSimpleSpells'))
    return {str(p.relative_to(s.ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}


def adjudicate(report, focal_seat):
    """Normal game results precede the house rule for complete turn windows."""
    final=report['events'][-1]['state']['players']
    scores=[p['life'] for p in final]
    winner=report.get('winner')
    if report['result']=='win':
        basis='game_rules'
    elif report['result']=='draw':
        winner=None;basis='game_rules'
    elif report['result']=='diagnostic_window_complete':
        winner=None if scores[0]==scores[1] else int(scores[1]>scores[0])
        basis='turn_limit_life_score'
    else:
        return dict(outcome='blocked',winner=None,basis='incomplete',scores=scores)
    return dict(outcome='tie' if winner is None else 'win' if winner==focal_seat else 'loss',
                winner=winner,basis=basis,scores=scores)


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
                       rulesProgress=report['rulesProgress'])
            summary['matches'].append(row)
            packed.append(dict(id=match_id, adjudication=decision, replay=s.pack_replay(report)))
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
