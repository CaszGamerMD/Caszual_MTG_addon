"""Rogue-entry counter replacement and conditional combat-discard triggers."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
from card_events import Game,Permanent,parse_card
import test_enchantment_abilities as helpers

class RogueEntryCountersChecks(unittest.TestCase):
    setUpClass=classmethod(helpers.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(helpers.EnchantmentChecks.tearDownClass.__func__)
    fixture=helpers.EnchantmentChecks.fixture
    put=helpers.EnchantmentChecks.put
    token=helpers.EnchantmentChecks.token
    drain=helpers.EnchantmentChecks.drain

    def test_oona_and_unknown_creature_type_parse_entire_text(self):
        raw=dict(self.lookup["Oona's Blackguard"],name="Unknown blackguard")
        parsed=s.import_diagnostic_card(self.rules,raw,0,'oona',{'Black'})
        self.assertEqual(parsed.kind,'creature')
        self.assertEqual(len(parsed.event_definition.entry_counter_grants),1)
        subject,amount=parsed.event_definition.entry_counter_grants[0]
        self.assertEqual((subject.subtype,amount),('Rogue',1))
        trigger=parsed.event_definition.triggers[0]
        self.assertEqual((trigger.event,trigger.min_counters),('combat_damage',1))
        variant=dict(raw,oracleText=raw['oracleText'].replace('Rogue creature','Elf creature').replace('an additional','two additional'))
        parsed=s.import_diagnostic_card(self.rules,variant,0,'variant',set())
        self.assertEqual(parsed.event_definition.entry_counter_grants[0][1],2)
        self.assertEqual(parsed.event_definition.entry_counter_grants[0][0].subtype,'Elf')
        variant['oracleText']+='\nDraw an unspecified bonus card.'
        self.assertEqual(s.import_diagnostic_card(self.rules,variant,0,'bad',set()).kind,'unsupported')

    def test_only_other_controller_rogues_get_counter_on_entry(self):
        sim,cards=self.fixture(["Oona's Blackguard"])
        source=self.put(sim,cards["Oona's Blackguard"])
        self.assertEqual(source.counters,0)
        rogue=self.token(sim,'ally',subtypes=('Rogue',))
        other=self.token(sim,'other',subtypes=('Elf',))
        enemy=self.token(sim,'enemy',seat=1,subtypes=('Rogue',))
        self.assertEqual((rogue.counters,other.counters,enemy.counters),(1,0,0))
        self.assertEqual(sim.effective_card(rogue).power,3)
        sim.send_to_destination(sim.players[0],source)
        after=self.token(sim,'later',subtypes=('Rogue',))
        self.assertEqual(after.counters,0)
        self.assertEqual(rogue.counters,1)
        sim.invariant()

    def test_countered_rogue_deals_combat_damage_and_discards_once(self):
        sim,cards=self.fixture(["Oona's Blackguard"])
        self.put(sim,cards["Oona's Blackguard"])
        attacker=self.token(sim,'attacker',subtypes=('Rogue',),power=2,toughness=2)
        self.assertEqual(attacker.counters,1)
        for permanent in sim.players[0].battlefield:permanent.fresh=False
        sim.phase='attack';sim.stack.priority=sim.active
        before=len(sim.players[1].hand)
        sim.declare_attackers([attacker.card.id]);sim.declare_blockers({})
        sim.group_damage_step()
        self.assertTrue(any(f.payload[0]['operation']=='discard' for f in sim.stack.items))
        self.drain(sim)
        self.assertEqual(len(sim.players[1].hand),before-1)
        self.assertTrue(any(e['kind']=='trigger' and 'discards' in e['message'] for e in sim.events))
        sim.invariant()

    def test_nonrogue_with_counter_also_triggers_and_uncountered_rogue_does_not(self):
        sim,cards=self.fixture(["Oona's Blackguard"])
        source=self.put(sim,cards["Oona's Blackguard"])
        attacker=self.token(sim,'elf',subtypes=('Elf',))
        attacker.counters=1
        for permanent in sim.players[0].battlefield:permanent.fresh=False
        sim.phase='attack';sim.stack.priority=sim.active
        sim.declare_attackers([attacker.card.id]);sim.declare_blockers({})
        sim.group_damage_step()
        self.assertTrue(any(f.payload[0]['operation']=='discard' for f in sim.stack.items))
        self.drain(sim);sim.invariant()
        sim.send_to_destination(sim.players[0],source)
        self.assertEqual(attacker.counters,1)

    def test_simultaneous_entry_ignores_other_entrant_replacement(self):
        effect=dict(name='Rule source',types=['Creature'],subTypes=['Rogue'],
                    power='2',toughness='2',manaCost='{1}',
                    oracleText='Each other Rogue creature you control enters with an additional +1/+1 counter on it.')
        definition=parse_card(effect)
        self.assertTrue(definition.supported)
        target=parse_card(dict(name='Target',types=['Creature'],subTypes=['Rogue'],
                               power='2',toughness='2',oracleText=''))
        game=Game()
        first=Permanent('first',definition,0)
        second=Permanent('second',target,0)
        game.enter_batch([first,second])
        self.assertEqual((first.counters,second.counters),(0,0))
        third=Permanent('third',target,0)
        game.enter_batch([third])
        self.assertEqual(third.counters,1)

