"""Public-information tactical loyalty choices and real-card stack resolutions."""
import json
import sys
import unittest
from pathlib import Path

HERE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HERE))
import simulator as s
from planeswalker_runtime import legal,activate

REAL=json.loads((HERE/'decks'/'27521806-faeries.json').read_text())
WALKERS={c['name']:c for c in REAL['mainboard'] if 'Planeswalker' in c.get('types',())}

class PlaneswalkerStrategyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.rules=s.RulesBridge()
    @classmethod
    def tearDownClass(cls):cls.rules.close()

    def fixture(self,name,enemy=True):
        raw=WALKERS[name]
        pw=s.import_diagnostic_card(self.rules,raw,0,'strategic-walker',set(raw['colorIdentity']))
        self.assertEqual(pw.kind,'planeswalker')
        threat=s.Card('tactical-threat','Opponent threat','creature',power=5,
            toughness=1,traits='5;1;',event_definition=s.EventDefinition('Opponent threat',
                frozenset({'Creature'}),frozenset(),False,5,1,frozenset()))
        sim=s.Simulator(self.rules,106,
             decks=(s.demo_deck(0)+[pw],s.demo_deck(1)+[threat]),diagnostic=True)
        self.assertFalse(sim.finished,sim.questions)
        sim.manual_priority=True;sim.phase='main'
        sim.active=0;sim.stack.active=0;sim.stack.priority=0;sim.turn=1
        me,opponent=sim.players
        (me.hand if pw in me.hand else me.library).remove(pw)
        placed=s.Permanent(pw,loyalty=3)
        me.battlefield.append(placed)
        if enemy:
            (opponent.hand if threat in opponent.hand else opponent.library).remove(threat)
            opponent.battlefield.append(s.Permanent(threat))
        return sim,pw,placed,threat

    def select(self,sim):
        loyalty=legal(sim,0)
        self.assertTrue(loyalty)
        obs=s.Observation(0,sim.turn,'main',tuple(sim.players[0].hand),
                          json.dumps(sim.state(),sort_keys=True),
                          loyalty,False)
        return s.Policy().choose(obs)

    def test_liliana_kills_high_threat_instead_of_blind_plus_one(self):
        sim,pw,placed,threat=self.fixture('Liliana, the Last Hope')
        action=self.select(sim)
        self.assertEqual((action.activation_index,action.target_permanent),(0,threat.id))
        self.assertIn('remove opposing creature',action.label)
        frame=activate(sim,0,pw.id,action.activation_index,action.target_permanent)
        self.assertEqual(placed.loyalty,4)
        while sim.stack.items:sim.pass_priority(sim.stack.priority)
        self.assertIn(threat,sim.players[1].graveyard)
        sim.invariant()

    def test_near_ultimate_builds_loyalty_instead_of_milling_for_nothing(self):
        sim,pw,placed,_=self.fixture('Liliana, the Last Hope',enemy=False)
        placed.loyalty=6
        action=self.select(sim)
        self.assertEqual(action.activation_index,0)
        self.assertEqual(action.target_permanent,'')
        self.assertIn('approach ultimate',action.label)

    def test_liliana_ultimates_when_ready_and_unchallenged(self):
        sim,pw,placed,_=self.fixture('Liliana, the Last Hope',enemy=False)
        placed.loyalty=8
        action=self.select(sim)
        self.assertEqual(action.activation_index,2)
        activate(sim,0,pw.id,action.activation_index,action.target_permanent)
        while sim.stack.items:sim.pass_priority(sim.stack.priority)
        self.assertEqual(len(sim.emblems[0]),1)
        sim.invariant()

    def test_known_creature_recovery_beats_unnecessary_loyalty_growth(self):
        sim,pw,placed,_=self.fixture('Liliana, the Last Hope',enemy=False)
        creature=next(x for x in sim.players[0].library if x.kind=='creature')
        sim.players[0].library.remove(creature);sim.players[0].graveyard.append(creature)
        action=self.select(sim)
        self.assertEqual(action.activation_index,1)
        self.assertIn('recover creature',action.label)
        sim.invariant()

    def test_kaito_makes_ninja_without_attack_and_draws_after_attack(self):
        sim,pw,placed,_=self.fixture('Kaito Shizuki',enemy=False)
        self.assertEqual(self.select(sim).activation_index,1)
        sim.attacked_this_turn.add(0)
        self.assertEqual(self.select(sim).activation_index,0)

    def test_kaito_ultimates_with_existing_attacker(self):
        sim,pw,placed,_=self.fixture('Kaito Shizuki',enemy=False)
        creature=next(x for x in sim.players[0].library if x.kind=='creature')
        sim.players[0].library.remove(creature)
        sim.players[0].battlefield.append(s.Permanent(creature,fresh=False))
        placed.loyalty=8
        sim.attacked_this_turn.add(0)
        selected=self.select(sim)
        self.assertEqual(selected.activation_index,2)
        activate(sim,0,pw.id,selected.activation_index)
        while sim.stack.items:sim.pass_priority(sim.stack.priority)
        self.assertEqual(len(sim.emblems[0]),1)
        sim.invariant()

    def test_no_enemy_hand_or_library_peeking_affects_same_public_choice(self):
        sim,pw,placed,_=self.fixture('Kaito Shizuki',enemy=False)
        initial=self.select(sim)
        enemy=sim.players[1]
        enemy.library.reverse()
        enemy.hand,enemy.library=enemy.library[:4],enemy.hand+enemy.library[4:]
        other=self.select(sim)
        self.assertEqual((initial.activation_index,initial.target_permanent),
                         (other.activation_index,other.target_permanent))
        sim.invariant()

if __name__=='__main__':unittest.main()
