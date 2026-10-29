"""Generic spell cost reduction grammar and legal payment regression tests."""
import sys
import unittest
from pathlib import Path
from dataclasses import replace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
import mana_pool
from oracle_abilities import compile_abilities
import test_enchantment_abilities as base

class CostReductionChecks(unittest.TestCase):
    setUpClass=classmethod(base.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(base.EnchantmentChecks.tearDownClass.__func__)
    fixture=base.EnchantmentChecks.fixture
    put=base.EnchantmentChecks.put

    def spell(self,name,cost,types,colors=(),subtypes=()):
        definition=s.EventDefinition(name,frozenset(types),frozenset(subtypes),False,0,0,frozenset())
        return s.Card(name,name,'aura' if 'Aura' in subtypes else 'spell',cost,
                      event_definition=definition,printed_types=tuple(types),colors=tuple(colors))

    def limit(self,sim,n):
        for i,p in enumerate(x for x in sim.players[0].battlefield if x.card.kind=='land'):
            p.tapped=i>=n

    def test_all_five_real_sources_compile_with_unknown_names(self):
        names=('Emerald Medallion','Pearl Medallion','Jukai Naturalist',
               'Starnheim Courser','Transcendent Envoy')
        for name in names:
            raw=dict(self.lookup[name],name='Unfamiliar reducer')
            card=s.import_diagnostic_card(self.rules,raw,0,'unseen',{'White','Green'})
            self.assertNotEqual(card.kind,'unsupported',name)
            self.assertEqual(len(card.event_definition.cost_reductions),1,name)
            raw['oracleText']+='\nSpells of the future cost anything you like.'
            self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'bad',set()).kind,'unsupported')
        self.assertIsNone(compile_abilities('Purple spells you cast cost {1} less to cast.'))

    def test_single_and_multiple_identical_color_discounts(self):
        sim,cards=self.fixture(['Emerald Medallion','Pearl Medallion'])
        self.put(sim,cards['Emerald Medallion'])
        self.limit(sim,1)
        green=self.spell('green','{2}{G}',('Creature',),('Green',))
        white=self.spell('white','{2}{W}',('Creature',),('White',))
        self.assertFalse(sim.payment(green,seat=0)['paid'])
        self.assertFalse(sim.payment(white,seat=0)['paid'])
        self.limit(sim,2)
        self.assertTrue(sim.payment(green,seat=0)['paid'])
        self.assertFalse(sim.payment(white,seat=0)['paid'])
        self.put(sim,cards['Pearl Medallion'])
        self.assertTrue(sim.payment(white,seat=0)['paid'])
        sim.invariant()

    def test_starnheim_artifact_and_enchantment_not_creature(self):
        sim,cards=self.fixture(['Starnheim Courser'])
        self.put(sim,cards['Starnheim Courser'])
        self.limit(sim,2)
        for types in (('Artifact',),('Enchantment',)):
            self.assertTrue(sim.payment(self.spell('yes','{2}{W}',types),seat=0)['paid'])
        self.assertFalse(sim.payment(self.spell('no','{2}{W}',('Creature',)),seat=0)['paid'])
        sim.invariant()

    def test_transcendent_only_reduces_aura_spells(self):
        sim,cards=self.fixture(['Transcendent Envoy'])
        self.put(sim,cards['Transcendent Envoy'])
        self.limit(sim,2)
        aura=self.spell('aura','{2}{W}',('Enchantment',),('White',),('Aura',))
        self.assertTrue(sim.payment(aura,seat=0)['paid'])
        normal=self.spell('other','{2}{W}',('Enchantment',),('White',))
        self.assertFalse(sim.payment(normal,seat=0)['paid'])
        sim.invariant()

    def test_jukai_reduces_own_type_other_spells_and_not_itself(self):
        sim,cards=self.fixture(['Jukai Naturalist'])
        self.limit(sim,1)
        aura=self.spell('test','{1}{G}',('Enchantment',),('Green',))
        self.assertFalse(sim.payment(aura,seat=0)['paid'])
        self.put(sim,cards['Jukai Naturalist'])
        self.assertTrue(sim.payment(aura,seat=0)['paid'])
        self.assertIn('lifelink',cards['Jukai Naturalist'].event_definition.abilities)
        sim.invariant()

    def test_no_color_symbol_can_be_paid_using_generic_discount(self):
        sim,cards=self.fixture(['Pearl Medallion'])
        self.put(sim,cards['Pearl Medallion'])
        self.limit(sim,3)
        for permanent in sim.players[0].battlefield:
            if permanent.card.kind=='land':permanent.card=replace(permanent.card,mask=16)
        spell=self.spell('white-spell','{2}{W}',('Enchantment',),('White',))
        self.assertFalse(sim.payment(spell,seat=0)['paid'])
        sim.invariant()

    def test_commander_tax_is_reducible_but_activated_ability_cost_is_not(self):
        sim,cards=self.fixture(['Emerald Medallion'])
        self.put(sim,cards['Emerald Medallion'])
        self.limit(sim,3)
        green=self.spell('commander','{G}',('Creature',),('Green',))
        self.assertTrue(sim.payment(green,tax=1,seat=0)['paid'])
        self.limit(sim,1)
        self.assertFalse(sim.payment(green,tax=1,seat=0)['paid'])
        # Unrelated activated costs are never discounted.
        self.assertFalse(sim.payment(self.spell('cost','{2}{G}',('Creature',),('Green',)),
                                     seat=0,spell_cost=False)['paid'])
        sim.invariant()

    def test_generic_x_and_hybrid_symbol_preservation(self):
        self.assertEqual(mana_pool.reduce_generic_cost('{2}{G}',1),'{G}{1}')
        self.assertEqual(mana_pool.reduce_generic_cost('{X}{W/U}',2,x=3),'{W/U}{1}')
        self.assertEqual(mana_pool.reduce_generic_cost('{X}{G}',2,x=1),'{G}{0}')
        self.assertEqual(mana_pool.reduce_generic_cost('{X}{G}',2,x=None),'{X}{G}')
        self.assertEqual(mana_pool.reduce_generic_cost('{W}{G}',9),'{W}{G}{0}')
        self.assertEqual(mana_pool.requirements('{W/U}{1}'),(3,63))
