"""Counterexample search policy must be deterministic and not peek."""
import unittest
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
from garbo_policy import GoblinPlan

class GarboStrategyChecks(unittest.TestCase):
    def test_actions_are_legal_and_deterministic(self):
        public=json.dumps(dict(players=[dict(battlefield=[],life=40),dict(battlefield=[],life=40)]))
        legal=(s.Candidate('land','land',features=s.features(power=1)),
               s.Candidate('pass','pass',features=s.features(**{'pass':1})))
        obs=s.Observation(0,1,'main',(),public,legal)
        for name in ('swarm','counterpunch'):
            p=GoblinPlan(plan=name)
            self.assertIn(p.choose(obs),legal)
            self.assertEqual(p.choose(obs),p.choose(obs))
        with self.assertRaises(ValueError):
            GoblinPlan().choose(s.Observation(0,1,'main',(),public,()))

    def test_tribal_reward_does_not_depend_on_specific_card_names(self):
        public=json.dumps(dict(players=[dict(battlefield=[],life=40),dict(battlefield=[],life=40)]))
        tribal=s.EventDefinition('Unknown',frozenset({'Creature'}),frozenset({'Goblin'}),
                                 False,2,2,frozenset())
        other=s.EventDefinition('Unknown',frozenset({'Creature'}),frozenset({'Beast'}),
                                 False,2,2,frozenset())
        gob=s.Card('g','Arbitrary Goblin','creature','{R}',event_definition=tribal)
        beast=s.Card('b','Arbitrary Beast','creature','{R}',event_definition=other)
        legal=(s.Candidate('g','cast','g',s.features(power=2,cost=1)),
               s.Candidate('b','cast','b',s.features(power=2,cost=1)))
        obs=s.Observation(0,2,'main',(gob,beast),public,legal)
        self.assertEqual(GoblinPlan(plan='swarm').choose(obs).card_id,'g')

    def test_raw_power_does_not_certify_combat_lethal_through_a_blocker(self):
        own=[dict(id='attacker',isCreature=True,kind='creature',power=10)]
        enemy=[dict(id='blocker',isCreature=True,kind='creature',power=2,toughness=4)]
        public=json.dumps(dict(players=[dict(battlefield=own,life=40),
                                      dict(battlefield=enemy,life=10)]))
        attack=s.Candidate('attack','attack_group','attacker',
                           s.features(power=1,damage=10,lethal=1),
                           attack_ids=('attacker',))
        pass_action=s.Candidate('pass','pass',features=s.features(**{'pass':1}))
        obs=s.Observation(0,3,'attack',(),public,(attack,pass_action))
        self.assertIn(GoblinPlan(plan='counterpunch').choose(obs),(attack,pass_action))

    def test_invalid_configuration_rejected(self):
        public=json.dumps(dict(players=[{},{}]))
        with self.assertRaises(ValueError):
            GoblinPlan(plan='invalid').choose(s.Observation(0,1,'main',(),public,
                                                    (s.Candidate('p','pass'),)))
