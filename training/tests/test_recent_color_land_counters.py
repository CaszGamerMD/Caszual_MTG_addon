"""Color-qualified entered-this-turn land counters use resolution-time battlefield."""
import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
import test_enchantment_abilities as fixtures

class RecentLandCountersChecks(unittest.TestCase):
    setUpClass=classmethod(fixtures.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.EnchantmentChecks.tearDownClass.__func__)
    fixture=fixtures.EnchantmentChecks.fixture
    put=fixtures.EnchantmentChecks.put
    token=fixtures.EnchantmentChecks.token
    drain=fixtures.EnchantmentChecks.drain

    def setup_land(self):
        sim,_=self.fixture([])
        raw=self.lookup['Oran-Rief, the Vastwood']
        card=s.import_diagnostic_card(self.rules,raw,0,'oran',{'Green'})
        self.assertEqual(card.kind,'land')
        sim.players[0].library.append(card);sim.card_owners[card.id]=0
        sim.total_cards=(sim.total_cards[0]+1,sim.total_cards[1])
        sim.players[0].library.remove(card)
        pending=sim.enter_creature(card,sim.players[0]);sim.resolve_entry_triggers(pending,card)
        land=next(p for p in sim.players[0].battlefield if p.card.id==card.id)
        land.tapped=False
        return sim,card,land

    def test_oracle_unseen_name_color_variants_and_strict_remainder(self):
        raw=dict(self.lookup['Oran-Rief, the Vastwood'],name='Unseen orchard')
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'a',{'Green'}).kind,'land')
        raw['oracleText']=raw['oracleText'].replace('green creature','white creature')
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'b',{'White'}).kind,'land')
        raw['oracleText']+='\nCreate a mysterious creature.'
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'c',{'White'}).kind,'unsupported')

    def test_only_controlled_green_creatures_entered_this_turn_get_counters(self):
        sim,card,land=self.setup_land()
        early=self.token(sim,'old',colors=('Green',))
        blue=self.token(sim,'blue',colors=('Blue',))
        opponent=self.token(sim,'enemy',seat=1,colors=('Green',))
        for entry in sim.entry_history:
            if entry.get('id')=='old':entry['turn']=sim.turn-1
        recent=self.token(sim,'recent',colors=('Green',))
        sim.activate_land_counters(0,card.id)
        self.assertTrue(land.tapped)
        self.assertEqual(recent.counters,0)
        self.drain(sim)
        self.assertEqual((early.counters,blue.counters,opponent.counters,recent.counters),(0,0,0,1))
        sim.invariant()

    def test_new_entrant_before_resolution_counts_and_counter_replacement_applies(self):
        sim,card,land=self.setup_land()
        sim.activate_land_counters(0,card.id)
        late=self.token(sim,'late',colors=('Green',))
        replacement=s.EventDefinition('Counter doubler',frozenset({'Enchantment'}),frozenset(),False,0,0,
            frozenset(),counter_replacements=(('double',2,'controlled_creature'),))
        sim.enter_creature(s.Card('double','Counter doubler','enchantment',event_definition=replacement,is_token=True),sim.players[0])
        self.drain(sim)
        self.assertEqual(late.counters,2)
        sim.invariant()

    def test_tap_cost_and_reset_prevent_repeated_activation(self):
        sim,card,land=self.setup_land()
        self.assertTrue(sim.land_counter_choices(0))
        sim.activate_land_counters(0,card.id)
        with self.assertRaises(ValueError):sim.activate_land_counters(0,card.id)
        self.drain(sim)
        sim.invariant()
