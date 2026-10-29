"""Win-rate accounting must distinguish unresolved games from actual losses."""
import sys
from pathlib import Path
import unittest
from unittest.mock import patch
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import gauntlet as g


class GauntletChecks(unittest.TestCase):
    def deck(self, name, identifier):
        return dict(name=name, sourceDeckId=identifier,
                    commanders=[dict(name=name, quantity=1, colorIdentity=[])], mainboard=[])

    def test_balanced_starts_rates_and_unresolved_results(self):
        focal, opponent = self.deck('Focal',1), self.deck('Opponent',2)
        reports=[]
        # Focal seats alternate 0/1. Winning seat 0 is therefore first a win,
        # then a loss. A turn limit and a rules pause remain separate outcomes.
        for result in ('win','win','diagnostic_window_complete','paused'):
            reports.append(dict(result=result,winner=0,learningEligible=False,
                turnsStarted=[10,10],turnsCompleted=[10,10],deckIds=[1,2],questions=[],
                rulesProgress=dict(unsupportedEncountered=[],unsupportedCommanders=[],runtimeQuestions=[]),
                events=[dict(state=dict(players=[dict(life=40),dict(life=35)]))]))
        with patch.object(g.s,'import_diagnostic_card',return_value=SimpleNamespace(kind='creature')), \
             patch.object(g.s,'diagnose',side_effect=reports) as diagnose, \
             patch.object(g.s,'pack_replay',side_effect=lambda r:r), patch('builtins.print'):
            summary=g.run(None,focal,[opponent],games=4)
        row=summary['matchups'][0]
        self.assertEqual((row['wins'],row['losses'],row['ties'],row['turnLimit'],row['blocked']),(2,1,0,1,1))
        self.assertEqual(row['winRateAllGames'],.5)
        self.assertEqual(row['winRateDecisive'],2/3)
        self.assertEqual(row['firstPlayerCounts'],dict(focalFirst=2,opponentFirst=2))
        self.assertEqual([call.args[1][0]['name'] for call in diagnose.call_args_list],['Focal','Opponent','Focal','Opponent'])
        self.assertEqual(summary['totals']['games'],4)

    def test_empty_opponents_and_unbalanced_batches_are_rejected(self):
        focal, opponent=self.deck('Focal',1),self.deck('Opponent',2)
        for opponents, games in (([],2),([opponent],3),([focal],2)):
            with self.assertRaises(ValueError):g.run(None,focal,opponents,games=games)

    def test_equal_scores_are_ties_and_normal_results_precede_score(self):
        report=dict(result='diagnostic_window_complete',winner=None,
                    events=[dict(state=dict(players=[dict(life=25),dict(life=25)]))])
        self.assertEqual(g.adjudicate(report,0)['outcome'],'tie')
        report['events'][0]['state']['players'][0]['life']=40
        self.assertEqual(g.adjudicate(report,0)['outcome'],'win')
        self.assertEqual(g.adjudicate(report,1)['outcome'],'loss')
        report.update(result='win',winner=1)
        self.assertEqual(g.adjudicate(report,1)['outcome'],'win')
        report.update(result='draw',winner=None)
        self.assertEqual(g.adjudicate(report,0)['outcome'],'tie')
        report.update(result='blocked')
        self.assertEqual(g.adjudicate(report,0)['outcome'],'blocked')
