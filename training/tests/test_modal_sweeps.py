"""Modal destruction choices are announced on casting and resolved in printed order."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
import test_enchantment_abilities as f
from dataclasses import replace

class ModalSweepsChecks(unittest.TestCase):
    setUpClass=classmethod(f.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(f.EnchantmentChecks.tearDownClass.__func__)
    fixture=f.EnchantmentChecks.fixture
    put=f.EnchantmentChecks.put
    token=f.EnchantmentChecks.token
    drain=f.EnchantmentChecks.drain

    def test_real_card_unseen_name_thresholds_and_unknown_remainder(self):
        raw=dict(self.lookup['Austere Command'],name='Unknown modal purge')
        card=s.import_diagnostic_card(self.rules,raw,0,'modal',{'White'})
        self.assertEqual(card.removal,'modal_sweep')
        self.assertEqual(len(card.modal_sweeps),4)
        raw['oracleText']=raw['oracleText'].replace('value 3','value 2').replace('value 4','value 5')
        changed=s.import_diagnostic_card(self.rules,raw,0,'variant',{'White'})
        self.assertEqual(changed.modal_sweeps[2:],(('creature_mana_le',2),('creature_mana_ge',5)))
        raw['oracleText']+='\n• Create a Mystery token.'
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'bad',{'White'}).kind,'unsupported')

    def test_choose_two_distinct_modes_and_fixed_stack_choices(self):
        sim,cards=self.fixture(['Austere Command'])
        card=cards['Austere Command']
        self.assertEqual(len(sim.removal_choices(0,card,'cast')),6)
        for modes in ((),(0,),(0,0),(1,4),(2,1)):
            with self.assertRaisesRegex(ValueError,'Choose two distinct'):
                sim.cast_spell(0,card,modal_modes=modes)
        sim.cast_spell(0,card,modal_modes=(0,2))
        self.assertEqual(sim.stack.items[-1].payload[0]['modalModes'],(0,2))
        self.drain(sim)
        sim.invariant()

    def test_artifact_and_enchantment_modes_destroy_each_type_but_not_creatures(self):
        sim,cards=self.fixture(['Austere Command','Basilisk Collar','Parallel Lives'])
        collar=self.put(sim,cards['Basilisk Collar'])
        enchant=self.put(sim,cards['Parallel Lives'])
        creature=self.token(sim,'survivor',seat=1)
        sim.cast_spell(0,cards['Austere Command'],modal_modes=(0,1))
        self.drain(sim)
        self.assertNotIn(collar,sim.players[0].battlefield)
        self.assertNotIn(enchant,sim.players[0].battlefield)
        self.assertIn(creature,sim.players[1].battlefield)
        sim.invariant()

    def test_mana_value_modes_respect_tokens_and_indestructible(self):
        sim,cards=self.fixture(['Austere Command'])
        low=self.token(sim,'zero-mv',seat=1)
        safe=self.token(sim,'indestructible-zero',keywords=('indestructible',))
        high=self.token(sim,'high-mv',seat=1)
        high.card=replace(high.card,printed_mana_value=6,is_token=False)
        sim.card_owners[high.card.id]=1
        sim.total_cards=(sim.total_cards[0],sim.total_cards[1]+1)
        sim.cast_spell(0,cards['Austere Command'],modal_modes=(2,3))
        self.drain(sim)
        self.assertNotIn(low,sim.players[1].battlefield)
        self.assertNotIn(high,sim.players[1].battlefield)
        self.assertIn(safe,sim.players[0].battlefield)
        sim.invariant()

    def test_resolution_rechecks_battlefield_after_cast(self):
        sim,cards=self.fixture(['Austere Command'])
        sim.cast_spell(0,cards['Austere Command'],modal_modes=(0,2))
        late=self.token(sim,'late-after-cast',seat=1)
        self.drain(sim)
        self.assertNotIn(late,sim.players[1].battlefield)
        sim.invariant()
