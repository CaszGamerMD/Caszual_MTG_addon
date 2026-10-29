"""Reproducible focal-deck diagnostics with balanced starts and explicit gaps."""
import argparse
from collections import Counter
import gzip
import json
import subprocess
from pathlib import Path

import simulator as s


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
                   gamesPerOpponent=games, turnsPerPlayer=turns, baseSeed=seed,
                   learningEligible=False, productionEligible=False, coverage=coverage,
                   notice='Incomplete-rules diagnostic only. Unsupported cards remain unplayable; these rates do not measure actual Commander deck strength. Limit games are unresolved, not draws or losses.',
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
            if report['result'] == 'win':
                outcome = 'win' if report['winner'] == focal_seat else 'loss'
            elif report['result'] == 'diagnostic_window_complete':
                outcome = 'turn_limit'
            else:
                outcome = 'blocked'
            results[outcome] += 1
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
                       winner=report['winner'], turnsCompleted=report['turnsCompleted'],
                       focalLife=final[focal_seat]['life'], opponentLife=final[1-focal_seat]['life'],
                       rulesProgress=report['rulesProgress'])
            summary['matches'].append(row)
            packed.append(dict(id=match_id, replay=s.pack_replay(report)))
            print(json.dumps({k:row[k] for k in ('id','opponent','outcome','turnsCompleted','focalLife','opponentLife')}), flush=True)
        wins, losses = results['win'], results['loss']
        summary['matchups'].append(dict(opponent=opponent['name'], opponentId=opponent['sourceDeckId'],
              games=games, wins=wins, losses=losses, turnLimit=results['turn_limit'], blocked=results['blocked'],
              winRateAllGames=wins/games, winRateDecisive=wins/(wins+losses) if wins+losses else None,
              firstPlayerCounts=dict(first), unsupportedEncountered=sorted(encountered)))
        if out:
            s.write_json(out/'summary.json', summary)
            s.write_json(out/'questions.json', dict(unsupportedCardQuestions=list(questions.values()), runtimeQuestions=summary['runtimeQuestions']))
    totals = Counter(row['outcome'] for row in summary['matches'])
    summary['totals'] = dict(games=len(summary['matches']), wins=totals['win'], losses=totals['loss'],
                            turnLimit=totals['turn_limit'], blocked=totals['blocked'],
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
