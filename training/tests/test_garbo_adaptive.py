"""Protect baseline while testing public-only defensive and lethal tactics."""
import json
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
from garbo_adaptive import AdaptiveGarboPolicy,defender_can_block

def actor(i,name,power=7,abilities='',tapped=False):
    return dict(id=f'{i}-commander',name=name,kind='creature',isCreature=True,
        power=power,toughness=5,traits=f'{power};5;{abilities}',tapped=tapped)

def state(own,enemy,damage=None,seat=0):
    a=dict(battlefield=own,life=40,commanderDamage=damage or {})
    b=dict(battlefield=enemy,life=40,commanderDamage={})
    players=[a,b] if seat==0 else [b,a]
    return json.dumps(dict(players=players))

class AdaptiveGarboTest(unittest.TestCase):
    def setUp(self):
        self.policy=AdaptiveGarboPolicy()
        self.pass_action=s.Candidate('pass','pass',features=s.features(**{'pass':1}))

    def test_default_noncombat_kept(self):
        cast=s.Candidate('spell','cast','unknown',s.features(power=9))
        commander=s.Candidate('0-commander','cast_commander','0-commander',
                              s.features(power=7,haste=1,cost=5))
        public=state([],[])
        obs=s.Observation(0,2,'main',(),public,(self.pass_action,cast,commander))
        self.assertEqual(self.policy.choose(obs),s.Policy().choose(obs))

    def test_late_commander_kill_selected(self):
        hero=actor(0,'Commander')
        hit=s.Candidate('hit','attack_group',hero['id'],
                        s.features(power=.7,damage=7),attack_ids=(hero['id'],))
        skip=s.Candidate('skip','attack_group','goblin',
                         s.features(power=3,damage=30),attack_ids=('goblin',))
        public=state([hero],[],seat=0)
        public=json.loads(public)
        public['players'][1]['commanderDamage']={'0-commander':14}
        obs=s.Observation(0,4,'attack',(),json.dumps(public),(skip,hit))
        self.assertEqual(self.policy.choose(obs),hit)

    def test_late_commander_not_assumed_unblocked(self):
        hero=actor(0,'Commander')
        enemy=dict(id='blocker',name='Wall',isCreature=True,kind='creature',
                   power=1,toughness=2,traits='1;2;',tapped=False)
        hit=s.Candidate('hit','attack_group',hero['id'],
                        s.features(power=.7,damage=7),attack_ids=(hero['id'],))
        skip=s.Candidate('skip','attack_group','goblin',
                         s.features(power=3,damage=30),attack_ids=('goblin',))
        public=json.loads(state([hero],[enemy]))
        public['players'][1]['commanderDamage']={'0-commander':14}
        obs=s.Observation(0,4,'attack',(),json.dumps(public),(skip,hit))
        self.assertEqual(self.policy.choose(obs),s.Policy().choose(obs))
        self.assertTrue(defender_can_block(hero,[enemy]))

    def test_flying_and_menace_blockability_proxy(self):
        ground=dict(id='g',isCreature=True,kind='creature',tapped=False,traits='2;2;')
        wing=dict(id='f',isCreature=True,kind='creature',tapped=False,traits='2;2;reach')
        self.assertFalse(defender_can_block(actor(0,'A',abilities='flying'),[ground]))
        self.assertTrue(defender_can_block(actor(0,'A',abilities='flying'),[wing]))
        self.assertFalse(defender_can_block(actor(0,'A',abilities='menace'),[ground]))
        self.assertTrue(defender_can_block(actor(0,'A',abilities='menace'),[ground,wing]))

    def test_block_opposing_commander_if_21_damage_would_be_lethal(self):
        opponent=actor(1,'Enemy',power=7)
        ours=actor(0,'Ours')
        none=s.Candidate('none','group_blocks',features=s.features(damage=0))
        stop=s.Candidate('stop','group_blocks',features=s.features(damage=-10),
                         blocks=((opponent['id'],(ours['id'],)),))
        public=state([ours],[opponent],damage={'1-commander':14})
        obs=s.Observation(0,5,'block',(),public,(none,stop))
        self.assertEqual(s.Policy().choose(obs),none)
        self.assertEqual(self.policy.choose(obs),stop)
        public=state([ours],[opponent],damage={'1-commander':7})
        obs=s.Observation(0,5,'block',(),public,(none,stop))
        self.assertEqual(self.policy.choose(obs),none)

    def test_seat_one_own_commander_damage_lookup(self):
        hero=actor(1,'Hero')
        hit=s.Candidate('hit','attack_group','1-commander',
                        s.features(power=.7,damage=7),attack_ids=('1-commander',))
        skip=s.Candidate('skip','attack_group','goblin',
                         s.features(power=3,damage=30),attack_ids=('goblin',))
        players=[dict(battlefield=[],life=40,commanderDamage={'1-commander':14}),
                 dict(battlefield=[hero],life=40,commanderDamage={})]
        obs=s.Observation(1,4,'attack',(),json.dumps(dict(players=players)),(skip,hit))
        self.assertEqual(self.policy.choose(obs),hit)

if __name__=='__main__':
    unittest.main()
