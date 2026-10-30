"""Changeling is every creature type in every zone, not noncreature subtypes."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
from creature_types import has_subtype, card_has_subtype
import test_enchantment_abilities as fixtures

class ChangelingCreatureTypesCycle(unittest.TestCase):
    setUpClass=classmethod(fixtures.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.EnchantmentChecks.tearDownClass.__func__)
    fixture=fixtures.EnchantmentChecks.fixture
    put=fixtures.EnchantmentChecks.put
    token=fixtures.EnchantmentChecks.token
    drain=fixtures.EnchantmentChecks.drain

    def test_real_unseen_and_unknown_remainder(self):
        for name in ('Universal Automaton','Woodland Changeling','Guardian Gladewalker'):
            raw=self.lookup[name]
            parsed=s.import_diagnostic_card(self.rules,raw,0,'real-'+name,{'Green'})
            self.assertEqual(parsed.kind,'creature',name)
            self.assertIn('changeling',parsed.event_definition.abilities)
            renamed=dict(raw,name='Unseen Omnitype Creature')
            self.assertEqual(s.import_diagnostic_card(self.rules,renamed,0,'new',{'Green'}).kind,'creature')
            renamed['oracleText']+='\nAll opponents lose the game.'
            self.assertEqual(s.import_diagnostic_card(self.rules,renamed,0,'bad',{'Green'}).kind,'unsupported')

    def test_characteristic_in_all_zones_and_not_noncreature_types(self):
        sim,cards=self.fixture(['Universal Automaton','Woodland Changeling'])
        automaton=cards['Universal Automaton']
        for kind in ('Elf','Goblin','Squirrel','Faerie','Sliver','Shapeshifter'):
            self.assertTrue(card_has_subtype(automaton,kind),kind)
        for kind in ('Forest','Mountain','Aura','Equipment','Treasure','Vehicle'):
            self.assertFalse(card_has_subtype(automaton,kind),kind)
        source=self.put(sim,automaton)
        state=sim.event_game('main').battlefield[source.card.id]
        self.assertTrue(has_subtype(state.definition,'Elf'))
        self.assertTrue(has_subtype(state.definition,'Squirrel'))
        sim.send_to_destination(sim.players[0],source)
        self.assertTrue(card_has_subtype(sim.players[0].graveyard[-1],'Goblin'))
        sim.invariant()

    def test_counted_mana_and_global_tribal_anthem_see_changeling(self):
        sim,cards=self.fixture(['Priest of Titania','Elvish Champion','Universal Automaton'])
        priest=self.put(sim,cards['Priest of Titania']);priest.fresh=False
        champion=self.put(sim,cards['Elvish Champion'])
        automaton=self.put(sim,cards['Universal Automaton'])
        self.assertEqual(sim.effective_card(automaton).power,2)
        self.assertEqual(dict(sim.mana_sources(0))[priest.card.id][0][4],3)
        game=sim.event_game('main')
        self.assertTrue(game.has(game.battlefield[automaton.card.id],'forestwalk'))
        sim.send_to_destination(sim.players[0],champion)
        self.assertEqual(sim.effective_card(automaton).power,1)
        self.assertEqual(dict(sim.mana_sources(0))[priest.card.id][0][4],2)
        sim.invariant()

    def test_changeling_spell_qualifies_for_tribal_cost_discount(self):
        sim,cards=self.fixture(['Goblin Warchief','Universal Automaton'])
        self.put(sim,cards['Goblin Warchief'])
        card=cards['Universal Automaton']
        for land in sim.players[0].battlefield:
            if land.card.kind=='land':land.tapped=True
        self.assertTrue(sim.payment(card,seat=0)['paid'])
        other=s.Card('unseen','Nonchangeling','creature',mana_cost='{1}',printed_types=('Creature',),land_subtypes=('Shapeshifter',))
        self.assertFalse(sim.payment(other,seat=0)['paid'])
        sim.invariant()

if __name__=='__main__':unittest.main()
