"""Real graveyard recursion from spells/upkeep; fear restriction."""
import sys
import unittest
from unittest.mock import patch
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
import test_enchantment_abilities as fixtures

class GraveyardReturnChecks(unittest.TestCase):
    setUpClass=classmethod(fixtures.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.EnchantmentChecks.tearDownClass.__func__)
    fixture=fixtures.EnchantmentChecks.fixture
    put=fixtures.EnchantmentChecks.put
    drain=fixtures.EnchantmentChecks.drain
    token=fixtures.EnchantmentChecks.token

    def grave(self,sim,card):
        if card in sim.players[0].hand:sim.players[0].hand.remove(card)
        sim.players[0].graveyard.append(card)

    def test_boggart_birth_rite_parses_without_card_name(self):
        raw=dict(self.lookup['Boggart Birth Rite'],name='Unknown tribal recovery')
        parsed=s.import_diagnostic_card(self.rules,raw,0,'rite',set())
        self.assertEqual((parsed.kind,parsed.graveyard_return_subtype),('graveyard_return_spell','Goblin'))
        raw['oracleText']='Return target Elf card from your graveyard to your hand.'
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'elf',set()).graveyard_return_subtype,'Elf')
        raw['oracleText']+='\nCreate an unparsed effect.'
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'bad',set()).kind,'unsupported')

    def test_targeted_spell_uses_graveyard_target_and_resolves(self):
        sim,cards=self.fixture(['Boggart Birth Rite','Goblin Matron'])
        spell=cards['Boggart Birth Rite'];target=cards['Goblin Matron']
        self.grave(sim,target)
        candidates=[x for x in sim.legal(0) if x.card_id==spell.id and x.target_permanent==target.id]
        self.assertEqual(len(candidates),1)
        sim.cast_spell(0,spell,target=target.id)
        self.assertIn(target,sim.players[0].graveyard)
        self.drain(sim)
        self.assertIn(target,sim.players[0].hand)
        self.assertIn(spell,sim.players[0].graveyard)
        sim.invariant()

    def test_illegal_target_fails_then_can_disappear_before_resolution(self):
        sim,cards=self.fixture(['Boggart Birth Rite','Goblin Matron'])
        spell=cards['Boggart Birth Rite'];target=cards['Goblin Matron']
        with self.assertRaisesRegex(ValueError,'Graveyard return requires legal target'):
            sim.cast_spell(0,spell,target=target.id)
        self.grave(sim,target)
        sim.cast_spell(0,spell,target=target.id)
        sim.players[0].graveyard.remove(target)
        sim.players[0].exile.append(target)
        self.drain(sim)
        self.assertNotIn(target,sim.players[0].hand)
        self.assertTrue(any(e['kind']=='illegal_target' for e in sim.events))
        sim.invariant()

    def test_wort_fear_and_upkeep_return_uses_target_on_stack(self):
        sim,cards=self.fixture(['Wort, Boggart Auntie','Goblin Matron'])
        source=self.put(sim,cards['Wort, Boggart Auntie'])
        target=cards['Goblin Matron'];self.grave(sim,target)
        self.assertIn('fear',sim.effective_card(source).traits)
        game=sim.event_game('main');game.turn_player=0
        triggers=game.upkeep_triggers()
        self.assertEqual(len(triggers),1)
        sim.resolve_entry_triggers(triggers,source.card)
        self.assertEqual(len(sim.stack.items),1)
        self.assertEqual(sim.stack.items[-1].payload[0].get('target'),target.id)
        self.drain(sim)
        self.assertIn(target,sim.players[0].hand)
        sim.invariant()

    def test_fear_allows_black_and_artifact_creatures_not_uncolored(self):
        sim,cards=self.fixture(['Wort, Boggart Auntie'])
        source=self.put(sim,cards['Wort, Boggart Auntie'])
        blocker=self.token(sim,'colorless',seat=1)
        self.assertFalse(sim.can_block(source,blocker))
        state=sim.event_game('main').battlefield[blocker.card.id]
        from dataclasses import replace
        state.definition=replace(state.definition,colors=frozenset({'Black'}))
        # event_game builds a fresh view; change source metadata too
        blocker.card=replace(blocker.card,event_definition=state.definition)
        self.assertTrue(sim.can_block(source,blocker))
        sim.invariant()
