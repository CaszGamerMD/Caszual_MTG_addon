"""Control strategy experiments must not count incomplete games as improvements."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from strategy_lab import compare,policy_for,results_for


class StrategyLabChecks(unittest.TestCase):
    def stub(self,seed,win,turn,seat=0,blocked=False):
        return dict(seed=seed,outcome='blocked' if blocked else 'win' if win else 'loss',
            winner=seat if win else 1-seat,
            focalSeat=seat,adjudication='game_rules',
            scores=[40,20],turnsStarted=[turn,turn],
            invalidReasons=['runtime_rules_question'] if blocked else [],
            telemetry=dict(runtimeQuestionCount=int(blocked),
                landDropsBySeat=[5,5],spellsCastBySeat=[4,4],
                attacksBySeat=[3,3],openingMulligans=[0,0]))

    def test_weight_profile_changes_only_public_feature_heuristics(self):
        baseline=policy_for('baseline')
        candidate=policy_for('tempo')
        self.assertEqual(baseline.version,0)
        self.assertEqual(candidate.version,1)
        self.assertGreater(candidate.weights[list(__import__('simulator').FEATURES).index('damage')],
                           baseline.weights[list(__import__('simulator').FEATURES).index('damage')])
        self.assertNotEqual(candidate.weights,baseline.weights)

    def test_phase_plan_uses_public_board_and_own_hand_only(self):
        import json
        import simulator as s
        policy=policy_for('phase-plan')
        land=s.Candidate('land','land',features=s.features(power=1))
        passing=s.Candidate('pass','pass',features=s.features(**{'pass':1}))
        state=dict(players=[dict(battlefield=[],life=40),dict(battlefield=[],life=40)])
        obs=s.Observation(0,1,'main',(),json.dumps(state),(land,passing))
        self.assertEqual(policy.choose(obs).kind,'land')
        self.assertEqual(policy.choose(obs),policy.choose(obs))
        with self.assertRaises(ValueError):
            policy.choose(s.Observation(0,1,'main',(),json.dumps(state),()))
        d=s.EventDefinition('Unseen',frozenset({'Enchantment'}),frozenset(),False,0,0,frozenset())
        e=s.Card('e','Unseen','enchantment','{W}',event_definition=d)
        generic=s.Card('g','Generic','artifact','{W}')
        a=s.Candidate('e','cast','e',s.features(power=2,cost=1))
        b=s.Candidate('g','cast','g',s.features(power=2,cost=1))
        ob=s.Observation(0,3,'main',(e,generic),json.dumps(state),(a,b))
        self.assertEqual(policy.choose(ob).card_id,'e')

    def test_same_win_count_faster_real_win_is_provisional_not_training(self):
        a=results_for([self.stub(1,True,8),self.stub(2,True,7)],5189995,'baseline')
        b=results_for([self.stub(1,True,5),self.stub(2,True,6)],5189995,'tempo')
        outcome=compare(a,b)
        self.assertTrue(outcome['provisionalImprovement'])
        self.assertFalse(outcome['promote'])
        self.assertEqual(outcome['candidate']['averageRealWinTurn'],5.5)

    def test_blocked_or_mismatched_matches_never_promote(self):
        a=results_for([self.stub(1,True,9),self.stub(2,True,9)],5189995,'baseline')
        b=results_for([self.stub(1,True,4),self.stub(2,True,4,blocked=True)],5189995,'tempo')
        outcome=compare(a,b)
        self.assertFalse(outcome['validComparison'])
        self.assertFalse(outcome['promote'])
        with self.assertRaises(ValueError):
            compare(a,b[::-1])

    def test_existing_gauntlet_places_turns_started_inside_telemetry(self):
        legacy=self.stub(1,True,6)
        legacy['telemetry']['turnsStarted']=legacy.pop('turnsStarted')
        row=results_for([legacy],5189995,'baseline')[0]
        self.assertEqual(row['actualWinTurn'],6)
        self.assertEqual(row['status'],'win')

    def test_loss_penalty_precedes_faster_win_turn(self):
        a=results_for([self.stub(1,True,9),self.stub(2,True,9)],5189995,'baseline')
        b=results_for([self.stub(1,True,2),self.stub(2,False,3)],5189995,'tempo')
        self.assertFalse(compare(a,b)['provisionalImprovement'])


if __name__=='__main__':unittest.main()
