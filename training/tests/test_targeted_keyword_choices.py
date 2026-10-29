"""Targeted choice modifiers: unseen names, targeting and stack rechecks."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
import test_enchantment_abilities as fixtures


class TargetedKeywordChoiceTests(unittest.TestCase):
    setUpClass=classmethod(fixtures.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.EnchantmentChecks.tearDownClass.__func__)
    fixture=fixtures.EnchantmentChecks.fixture
    token=fixtures.EnchantmentChecks.token
    drain=fixtures.EnchantmentChecks.drain

    def test_real_unseen_parameterized_and_unknown_extra_clause(self):
        raw=dict(self.lookup["Alchemist's Gift"],name='Unseen boon')
        card=s.import_diagnostic_card(self.rules,raw,0,'u',{'Black'})
        self.assertEqual(card.kind,'modifier_spell')
        self.assertEqual(card.target_modifier,(1,1,('deathtouch','lifelink'),''))
        raw['oracleText']=raw['oracleText'].replace('+1/+1','+2/+3').replace(
            'deathtouch or lifelink','flying or vigilance')
        card=s.import_diagnostic_card(self.rules,raw,0,'v',{'Black'})
        self.assertEqual(card.target_modifier,(2,3,('flying','vigilance'),''))
        raw['oracleText']+='\nCreate an unsupported bonus.'
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'bad',set()).kind,'unsupported')

    def test_choose_keyword_and_apply_temporary_stats(self):
        sim,cards=self.fixture(["Alchemist's Gift"])
        ally=self.token(sim,'ally',power=2,toughness=2)
        spell=cards["Alchemist's Gift"]
        sim.cast_spell(0,spell,target=ally.card.id,keyword_choice='lifelink')
        self.assertEqual(sim.effective_card(ally).power,2)
        self.drain(sim)
        game=sim.event_game('main');state=game.battlefield[ally.card.id]
        self.assertEqual(game.stats(state),(3,3))
        self.assertTrue(game.has(state,'lifelink'))
        self.assertFalse(game.has(state,'deathtouch'))
        self.assertIn(spell,sim.players[0].graveyard)
        sim.invariant()

    def test_illegal_choice_and_protected_target_rejected_before_payment(self):
        sim,cards=self.fixture(["Alchemist's Gift"])
        ally=self.token(sim,'ally')
        enemy=self.token(sim,'enemy',seat=1,keywords=('hexproof',))
        spell=cards["Alchemist's Gift"]
        with self.assertRaises(ValueError):
            sim.cast_spell(0,spell,target=ally.card.id,keyword_choice='trample')
        with self.assertRaises(ValueError):
            sim.cast_spell(0,spell,target=enemy.card.id,keyword_choice='lifelink')
        self.assertIn(spell,sim.players[0].hand)
        sim.invariant()

    def test_target_leaves_before_resolution_and_spell_fizzles(self):
        sim,cards=self.fixture(["Alchemist's Gift"])
        ally=self.token(sim,'ally')
        spell=cards["Alchemist's Gift"]
        sim.cast_spell(0,spell,target=ally.card.id,keyword_choice='deathtouch')
        sim.send_to_destination(sim.players[0],ally)
        self.drain(sim)
        self.assertIn(spell,sim.players[0].graveyard)
        self.assertTrue(any(e['kind']=='modifier_fizzle' for e in sim.events))
        sim.invariant()
