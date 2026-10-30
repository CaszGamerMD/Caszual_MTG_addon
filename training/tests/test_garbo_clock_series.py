"""Commander-clock candidate choices and real-vs-score win gates."""
import json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
from garbo_clock import CommanderClockPolicy
from garbo_clock_series import actual_win,summarized

def snapshot(own=None,enemy=None,damage=0,life=40):
    return json.dumps(dict(players=[
        dict(battlefield=own or [],life=40),
        dict(battlefield=enemy or [],life=life,
             commanderDamage={'0-commander':damage})]))

class CommanderClockTests(unittest.TestCase):
    def test_commander_cast_prioritized_on_equal_other_plays(self):
        clock=CommanderClockPolicy()
        cast=s.Candidate('0-commander','cast_commander','0-commander',
                         s.features(power=7,cost=5))
        other=s.Candidate('other','cast','other',s.features(power=7,cost=5))
        obs=s.Observation(0,4,'main',(),snapshot(),(other,cast))
        self.assertEqual(clock.choose(obs).kind,'cast_commander')
        self.assertIn(clock.choose(obs),obs.legal_actions)

    def test_commander_damage_progress_changes_ranking_with_no_hidden_data(self):
        clock=CommanderClockPolicy()
        own=[dict(id='0-commander',kind='creature',isCreature=True,
                  power=7,toughness=2,tapped=False)]
        commander=s.Candidate('attack-z','attack_group','0-commander',
                  s.features(power=.7,damage=7),attack_ids=('0-commander',))
        pass_a=s.Candidate('pass','pass',features=s.features(**{'pass':1}))
        for damage in (0,7,14):
            obs=s.Observation(0,5,'attack',(),snapshot(own=own,damage=damage),
                              (pass_a,commander))
            self.assertEqual(clock.choose(obs),commander)
            self.assertEqual(clock.choose(obs),clock.choose(obs))

    def test_never_invents_action_or_peeks_at_library(self):
        clock=CommanderClockPolicy()
        pass_a=s.Candidate('pass','pass',features=s.features(**{'pass':1}))
        obs=s.Observation(0,1,'main',(),snapshot(),(pass_a,))
        self.assertEqual(clock.choose(obs),pass_a)
        with self.assertRaises(ValueError):
            clock.choose(s.Observation(0,1,'main',(),snapshot(),()))

    def test_life_score_not_actual_win_and_rules_blocker_invalid(self):
        report=dict(result='diagnostic_window_complete')
        verdict=dict(outcome='win',basis='turn_limit_life_score',winner=0)
        self.assertFalse(actual_win(verdict,report,0))
        report['result']='win'
        verdict['basis']='game_rules'
        self.assertTrue(actual_win(verdict,report,0))
        verdict['outcome']='blocked'
        self.assertFalse(actual_win(verdict,report,0))
        verdict['outcome']='win'
        verdict['winner']=1
        self.assertFalse(actual_win(verdict,report,0))

    def test_scoreboard_does_not_promote_turn_limit_score(self):
        row=lambda a,b,c:dict(actualWin=a,commanderDamageWin=a,
            turnLimitScoreWin=b,outcome='win' if a or b else 'loss',
            invalidReasons=[] if not c else ['runtime_rules_question'],
            garboTurn=6,commanderDamage=21 if a else 0,lifeMargin=5,
            garboSeat=0)
        data=summarized([row(True,False,False),row(False,True,False),
                         row(False,False,True)])
        self.assertEqual(data['actualWins'],1)
        self.assertEqual(data['turnLimitScoreWins'],1)
        self.assertEqual(data['blocked'],1)

if __name__=='__main__':unittest.main()
