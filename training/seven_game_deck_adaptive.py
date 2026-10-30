"""Deck-adaptive shared AI: Garbo vs Wilds, seven games, 15 turns each.

Both seats run the exact same AdaptiveDeckPolicy class and base weights.
Only their independently precomputed OWN deck profiles differ. The simulator
only exposes public observations and their own hands to decision-making.
Prior two seven-game comparisons remain untouched.
Not a complete legal Commander game or learning-eligible training data.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from statistics import mean

import gauntlet
import simulator as s
from deck_adaptive_strategy import AdaptiveDeckPolicy, analyze_deck


GARBO_ID = 5254666
WILDS_ID = 5189995
DEFAULT_SEED = 5189995


def _coverage(rules, deck):
    """Reject a partially imported deck before scoring a strategic result."""
    identity = set(deck['commanders'][0].get('colorIdentity', ()))
    missing = []
    for role in ('commanders', 'mainboard'):
        for index, raw in enumerate(deck[role]):
            card = s.import_diagnostic_card(rules, raw, 0, f'audit-{role}-{index}', identity)
            if card.kind == 'unsupported':
                missing.append(raw['name'])
    return missing


def run(rules, garbo, wilds, games=7, turns=15, seed=DEFAULT_SEED, out=None):
    if garbo['sourceDeckId'] != GARBO_ID or wilds['sourceDeckId'] != WILDS_ID:
        raise ValueError('Expected Garbo Gobbos 5254666 and Getting Wild 5189995')
    if games != 7 or turns != 15:
        raise ValueError('This requested study must run exactly seven 15-turn games')
    unsupported = {'garbo': _coverage(rules, garbo), 'wilds': _coverage(rules, wilds)}
    if any(unsupported.values()):
        raise ValueError('Cannot score decks with unsupported cards: ' + repr(unsupported))
    plans = {'Garbo': analyze_deck(garbo), 'Wilds': analyze_deck(wilds)}
    for name, plan in plans.items():
        print('DECK_BUILDING_BLOCKS ' + json.dumps(dict(deck=name,
              primary=plan.primary, secondary=plan.secondary,
              routes=[r.describe() for r in plan.routes]), sort_keys=True), flush=True)
    matches = []
    for index in range(games):
        garbo_seat = index % 2
        decks = [garbo, wilds] if garbo_seat == 0 else [wilds, garbo]
        garbo_policy = AdaptiveDeckPolicy(plan=plans['Garbo'])
        wilds_policy = AdaptiveDeckPolicy(plan=plans['Wilds'])
        policies = (garbo_policy, wilds_policy) if garbo_seat == 0 else (wilds_policy, garbo_policy)
        report = s.diagnose(rules, decks, seed + index, turns, policies=policies)
        decision = gauntlet.adjudicate(report, garbo_seat)
        stats = gauntlet.match_telemetry(report)
        scores = decision['scores']
        row = dict(game=index + 1, seed=seed + index,
                   garboPlan=plans['Garbo'].primary, wildsPlan=plans['Wilds'].primary,
                   garboFirst=garbo_seat == 0, garboSeat=garbo_seat,
                   outcome=decision['outcome'], adjudication=decision['basis'],
                   winner='Garbo' if decision['winner'] == garbo_seat
                          else 'Wilds' if decision['winner'] == 1 - garbo_seat else None,
                   garboLife=scores[garbo_seat] if len(scores) == 2 else None,
                   wildsLife=scores[1 - garbo_seat] if len(scores) == 2 else None,
                   garboTurns=report['turnsStarted'][garbo_seat],
                   wildsTurns=report['turnsStarted'][1 - garbo_seat],
                   invalidReasons=decision['invalidReasons'],
                   garboCasts=stats['spellsCastBySeat'][garbo_seat],
                   wildsCasts=stats['spellsCastBySeat'][1 - garbo_seat],
                   garboAttacks=stats['attacksBySeat'][garbo_seat],
                   wildsAttacks=stats['attacksBySeat'][1 - garbo_seat],
                   garboMulligans=stats['openingMulligans'][garbo_seat],
                   wildsMulligans=stats['openingMulligans'][1 - garbo_seat],
                   runtimeQuestions=stats['runtimeQuestionCount'])
        matches.append(row)
        print('MATCH_RESULT ' + json.dumps(row, sort_keys=True), flush=True)
        if out:
            # Every result gets a replay, including wins by either deck.
            s.write_json(out / f'game-{index + 1}-replay.json', s.pack_replay(report))
    counters = Counter(m['outcome'] for m in matches)
    valid = [m for m in matches if m['outcome'] != 'blocked']
    garbo_wins = [m for m in valid if m['winner'] == 'Garbo']
    rule_wins = [m for m in garbo_wins if m['adjudication'] == 'game_rules']
    summary = dict(schemaVersion=1, diagnostic=True, learningEligible=False,
        productionEligible=False,
        disclaimer='Incomplete two-player Commander diagnostic, NOT certified legal Magic games.',
        matchup=['Garbo Gobbos (adaptive)', 'Getting Wild (adaptive)'],
        policyBySeat=['AdaptiveDeckPolicy-v5', 'AdaptiveDeckPolicy-v5'],
        plans={name:plan.describe() for name,plan in plans.items()},
        identicalAi=True,
        games=games, turnsPerPlayer=turns, seed=seed, firstPlayerSplit={'Garbo': 4, 'Wilds': 3},
        garboWins=counters['win'], wildsWins=counters['loss'], ties=counters['tie'],
        blocked=counters['blocked'], garboRuleWins=len(rule_wins),
        garboScoreWins=sum(m['adjudication'] == 'turn_limit_life_score' for m in garbo_wins),
        averageGarboLifeMargin=round(mean(m['garboLife'] - m['wildsLife'] for m in valid), 2)
                               if valid else None,
        averageGarboRealWinTurn=round(mean(m['garboTurns'] for m in rule_wins), 2)
                                if rule_wins else None,
        matches=matches)
    if out:
        s.write_json(out / 'summary.json', summary)
    print('SEVEN_GAME_SUMMARY ' + json.dumps(
        {k: v for k, v in summary.items() if k != 'matches'}, sort_keys=True), flush=True)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--garbo', type=Path, default=s.HERE / 'decks/5254666-garbo-gobbos.json')
    parser.add_argument('--wilds', type=Path, default=s.HERE / 'decks/5189995-enchantments.json')
    parser.add_argument('--games', type=int, default=7)
    parser.add_argument('--turns', type=int, default=15)
    parser.add_argument('--seed', type=int, default=DEFAULT_SEED)
    parser.add_argument('--out', type=Path, default=s.HERE / 'reports/garbo-wilds-7x15-deck-adaptive')
    args = parser.parse_args()
    with s.RulesBridge() as rules:
        run(rules, json.loads(args.garbo.read_text()), json.loads(args.wilds.read_text()),
            games=args.games, turns=args.turns, seed=args.seed, out=args.out)


if __name__ == '__main__':
    main()
