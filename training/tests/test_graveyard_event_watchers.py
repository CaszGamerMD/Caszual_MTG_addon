"""Subtype death and noncreature graveyard triggers use real zone moves."""
import sys
import unittest
from unittest.mock import patch
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
import test_enchantment_abilities as helper

class GraveyardEventWatchersChecks(unittest.TestCase):
    setUpClass=classmethod(helper.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(helper.EnchantmentChecks.tearDownClass.__func__)
    fixture=helper.EnchantmentChecks.fixture
    put=helper.EnchantmentChecks.put
    token=helper.EnchantmentChecks.token
    drain=helper.EnchantmentChecks.drain

    def test_real_and_renamed_card_rules_and_strict_remainder(self):
        for name in ('Knucklebone Witch','Uglúk of the White Hand','Starfield Mystic'):
            raw=dict(self.lookup[name],name='Unknown source')
            if name=='Uglúk of the White Hand':raw['oracleText']=raw['oracleText'].replace('Uglúk','Unknown')
            imported=s.import_diagnostic_card(self.rules,raw,0,'new',set())
            self.assertEqual(imported.kind,'creature',name)
            self.assertTrue(any(t.event in ('dies','graveyard') for t in imported.event_definition.triggers))
            raw['oracleText']+='\nUnknown additional instruction.'
            self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'bad',set()).kind,'unsupported')

    def test_goblin_graveyard_events_trigger_knucklebone_and_can_be_declined(self):
        sim,cards=self.fixture(['Knucklebone Witch'])
        witch=self.put(sim,cards['Knucklebone Witch'])
        goblin=self.token(sim,'goblin',subtypes=('Goblin',),power=2,toughness=2)
        sim.destroy_batch(((0,goblin),),witch.card)
        self.assertTrue(any(f.payload[0].get('operation')=='self_counter' for f in sim.stack.items))
        self.drain(sim)
        self.assertEqual(witch.counters,1)
        second=self.token(sim,'second',subtypes=('Goblin',))
        sim.destroy_batch(((0,second),),witch.card)
        with patch.object(sim,'choose_optional_self_counter',return_value=False):
            self.drain(sim)
        self.assertEqual(witch.counters,1)
        sim.invariant()

    def test_ugluks_conditional_counter_depends_on_dead_creature_subtype(self):
        sim,cards=self.fixture(['Uglúk of the White Hand'])
        ugluk=self.put(sim,cards['Uglúk of the White Hand'])
        elf=self.token(sim,'elf',subtypes=('Elf',))
        goblin=self.token(sim,'goblin',subtypes=('Goblin',))
        sim.destroy_batch(((0,elf),),ugluk.card);self.drain(sim)
        self.assertEqual(ugluk.counters,1)
        sim.destroy_batch(((0,goblin),),ugluk.card);self.drain(sim)
        self.assertEqual(ugluk.counters,3)
        sim.invariant()

    def test_starfield_mystic_tracks_enchantments_to_graveyard(self):
        sim,cards=self.fixture(['Starfield Mystic','Anthem of Champions'])
        mystic=self.put(sim,cards['Starfield Mystic'])
        enchantment=self.put(sim,cards['Anthem of Champions'])
        sim.destroy_batch(((0,enchantment),),mystic.card)
        self.drain(sim)
        self.assertEqual(mystic.counters,1)
        sim.invariant()

    def test_blink_goes_through_exile_not_graveyard(self):
        sim,cards=self.fixture(['Knucklebone Witch','Cloudshift'])
        witch=self.put(sim,cards['Knucklebone Witch'])
        goblin=self.token(sim,'victim',subtypes=('Goblin',))
        sim.cast_spell(0,cards['Cloudshift'],target=goblin.card.id)
        self.drain(sim)
        self.assertEqual(witch.counters,0)
        sim.invariant()

    def test_other_zone_moves_do_not_trigger_graveyard_watchers(self):
        sim,cards=self.fixture(['Starfield Mystic','Anthem of Champions'])
        mystic=self.put(sim,cards['Starfield Mystic'])
        enchantment=self.put(sim,cards['Anthem of Champions'])
        sim.send_to_destination(sim.players[0],enchantment,to_exile=True)
        self.drain(sim)
        self.assertEqual(mystic.counters,0)
        sim.invariant()
