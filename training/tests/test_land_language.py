"""Land entry compositions resolve actual events without card-name dispatch."""
import unittest
from dataclasses import replace
from unittest.mock import patch
import test_enchantment_abilities as fixtures
import simulator as s

NAMES=['Blossoming Sands','Graypelt Refuge','Temple of Plenty','Drowned Catacomb','Fortified Village',"Auntie's Hovel",'Overgrown Tomb','Golgari Rot Farm']

class LandLanguageChecks(unittest.TestCase):
    setUpClass=classmethod(fixtures.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.EnchantmentChecks.tearDownClass.__func__)
    fixture=fixtures.EnchantmentChecks.fixture
    put=fixtures.EnchantmentChecks.put
    drain=fixtures.EnchantmentChecks.drain

    def test_real_and_unseen_compositions_fail_closed(self):
        for name in NAMES:
            raw=dict(self.lookup[name]);raw['name']='Unseen land'
            card=s.import_diagnostic_card(self.rules,raw,0,'land',set())
            self.assertEqual(card.kind,'land',name)
            raw['oracleText']+='\nWhenever you blink, do something unknown.'
            self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'land',set()).kind,'unsupported',name)
        # New numbers and colors compose, not just renamed known cards.
        for amount in (2,3,7):
            raw=dict(self.lookup[NAMES[0]],name='Unseen land',oracleText=f'This land enters tapped.\nWhen this land enters, you gain {amount} life.\n{{T}}: Add {{U}} or {{R}}.')
            card=s.import_diagnostic_card(self.rules,raw,0,'land',set())
            self.assertEqual(card.mask,10)
            self.assertEqual(card.event_definition.triggers[0].effect.amount,amount)

    def test_gainland_enters_tapped_and_gain_waits_for_stack(self):
        sim,cards=self.fixture(['Blossoming Sands',"Ajani's Welcome",'Boon Reflection'])
        self.put(sim,cards["Ajani's Welcome"]);self.put(sim,cards['Boon Reflection'])
        land=self.put(sim,cards['Blossoming Sands'])
        self.assertTrue(land.tapped)
        self.assertEqual(len(sim.stack.items),1) # Not a creature entry.
        self.assertEqual(sim.players[0].life,40)
        sim.send_to_destination(sim.players[0],land)
        self.drain(sim)
        self.assertEqual(sim.players[0].life,42) # Existing replacement applies.
        self.assertEqual(sim.life_gained_turn[0],2)
        sim.invariant()

    def test_play_land_dispatches_entry_without_casting(self):
        sim,cards=self.fixture(['Graypelt Refuge'])
        card=cards['Graypelt Refuge'];sim.phase='land'
        with patch.object(sim,'decide',return_value=s.Candidate('land','land',card.id)):
            sim.step()
        self.assertTrue(sim.land_played)
        self.assertEqual(sim.phase,'main')
        self.assertEqual(len(sim.stack.items),1)
        self.assertFalse(any(e['kind']=='cast' for e in sim.events))
        self.drain(sim)
        self.assertEqual(sim.players[0].life,41)
        sim.invariant()

    def test_scry_land_preserves_private_card_order_under_keep_policy(self):
        sim,cards=self.fixture(['Temple of Plenty'])
        before=list(sim.players[0].library)
        land=self.put(sim,cards['Temple of Plenty'])
        self.assertTrue(land.tapped);self.assertEqual(len(sim.stack.items),1)
        self.drain(sim)
        self.assertEqual(sim.players[0].library,before)
        self.assertTrue(any('scries 1' in e['message'] for e in sim.events))
        sim.invariant()

    def test_reveal_entry_uses_matching_own_hand_and_keeps_card(self):
        for name,reveal in [('Fortified Village','Plains'),("Auntie's Hovel",'Goblin Instigator')]:
            sim,cards=self.fixture([name,reveal])
            land=self.put(sim,cards[name])
            self.assertFalse(land.tapped)
            self.assertIn(cards[reveal],sim.players[0].hand)
            events=[e for e in sim.events if e['kind']=='reveal_land_entry']
            self.assertEqual(len(events),1)
            self.assertEqual(events[0]['details']['card'],reveal)
            self.assertFalse(sim.stack.items);sim.invariant()
        sim,cards=self.fixture(['Fortified Village'])
        land=self.put(sim,cards['Fortified Village'])
        self.assertTrue(land.tapped)
        self.assertFalse(any(e['kind']=='reveal_land_entry' for e in sim.events))

    def test_shock_payment_is_not_damage_or_lifegain_and_can_decline(self):
        for life in (40,2,1):
            sim,cards=self.fixture(['Overgrown Tomb'])
            sim.players[0].life=life
            land=self.put(sim,cards['Overgrown Tomb'])
            self.assertEqual(land.tapped,life<=2)
            self.assertEqual(sim.players[0].life,life-2 if life>2 else life)
            self.assertEqual(sim.life_gained_turn[0],0)
            self.assertFalse(sim.stack.items);sim.invariant()

    def test_checkland_article_variation_and_current_land_types(self):
        for present in (False,True):
            sim,cards=self.fixture(['Drowned Catacomb','Island'])
            if present:self.put(sim,cards['Island'])
            land=self.put(sim,cards['Drowned Catacomb'])
            self.assertEqual(land.tapped,not present)
            game=sim.event_game('main')
            self.assertFalse(game.creature(game.battlefield[land.card.id]))
            sim.invariant()

    def test_dual_land_and_two_mana_land_production(self):
        for name,cost,amount in [('Blossoming Sands','{G}',1),('Golgari Rot Farm','{B}{G}',2)]:
            sim,cards=self.fixture([name])
            land=self.put(sim,cards[name]);self.drain(sim)
            self.assertNotIn(land.card.id,[identifier for identifier,_ in sim.mana_sources(0)])
            land.tapped=False
            sources=[source for source in sim.mana_sources(0) if source[0]==land.card.id]
            self.assertEqual(len(sources),1)
            result=s.mana_pool.plan(cost,[0]*6,sources)
            self.assertTrue(result['paid']);self.assertEqual(result['sources'],[land.card.id])
            self.assertEqual(max(sum(vector) for vector in sources[0][1]),amount)

    def test_bounce_land_can_return_itself_to_owner_not_controller(self):
        sim,cards=self.fixture(['Golgari Rot Farm'])
        card=cards['Golgari Rot Farm'];sim.players[0].hand.remove(card)
        pending=sim.enter_creature(card,sim.players[1])
        sim.resolve_entry_triggers(pending,card)
        self.assertEqual(len(sim.stack.items),1)
        self.assertTrue(sim.players[1].battlefield[-1].tapped)
        self.drain(sim)
        self.assertIn(card,sim.players[0].hand)
        self.assertFalse(sim.players[1].battlefield)
        sim.invariant()

    def test_bounce_land_chooses_at_resolution_after_source_leaves(self):
        sim,cards=self.fixture(['Golgari Rot Farm'])
        source=self.put(sim,cards['Golgari Rot Farm'])
        sim.send_to_destination(sim.players[0],source)
        before=len(sim.players[0].battlefield)
        self.drain(sim)
        self.assertEqual(len(sim.players[0].battlefield),before-1)
        self.assertTrue(any(e['kind']=='return_land' for e in sim.events))
        sim.invariant()
