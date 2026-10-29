"""Reusable begin-combat token triggers and other-attacking-subtype bonuses."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
import test_enchantment_abilities as fixtures

class CombatTribalTokenChecks(unittest.TestCase):
    setUpClass=classmethod(fixtures.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.EnchantmentChecks.tearDownClass.__func__)
    fixture=fixtures.EnchantmentChecks.fixture
    put=fixtures.EnchantmentChecks.put
    token=fixtures.EnchantmentChecks.token
    ready=fixtures.EnchantmentChecks.ready
    drain=fixtures.EnchantmentChecks.drain

    def test_saved_rabblemaster_and_unseen_name_and_parameters(self):
        raw=dict(self.lookup['Goblin Rabblemaster'],name='Unknown tribal captain')
        card=s.import_diagnostic_card(self.rules,raw,0,'unseen',{'Red'})
        self.assertEqual(card.kind,'creature')
        self.assertEqual(card.event_definition.triggers[0].event,'begin_combat')
        self.assertEqual(card.event_definition.attack_effects[0][0],'attacking_subtype_boost')
        raw['oracleText']=raw['oracleText'].replace('+1/+0 until end of turn for each other attacking Goblin',
                                                  '+2/+1 until end of turn for each other attacking Elf')
        modified=s.import_diagnostic_card(self.rules,raw,0,'modified',{'Red'})
        self.assertEqual(modified.event_definition.attack_effects[0][1:4],(2,1,'Elf'))
        raw['oracleText']+='\nWhenever the sun rises, create an unknown thing.'
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'bad',{'Red'}).kind,'unsupported')

    def test_beginning_of_combat_creates_hasty_token_on_stack(self):
        sim,cards=self.fixture(['Goblin Rabblemaster'])
        source=self.put(sim,cards['Goblin Rabblemaster'])
        sim.active=0
        game=sim.event_game('combat');game.turn_player=0
        sim.resolve_entry_triggers(game.begin_combat_triggers(),source.card)
        self.assertEqual(len(sim.stack.items),1)
        self.assertFalse([p for p in sim.players[0].battlefield if p.card.is_token])
        self.drain(sim)
        goblins=[p for p in sim.players[0].battlefield if p.card.is_token and
                 'Goblin' in p.card.event_definition.subtypes]
        self.assertEqual(len(goblins),1)
        self.assertIn('haste',sim.effective_card(goblins[0]).traits)
        sim.invariant()

    def test_attacking_goblins_count_at_resolution_not_nonattackers(self):
        sim,cards=self.fixture(['Goblin Rabblemaster'])
        source=self.put(sim,cards['Goblin Rabblemaster'])
        first=self.token(sim,'first',subtypes=('Goblin',))
        second=self.token(sim,'second',subtypes=('Goblin',))
        idle=self.token(sim,'idle',subtypes=('Goblin',));idle.tapped=True
        elf=self.token(sim,'elf',subtypes=('Elf',))
        self.ready(sim)
        sim.declare_attackers([source.card.id,first.card.id,second.card.id,elf.card.id])
        self.assertEqual(sim.effective_card(source).power,2)
        self.assertTrue(any(f.payload[0].get('operation')=='attacking_subtype_boost' for f in sim.stack.items))
        sim.send_to_destination(sim.players[0],first)
        self.drain(sim)
        self.assertEqual(sim.effective_card(source).power,3)
        sim.invariant()
