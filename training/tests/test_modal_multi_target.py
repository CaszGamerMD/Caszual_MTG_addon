"""Choose-two modal Oracle program, real Verdant Command and failure cases."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
from test_modal_target_cast import ModalCastTests

VERDANT=("Choose two —\n"
         "• Target player creates two tapped 1/1 green Squirrel creature tokens.\n"
         "• Counter target loyalty ability of a planeswalker.\n"
         "• Exile target card from a graveyard.\n"
         "• Target player gains 3 life.")

class ModalMultiTargetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.rules=s.RulesBridge()
    @classmethod
    def tearDownClass(cls):cls.rules.close()

    def spell(self,oracle=VERDANT,name="Verdant Command",cost="{1}{G}"):
        raw=dict(name=name,layout="normal",types=["Instant"],superTypes=[],
                 subTypes=[],manaCost=cost,oracleText=oracle,colors=["Green"])
        return s.import_diagnostic_card(self.rules,raw,0,"modal-multi",
                {"White","Green","Red","Blue","Black"})

    def fixture(self,spell):
        return ModalCastTests.fixture(self,spell)

    @staticmethod
    def resolve(sim):
        while sim.stack.items:sim.pass_priority(sim.stack.priority)

    @staticmethod
    def squirrels(sim,seat):
        return [p for p in sim.players[seat].battlefield
                if p.card.is_token and p.card.event_definition
                and 'Squirrel' in p.card.event_definition.subtypes]

    def test_verdant_command_complete_oracle_import_and_unknown_name(self):
        spell=self.spell()
        self.assertEqual(spell.kind,'modal_target_spell')
        self.assertEqual(spell.modal_target_program.choose,2)
        self.assertEqual([mode.operation for mode in spell.modal_target_program.modes],
                         ['create_tokens','counter_ability','exile','gain_life'])
        self.assertEqual(self.spell(name='Unseen green command').kind,'modal_target_spell')
        self.assertEqual(self.spell(VERDANT+'\n• Draw a card.').kind,'unsupported')

    def test_two_modes_create_tapped_squirrels_for_a_target_player_then_gain_life(self):
        spell=self.spell()
        sim,_,_,_,_=self.fixture(spell)
        before=sim.players[1].life
        sim.cast_spell(0,spell,target=('player:1','player:1'),modal_modes=(0,3))
        self.resolve(sim)
        tokens=self.squirrels(sim,1)
        self.assertEqual(len(tokens),2)
        self.assertTrue(all(p.tapped and p.card.power==1 and p.card.toughness==1
                            for p in tokens))
        self.assertTrue(all(p.card.event_definition.colors==frozenset({'Green'})
                            for p in tokens))
        self.assertEqual(sim.players[1].life,before+3)
        self.assertIn(spell,sim.players[0].graveyard)
        sim.invariant()

    def test_exile_graveyard_and_gain_life_in_oracle_order(self):
        spell=self.spell()
        sim,_,_,_,yard=self.fixture(spell)
        sim.cast_spell(0,spell,target=(yard.id,'player:0'),modal_modes=(2,3))
        self.resolve(sim)
        self.assertIn(yard,sim.players[1].exile)
        self.assertNotIn(yard,sim.players[1].graveyard)
        self.assertEqual(sim.players[0].life,43)
        sim.invariant()

    def test_partial_target_failure_does_not_fizzle_other_mode(self):
        spell=self.spell()
        sim,_,_,_,yard=self.fixture(spell)
        sim.cast_spell(0,spell,target=(yard.id,'player:0'),modal_modes=(2,3))
        sim.players[1].graveyard.remove(yard)
        sim.players[1].exile.append(yard)
        self.resolve(sim)
        self.assertEqual(sim.players[0].life,43)
        self.assertTrue(any(e['kind']=='modal_target_skipped' for e in sim.events))
        sim.invariant()

    def test_invalid_mode_and_target_combinations_fail_before_spending_mana(self):
        spell=self.spell()
        sim,_,_,_,yard=self.fixture(spell)
        invalid=[((0,3),('player:0',yard.id)),
                 ((2,3),(yard.id,)),
                 ((2,2),(yard.id,yard.id)),
                 ((0,),( 'player:0',)),
                 ((0,4),('player:0','player:1')),
                 ((True,3),('player:0','player:1')),
                 ((1,3),('ability:123','player:0'))]
        for modes,target in invalid:
            with self.subTest(modes=modes,target=target):
                with self.assertRaises(ValueError):
                    sim.cast_spell(0,spell,modal_modes=modes,target=target)
                self.assertIn(spell,sim.players[0].hand)
                self.assertFalse(sim.stack.items)
                self.assertTrue(all(not p.tapped for p in sim.players[0].battlefield))
        sim.invariant()

    def test_ai_selections_include_both_modes_and_both_targets(self):
        spell=self.spell()
        sim,_,_,_,yard=self.fixture(spell)
        options=sim.modal_target_choices(0,spell,'cast')
        selected={(c.modal_modes,c.target_permanent) for c in options}
        self.assertIn(((0,3),('player:0','player:1')),selected)
        self.assertIn(((2,3),(yard.id,'player:0')),selected)
        self.assertFalse(any(1 in c.modal_modes for c in options))
        self.assertTrue(all(len(c.target_permanent)==2 for c in options))
        sim.invariant()

    def test_loyalty_counter_mode_targets_only_real_loyalty_stack_entry(self):
        spell=self.spell()
        sim,_,_,_,_=self.fixture(spell)
        ability=sim.stack.push(1,({'operation':'loyalty_ability','sourceType':'Planeswalker'},spell),
                               'Loyalty ability test')
        unrelated=sim.stack.push(1,({'operation':'activated','sourceType':'Planeswalker'},spell),
                                 'Unrelated activated ability')
        sim.stack.priority=0
        options=sim.modal_target_choices(0,spell,'cast')
        self.assertTrue(any(c.modal_modes==(1,3) and
             c.target_permanent==('ability:'+str(ability.id),'player:0') for c in options))
        self.assertFalse(any('ability:'+str(unrelated.id) in str(c.target_permanent)
                             for c in options))
        sim.cast_spell(0,spell,modal_modes=(1,3),
                       target=('ability:'+str(ability.id),'player:0'))
        # Remove unrelated dummy frame, which is not an executable game instruction.
        sim.stack.counter(unrelated.id)
        self.resolve(sim)
        self.assertFalse(any(x.id==ability.id for x in sim.stack.items))
        self.assertTrue(any(e['kind']=='modal_counter_ability' for e in sim.events))
        self.assertEqual(sim.players[0].life,43)
        sim.invariant()

if __name__=='__main__':unittest.main()
