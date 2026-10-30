"""Two modal attack-token branches: choice now, resolution-time X and attacking state."""
import unittest
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
import test_enchantment_abilities as fixtures

NAME='Ghalta and Mavren'

class SessionLearningModalAttackTokens(unittest.TestCase):
    setUpClass=classmethod(fixtures.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.EnchantmentChecks.tearDownClass.__func__)
    fixture=fixtures.EnchantmentChecks.fixture
    put=fixtures.EnchantmentChecks.put
    token=fixtures.EnchantmentChecks.token
    ready=fixtures.EnchantmentChecks.ready
    drain=fixtures.EnchantmentChecks.drain

    def test_actual_unseen_name_parameters_and_extra_clause_rejected(self):
        raw=dict(self.lookup[NAME])
        card=s.import_diagnostic_card(self.rules,raw,0,'real',{'Green','White'})
        self.assertNotEqual(card.kind,'unsupported')
        self.assertEqual(len(card.event_definition.modal_attack_tokens),2)
        raw['name']='Unfamiliar modal battle lord'
        raw['oracleText']=raw['oracleText'].replace('green Dinosaur','blue Dragon').replace('white Vampire','red Soldier')
        raw['oracleText']=raw['oracleText'].replace('1/1 white','2/2 white').replace('1/1 red','2/2 red')
        other=s.import_diagnostic_card(self.rules,raw,0,'new',{'Green','White'})
        self.assertNotEqual(other.kind,'unsupported')
        self.assertEqual(other.event_definition.modal_attack_tokens[1]['power'],2)
        raw['oracleText']+='\nCast an unknown card without paying.'
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'bad',{'Green','White'}).kind,'unsupported')

    def prepare(self,mode):
        sim,cards=self.fixture([NAME])
        source=self.put(sim,cards[NAME])
        first=self.token(sim,'ally-one',power=4,toughness=4)
        second=self.token(sim,'ally-two',power=2,toughness=2)
        sim.choose_modal_attack_mode=lambda *_: mode
        self.ready(sim)
        return sim,source,first,second

    def test_dinosaur_choice_uses_greatest_power_at_resolution_and_attacks(self):
        sim,source,first,second=self.prepare(0)
        sim.declare_attackers([first.card.id,second.card.id])
        self.assertEqual(len(sim.stack.items),1)
        event=sim.stack.items[-1].payload[0]
        self.assertEqual(event['operation'],'modal_attack_tokens')
        self.assertEqual(event['mode'],0)
        first.counters+=2
        sim.send_to_destination(sim.players[0],source)
        self.drain(sim)
        dinos=[p for p in sim.players[0].battlefield if p.card.is_token and
               p.card.event_definition and 'Dinosaur' in p.card.event_definition.subtypes]
        self.assertEqual(len(dinos),1)
        self.assertEqual((dinos[0].card.power,dinos[0].card.toughness),(6,6))
        self.assertTrue(dinos[0].tapped)
        self.assertIn(dinos[0].card.id,sim.group_combat['attackers'])
        sim.invariant()

    def test_vampire_choice_counts_other_attackers_but_not_source(self):
        sim,source,first,second=self.prepare(1)
        sim.declare_attackers([source.card.id,first.card.id,second.card.id])
        self.assertEqual(sim.stack.items[-1].payload[0]['mode'],1)
        self.drain(sim)
        vampires=[p for p in sim.players[0].battlefield if p.card.is_token and
                  p.card.event_definition and 'Vampire' in p.card.event_definition.subtypes]
        self.assertEqual(len(vampires),2)
        self.assertTrue(all(not p.tapped and p.card.id not in sim.group_combat['attackers'] for p in vampires))
        self.assertTrue(all('lifelink' in p.card.event_definition.abilities for p in vampires))
        sim.invariant()

    def test_not_declaring_attackers_does_not_trigger(self):
        sim,_,first,second=self.prepare(1)
        sim.declare_attackers([])
        self.assertFalse(sim.stack.items)
        self.assertEqual(sim.phase,'second_main')
        sim.invariant()
