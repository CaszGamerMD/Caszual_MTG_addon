"""Subtype-aware cost reductions and Goblin stat/keyword anthems."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
from oracle_abilities import compile_abilities
import test_enchantment_abilities as fixtures

class SubtypeRulesChecks(unittest.TestCase):
    setUpClass=classmethod(fixtures.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.EnchantmentChecks.tearDownClass.__func__)
    fixture=fixtures.EnchantmentChecks.fixture
    put=fixtures.EnchantmentChecks.put
    token=fixtures.EnchantmentChecks.token

    def mana(self,sim,number):
        for index,permanent in enumerate(
                p for p in sim.players[0].battlefield if p.card.kind=='land'):
            permanent.tapped=index>=number

    def spell(self,identifier,subtypes):
        return s.Card(identifier,identifier,'creature',mana_cost='{2}{B}',
                      printed_types=('Creature',),land_subtypes=tuple(subtypes),
                      colors=('Black',))

    def test_all_three_real_cards_compile_and_unknown_names_fail_closed(self):
        for name in ('Frogtosser Banneret','Goblin Warchief','Goblin Chieftain'):
            raw=dict(self.lookup[name],name='Unfamiliar tribal card')
            card=s.import_diagnostic_card(self.rules,raw,0,'tribal',{'Red','Black'})
            self.assertEqual(card.kind,'creature',name)
            self.assertIsNotNone(card.event_definition,name)
            self.assertTrue(card.event_definition.cost_reductions or
                            card.event_definition.static_effects,name)
            raw['oracleText']+='\nGoblins you control can fly to the moon.'
            self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'bad',set()).kind,'unsupported',name)

    def test_banneret_reduces_goblin_and_rogue_but_not_unrelated(self):
        sim,cards=self.fixture(['Frogtosser Banneret'])
        banneret=self.put(sim,cards['Frogtosser Banneret'])
        self.assertIn('haste',banneret.card.event_definition.abilities)
        self.mana(sim,2)
        for tags in (('Goblin',),('Rogue',),('Goblin','Rogue')):
            self.assertTrue(sim.payment(self.spell('tribal',tags),seat=0)['paid'],tags)
        self.assertFalse(sim.payment(self.spell('other',('Wizard',)),seat=0)['paid'])
        sim.invariant()

    def test_two_valid_subtypes_still_receive_only_one_discount_per_source(self):
        sim,cards=self.fixture(['Frogtosser Banneret'])
        self.put(sim,cards['Frogtosser Banneret'])
        self.mana(sim,1)
        self.assertFalse(sim.payment(self.spell('dual',('Goblin','Rogue')),seat=0)['paid'])
        sim.invariant()

    def test_warchief_reduces_goblin_spells_and_grants_haste(self):
        sim,cards=self.fixture(['Goblin Warchief'])
        warchief=self.put(sim,cards['Goblin Warchief'])
        goblin=self.token(sim,'goblin',subtypes=('Goblin',))
        rogue=self.token(sim,'rogue',subtypes=('Rogue',))
        opponent=self.token(sim,'opponent',seat=1,subtypes=('Goblin',))
        self.assertIn('haste',sim.effective_card(warchief).traits)
        self.assertIn('haste',sim.effective_card(goblin).traits)
        self.assertNotIn('haste',sim.effective_card(rogue).traits)
        self.assertNotIn('haste',sim.effective_card(opponent).traits)
        self.mana(sim,2)
        self.assertTrue(sim.payment(self.spell('goblin-spell',('Goblin',)),seat=0)['paid'])
        self.assertFalse(sim.payment(self.spell('rogue-spell',('Rogue',)),seat=0)['paid'])
        sim.invariant()

    def test_chieftain_buffs_only_other_controlled_goblins(self):
        sim,cards=self.fixture(['Goblin Chieftain'])
        chieftain=self.put(sim,cards['Goblin Chieftain'])
        friend=self.token(sim,'friend',subtypes=('Goblin',))
        opponent=self.token(sim,'opponent',seat=1,subtypes=('Goblin',))
        other=self.token(sim,'other',subtypes=('Elf',))
        self.assertEqual((sim.effective_card(chieftain).power,sim.effective_card(chieftain).toughness),(2,2))
        self.assertEqual((sim.effective_card(friend).power,sim.effective_card(friend).toughness),(3,3))
        self.assertIn('haste',sim.effective_card(friend).traits)
        self.assertEqual(sim.effective_card(opponent).power,2)
        self.assertEqual(sim.effective_card(other).power,2)
        sim.invariant()

    def test_anthem_is_continuous_and_disappears_when_source_leaves(self):
        sim,cards=self.fixture(['Goblin Chieftain'])
        chieftain=self.put(sim,cards['Goblin Chieftain'])
        ally=self.token(sim,'ally',subtypes=('Goblin',))
        self.assertEqual(sim.effective_card(ally).power,3)
        sim.send_to_destination(sim.players[0],chieftain)
        self.assertEqual(sim.effective_card(ally).power,2)
        self.assertNotIn('haste',sim.effective_card(ally).traits)
        sim.invariant()

    def test_unfamiliar_subtype_and_unknown_clauses_reject_correctly(self):
        text='Goblin spells and Rogue spells you cast cost {2} less to cast.'
        program=compile_abilities(text)
        self.assertIsNotNone(program)
        self.assertEqual(program.cost_reductions,((('subtype:goblin','subtype:rogue'),2),))
        self.assertIsNone(compile_abilities('Banana spells you cast cost {1} less to cast.'))
        self.assertIsNone(compile_abilities('Goblins you control have magical powers.'))
