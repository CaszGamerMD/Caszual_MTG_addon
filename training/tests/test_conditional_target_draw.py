"""Resolution-time subtype checks for targeted temporary stat modifiers."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
import test_enchantment_abilities as fixtures


class ConditionalTargetDrawTests(unittest.TestCase):
    setUpClass=classmethod(fixtures.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.EnchantmentChecks.tearDownClass.__func__)
    fixture=fixtures.EnchantmentChecks.fixture
    token=fixtures.EnchantmentChecks.token
    drain=fixtures.EnchantmentChecks.drain

    def test_real_unseen_subtype_and_negative_remainder(self):
        raw=dict(self.lookup['Peppersmoke'],name='Unseen conditional trick')
        card=s.import_diagnostic_card(self.rules,raw,0,'x',{'Black'})
        self.assertEqual(card.kind,'modifier_spell')
        self.assertEqual(card.target_modifier,(-1,-1,(),'Faerie'))
        raw['oracleText']=raw['oracleText'].replace('-1/-1','-2/-3').replace('a Faerie','an Elf')
        card=s.import_diagnostic_card(self.rules,raw,0,'y',{'Black'})
        self.assertEqual(card.target_modifier,(-2,-3,(),'Elf'))
        raw['oracleText']+='\nCreate an unknown permanent.'
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'bad',set()).kind,'unsupported')

    def test_conditional_draw_checks_battlefield_at_resolution(self):
        sim,cards=self.fixture(['Peppersmoke'])
        victim=self.token(sim,'victim',seat=1,power=3,toughness=3)
        spell=cards['Peppersmoke']
        hand=len(sim.players[0].hand)
        sim.cast_spell(0,spell,target=victim.card.id)
        self.token(sim,'ally',power=2,toughness=2,subtypes=('Faerie',))
        self.drain(sim)
        self.assertEqual(len(sim.players[0].hand),hand)
        self.assertEqual(sim.event_game('main').stats(sim.event_game('main').battlefield[victim.card.id]),(2,2))
        self.assertIn(spell,sim.players[0].graveyard)
        sim.invariant()

    def test_without_matching_subtype_no_draw(self):
        sim,cards=self.fixture(['Peppersmoke'])
        victim=self.token(sim,'victim',seat=1,power=3,toughness=3)
        spell=cards['Peppersmoke']
        before=len(sim.players[0].hand)
        sim.cast_spell(0,spell,target=victim.card.id)
        self.drain(sim)
        self.assertEqual(len(sim.players[0].hand),before-1)
        sim.invariant()

    def test_fizzle_if_target_leaves_even_with_matching_subtype(self):
        sim,cards=self.fixture(['Peppersmoke'])
        self.token(sim,'ally',subtypes=('Faerie',))
        victim=self.token(sim,'victim',seat=1,power=2,toughness=2)
        spell=cards['Peppersmoke']
        before=len(sim.players[0].hand)
        sim.cast_spell(0,spell,target=victim.card.id)
        sim.send_to_destination(sim.players[1],victim)
        self.drain(sim)
        self.assertEqual(len(sim.players[0].hand),before-1)
        self.assertTrue(any(e['kind']=='modifier_fizzle' for e in sim.events))
        sim.invariant()

    def test_minus_toughness_causes_state_based_death(self):
        sim,cards=self.fixture(['Peppersmoke'])
        victim=self.token(sim,'victim',seat=1,power=1,toughness=1)
        spell=cards['Peppersmoke']
        sim.cast_spell(0,spell,target=victim.card.id)
        self.drain(sim)
        self.assertNotIn(victim,sim.players[1].battlefield)
        self.assertIn(spell,sim.players[0].graveyard)
        sim.invariant()
