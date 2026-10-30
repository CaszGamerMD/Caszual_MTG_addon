"""Land type layer changes affect all players' mana and suppress overwritten abilities."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
import test_enchantment_abilities as f

class LandTypeCycle(unittest.TestCase):
    setUpClass=classmethod(f.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(f.EnchantmentChecks.tearDownClass.__func__)
    fixture=f.EnchantmentChecks.fixture
    put=f.EnchantmentChecks.put

    def land(self,sim,name,seat=0,mask=2,basic=False):
        card=s.Card(name,name,'land',mask=mask,basic_land=basic,is_token=True,
                    land_subtypes=('Island',) if basic else ())
        perm=s.Permanent(card)
        sim.players[seat].battlefield.append(perm)
        return perm

    def test_full_oracle_unknown_name_other_land_type_and_extra_text(self):
        raw=dict(self.lookup['Blood Moon'],name='Unseen lunar enchantment')
        card=s.import_diagnostic_card(self.rules,raw,0,'a',{'Red'})
        self.assertEqual(card.event_definition.land_type_effect,('nonbasic','replace',('Mountain',)))
        raw['oracleText']='Nonbasic lands are Forests.'
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'b',{'Red'}).event_definition.land_type_effect,
                         ('nonbasic','replace',('Forest',)))
        raw['oracleText']+='\nDraw a card.'
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'bad',{'Red'}).kind,'unsupported')
        raw=dict(self.lookup['Urborg, Tomb of Yawgmoth'],name='Unseen swamp realm')
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'c',set()).kind,'land')
        raw['oracleText']+='\nUntap target land.'
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'d',set()).kind,'unsupported')

    def test_blood_moon_replaces_nonbasic_production_not_basic_land(self):
        sim,cards=self.fixture(['Blood Moon'])
        dual=self.land(sim,'nonbasic-dual',seat=1,mask=3)
        basic=self.land(sim,'basic-island',seat=1,mask=2,basic=True)
        self.assertEqual(set(i for i in range(6) if any(v[i] for v in dict(sim.mana_sources(1))[dual.card.id])),{0,1})
        moon=self.put(sim,cards['Blood Moon'])
        options=dict(sim.mana_sources(1))
        self.assertEqual(options[dual.card.id],((0,0,0,1,0,0),))
        self.assertTrue(sim.payment(s.Card('red-spell','Red','spell',mana_cost='{R}'),seat=1)['paid'])
        self.assertFalse(sim.payment(s.Card('blue-spell','Blue','spell',mana_cost='{U}{U}{U}{U}{U}{U}{U}{U}{U}{U}{U}'),seat=1)['paid'])
        self.assertEqual(options[basic.card.id],((0,1,0,0,0,0),))
        self.assertEqual(sim.event_game('main').battlefield[dual.card.id].definition.subtypes,frozenset({'Mountain'}))
        sim.send_to_destination(sim.players[0],moon)
        self.assertEqual(set(i for i in range(6) if any(v[i] for v in dict(sim.mana_sources(1))[dual.card.id])),{0,1})
        sim.invariant()

    def test_urborg_adds_swamp_to_both_players_and_blood_moon_turns_it_off(self):
        sim,cards=self.fixture(['Urborg, Tomb of Yawgmoth','Blood Moon'])
        own=self.land(sim,'own-plains',mask=1,basic=True)
        enemy=self.land(sim,'enemy-island',seat=1,mask=2,basic=True)
        urborg=self.put(sim,cards['Urborg, Tomb of Yawgmoth'])
        self.assertEqual(sim.event_game('main').battlefield[enemy.card.id].definition.subtypes,
                         frozenset({'Island','Swamp'}))
        self.assertEqual(set(i for i in range(6) if any(v[i] for v in dict(sim.mana_sources(1))[enemy.card.id])),{1,2})
        moon=self.put(sim,cards['Blood Moon'])
        self.assertEqual(sim.event_game('main').battlefield[urborg.card.id].definition.subtypes,
                         frozenset({'Mountain'}))
        self.assertEqual(set(i for i in range(6) if any(v[i] for v in dict(sim.mana_sources(1))[enemy.card.id])),{1})
        sim.send_to_destination(sim.players[0],moon)
        self.assertEqual(set(i for i in range(6) if any(v[i] for v in dict(sim.mana_sources(1))[enemy.card.id])),{1,2})
        sim.invariant()

    def test_moon_suppresses_nonbasic_land_activated_abilities(self):
        sim,cards=self.fixture(['Blood Moon','Gavony Township'])
        township=self.put(sim,cards['Gavony Township'])
        self.assertTrue(any(c.card_id==township.card.id for c in sim.land_counter_choices(0)))
        moon=self.put(sim,cards['Blood Moon'])
        self.assertFalse(any(c.card_id==township.card.id for c in sim.land_counter_choices(0)))
        with self.assertRaisesRegex(ValueError,'Illegal land counter activation'):
            sim.activate_land_counters(0,township.card.id)
        sim.send_to_destination(sim.players[0],moon)
        self.assertTrue(any(c.card_id==township.card.id for c in sim.land_counter_choices(0)))
        sim.invariant()

    def test_overridden_nonbasic_land_loses_enter_tapped_ability(self):
        sim,cards=self.fixture(['Blood Moon'])
        moon=self.put(sim,cards['Blood Moon'])
        land=s.Card('new-nonbasic','New nonbasic','land',mask=2,land_rule='reveal_types:Forest',is_token=True)
        self.assertFalse(sim.land_entry_tapped(land,0,[]))
        sim.send_to_destination(sim.players[0],moon)
        self.assertTrue(sim.land_entry_tapped(land,0,[]))
        sim.invariant()
