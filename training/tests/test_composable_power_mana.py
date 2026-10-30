"""Composition test: Elf-entry trigger + self-power tap-mana (no card-name dispatch)."""
import sys
import json
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
import test_enchantment_abilities as fixtures
from composable_oracle import parse_power_mana


class ComposedPowerManaTests(unittest.TestCase):
    setUpClass=classmethod(fixtures.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.EnchantmentChecks.tearDownClass.__func__)
    fixture=fixtures.EnchantmentChecks.fixture
    put=fixtures.EnchantmentChecks.put
    token=fixtures.EnchantmentChecks.token
    drain=fixtures.EnchantmentChecks.drain

    def raw(self):
        return self.lookup['Marwyn, the Nurturer']

    def test_real_card_is_parsed_from_independent_trigger_and_mana_fragments(self):
        raw=self.raw()
        card=s.import_diagnostic_card(self.rules,raw,0,'marwyn',{'Green'})
        self.assertEqual(card.kind,'creature')
        self.assertEqual(card.event_definition.scaled_mana_tap,'power:G')
        self.assertEqual(len(card.event_definition.triggers),1)
        self.assertEqual(card.event_definition.triggers[0].event,'enters')
        self.assertEqual(card.event_definition.triggers[0].effect.operation,'self_counter')

    def test_unseen_elf_or_goblin_name_and_mana_color_are_parameters(self):
        source=self.raw()
        raw=dict(source,name='Unknown Copper Botanist',subTypes=['Goblin','Druid'],
                 colors=['Red'],colorIdentity=['Red'],
                 oracleText=("Whenever another Goblin you control enters, "
                             "put a +1/+1 counter on Unknown Copper Botanist.\n"
                             "{T}: Add an amount of {R} equal to Unknown Copper Botanist's power."))
        card=s.import_diagnostic_card(self.rules,raw,0,'unseen',{'Red'})
        self.assertEqual(card.kind,'creature')
        self.assertEqual(card.event_definition.scaled_mana_tap,'power:R')
        self.assertEqual(card.event_definition.triggers[0].subject.subtype,'Goblin')
        extra=dict(raw,oracleText=raw['oracleText']+'\nGain unbounded luck.')
        self.assertEqual(s.import_diagnostic_card(self.rules,extra,0,'extra',{'Red'}).kind,
                         'unsupported')

    def test_no_unearned_or_off_color_mana_and_summoning_sickness(self):
        sim,cards=self.fixture(['Marwyn, the Nurturer'])
        marwyn=self.put(sim,cards['Marwyn, the Nurturer'])
        self.assertFalse(any(id==marwyn.card.id for id,_ in sim.mana_sources(0)))
        marwyn.fresh=False
        sources=dict(sim.mana_sources(0))
        self.assertIn(marwyn.card.id,sources)
        self.assertEqual(sources[marwyn.card.id],((0,0,0,0,1,0),))
        choices=sim.scaled_mana_choices(0)
        mana=[x for x in choices if x.card_id==marwyn.card.id]
        self.assertEqual([x.x_value for x in mana],[4])
        with self.assertRaises(ValueError):
            sim.activate_scaled_mana(0,marwyn.card.id,3)
        sim.stack.priority=0
        sim.activate_scaled_mana(0,marwyn.card.id,4)
        self.assertTrue(marwyn.tapped)
        self.assertEqual(sim.players[0].mana_pool[4],1)
        self.assertFalse(any(id==marwyn.card.id for id,_ in sim.mana_sources(0)))
        sim.invariant()

    def test_elf_entry_counter_uses_stack_and_effective_power_for_mana(self):
        sim,cards=self.fixture(['Marwyn, the Nurturer'])
        marwyn=self.put(sim,cards['Marwyn, the Nurturer'])
        marwyn.fresh=False
        ally_type=s.EventDefinition('Unseen ally',frozenset({'Creature'}),
                     frozenset({'Elf'}),False,2,2,frozenset())
        ally=s.Card('ally','Unseen ally','creature','{1}{G}',power=2,
                    toughness=2,event_definition=ally_type,is_token=True)
        triggers=sim.enter_creature(ally,sim.players[0])
        sim.resolve_entry_triggers(triggers,ally)
        self.assertEqual(marwyn.counters,0)  # trigger is on stack, not resolved yet
        self.assertGreaterEqual(len(sim.stack.items),1)
        self.drain(sim)
        self.assertEqual(marwyn.counters,1)
        sources=dict(sim.mana_sources(0))
        self.assertEqual(sources[marwyn.card.id],((0,0,0,0,2,0),))
        # Counters plus a continuous/temporary bonus must scale dynamically.
        marwyn.temporary_power=3
        self.assertEqual(dict(sim.mana_sources(0))[marwyn.card.id],((0,0,0,0,5,0),))
        sim.stack.priority=0
        sim.activate_scaled_mana(0,marwyn.card.id,4)
        self.assertEqual(sim.players[0].mana_pool[4],5)
        sim.invariant()


if __name__=='__main__':
    unittest.main()
