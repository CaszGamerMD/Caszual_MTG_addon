"""Reusable instant blink wording and ownership/control distinction."""
import sys
import unittest
from pathlib import Path
from dataclasses import replace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
from advanced_simulator import root
import test_enchantment_abilities as fixtures

class BlinkVariantsChecks(unittest.TestCase):
    setUpClass=classmethod(fixtures.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.EnchantmentChecks.tearDownClass.__func__)
    fixture=fixtures.EnchantmentChecks.fixture
    put=fixtures.EnchantmentChecks.put
    drain=fixtures.EnchantmentChecks.drain
    token=fixtures.EnchantmentChecks.token

    def test_saved_cloudshift_oracle_and_renames(self):
        raw=self.lookup['Cloudshift']
        card=s.import_diagnostic_card(self.rules,raw,0,'cloud',{'White'})
        self.assertEqual(card.kind,'blink_spell')
        self.assertTrue(card.blink_to_controller)
        self.assertFalse(card.rebound)
        for wording in (
            "Exile target creature you control, then return that card to the battlefield under your control.",
            "Exile target creature you control, then return it to the battlefield under your control.",
            "Exile target creature you control, then return that card to the battlefield under its owner's control.",
        ):
            alternate=dict(raw,name='Unknown instant',oracleText=wording)
            parsed=s.import_diagnostic_card(self.rules,alternate,0,'alt',set())
            self.assertEqual(parsed.kind,'blink_spell')
            self.assertEqual(parsed.blink_to_controller,wording.endswith('under your control.'))
            alternate['oracleText']+='\nDraw an extra card you cannot interpret.'
            self.assertEqual(s.import_diagnostic_card(self.rules,alternate,0,'bad',set()).kind,'unsupported')

    def test_cloudshift_blinks_real_creature_as_new_object_without_rebound(self):
        sim,cards=self.fixture(['Cloudshift','Cloudspire Coordinator'])
        source=self.put(sim,cards['Cloudspire Coordinator'])
        old=source.card.id
        source.counters=3;source.marked_damage=1;source.fresh=False
        sim.cast_spell(0,cards['Cloudshift'],target=old)
        self.drain(sim)
        returned=next(p for p in sim.players[0].battlefield if root(p.card)==old)
        self.assertNotEqual(returned.card.id,old)
        self.assertEqual((returned.counters,returned.marked_damage),(0,0))
        self.assertTrue(returned.fresh)
        self.assertIn(cards['Cloudshift'],sim.players[0].graveyard)
        self.assertFalse(sim.rebound_pending)
        sim.invariant()

    def test_stolen_opponent_owned_creature_returns_under_casters_control(self):
        sim,cards=self.fixture(['Cloudshift'])
        d=s.EventDefinition('Borrowed',frozenset({'Creature'}),frozenset(),False,3,2,frozenset())
        stolen=s.Card('borrowed','Borrowed','creature',mana_cost='{0}',power=3,toughness=2,
                      traits='3;2;',event_definition=d,printed_types=('Creature',))
        # This physical creature belongs to player 2, but was controlled by
        # player 1 at the time Cloudshift targets it.
        sim.card_owners[stolen.id]=1
        sim.total_cards=(sim.total_cards[0],sim.total_cards[1]+1)
        sim.enter_creature(stolen,sim.players[0])
        sim.cast_spell(0,cards['Cloudshift'],target=stolen.id)
        self.drain(sim)
        returned=[p for p in sim.players[0].battlefield if root(p.card)==stolen.id]
        self.assertEqual(len(returned),1)
        self.assertNotEqual(returned[0].card.id,stolen.id)
        self.assertFalse(any(root(p.card)==stolen.id for p in sim.players[1].battlefield))
        self.assertEqual(sim.card_owners[stolen.id],1)
        sim.invariant()

    def test_owner_wording_still_returns_owner_not_previous_controller(self):
        sim,cards=self.fixture(['Ephemerate'])
        d=s.EventDefinition('Borrowed',frozenset({'Creature'}),frozenset(),False,2,2,frozenset())
        stolen=s.Card('borrowed','Borrowed','creature',power=2,toughness=2,
                      event_definition=d,printed_types=('Creature',))
        sim.card_owners[stolen.id]=1
        sim.total_cards=(sim.total_cards[0],sim.total_cards[1]+1)
        sim.enter_creature(stolen,sim.players[0])
        sim.cast_spell(0,cards['Ephemerate'],target=stolen.id)
        self.drain(sim)
        self.assertTrue(any(root(p.card)==stolen.id for p in sim.players[1].battlefield))
        self.assertFalse(any(root(p.card)==stolen.id for p in sim.players[0].battlefield))
        sim.invariant()

    def test_cloudshift_token_exiles_without_returning(self):
        sim,cards=self.fixture(['Cloudshift'])
        victim=self.token(sim,'temporary')
        sim.cast_spell(0,cards['Cloudshift'],target=victim.card.id)
        self.drain(sim)
        self.assertFalse(any(p.card.id==victim.card.id for p in sim.players[0].battlefield))
        self.assertTrue(any(e['kind']=='blink_token' for e in sim.events))
        sim.invariant()

