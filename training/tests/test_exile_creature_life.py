"""Swords-like exile and last-known power lifegain, distinct from destroying."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
import test_enchantment_abilities as fixtures

class ExileCreatureLifeChecks(unittest.TestCase):
    setUpClass=classmethod(fixtures.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.EnchantmentChecks.tearDownClass.__func__)
    fixture=fixtures.EnchantmentChecks.fixture
    put=fixtures.EnchantmentChecks.put
    drain=fixtures.EnchantmentChecks.drain

    def creature(self,sim,identifier,seat=1,power=3,abilities=()):
        definition=s.EventDefinition(identifier,frozenset({'Creature'}),frozenset(),
                      False,power,2,frozenset(abilities))
        card=s.Card(identifier,identifier,'creature',mana_cost='{0}',power=power,
                    toughness=2,event_definition=definition,printed_types=('Creature',))
        sim.players[seat].hand.append(card)
        sim.card_owners[card.id]=seat
        sim.total_cards=tuple(n+(i==seat) for i,n in enumerate(sim.total_cards))
        sim.players[seat].hand.remove(card)
        pending=sim.enter_creature(card,sim.players[seat])
        sim.resolve_entry_triggers(pending,card)
        return next(p for p in sim.players[seat].battlefield if p.card.id==card.id)

    def test_actual_oracle_and_unfamiliar_name_compile_without_extra_rules(self):
        raw=dict(self.lookup['Swords to Plowshares'],name='Unfamiliar exile')
        card=s.import_diagnostic_card(self.rules,raw,0,'unknown',{'White'})
        self.assertEqual((card.kind,card.removal),('removal_spell','exile_creature_life'))
        raw['oracleText']+='\nEach player must create a mysterious token.'
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'invalid',set()).kind,'unsupported')

    def test_exile_moves_real_owned_creature_to_exile_and_gains_power(self):
        sim,cards=self.fixture(['Swords to Plowshares'])
        target=self.creature(sim,'enemy',seat=1,power=3)
        sim.cast_spell(0,cards['Swords to Plowshares'],target=target.card.id)
        self.assertIn(target,sim.players[1].battlefield)
        self.drain(sim)
        self.assertNotIn(target,sim.players[1].battlefield)
        self.assertIn(target.card,sim.players[1].exile)
        self.assertNotIn(target.card,sim.players[1].graveyard)
        self.assertEqual([p.life for p in sim.players],[40,43])
        sim.invariant()

    def test_power_uses_last_known_stats_with_current_bonuses(self):
        sim,cards=self.fixture(['Swords to Plowshares'])
        target=self.creature(sim,'boosted',power=2)
        target.temporary_power=4
        sim.cast_spell(0,cards['Swords to Plowshares'],target=target.card.id)
        self.drain(sim)
        self.assertEqual(sim.players[1].life,46)
        sim.invariant()

    def test_indestructible_does_not_prevent_exile(self):
        sim,cards=self.fixture(['Swords to Plowshares'])
        target=self.creature(sim,'indestructible',abilities=('indestructible',))
        sim.cast_spell(0,cards['Swords to Plowshares'],target=target.card.id)
        self.drain(sim)
        self.assertIn(target.card,sim.players[1].exile)
        sim.invariant()

    def test_life_gain_replacements_use_exiled_creatures_controller(self):
        sim,cards=self.fixture(['Swords to Plowshares','Boon Reflection'])
        self.put(sim,cards['Boon Reflection'])
        target=self.creature(sim,'friendly',seat=0,power=3)
        sim.cast_spell(0,cards['Swords to Plowshares'],target=target.card.id)
        self.drain(sim)
        self.assertIn(target.card,sim.players[0].exile)
        self.assertEqual([p.life for p in sim.players],[46,40])
        self.assertEqual(sim.life_gained_turn[0],6)
        sim.invariant()

    def test_target_gone_before_resolution_prevents_exile_and_lifegain(self):
        sim,cards=self.fixture(['Swords to Plowshares'])
        target=self.creature(sim,'missing',power=4)
        sim.cast_spell(0,cards['Swords to Plowshares'],target=target.card.id)
        sim.send_to_destination(sim.players[1],target)
        self.drain(sim)
        self.assertEqual(sim.players[1].life,40)
        self.assertIn(target.card,sim.players[1].graveyard)
        self.assertNotIn(target.card,sim.players[1].exile)
        sim.invariant()

    def test_noncreature_and_opposing_hexproof_are_not_legal_targets(self):
        sim,cards=self.fixture(['Swords to Plowshares'])
        protected=self.creature(sim,'protected',abilities=('hexproof',))
        with self.assertRaisesRegex(ValueError,'legal permanent'):
            sim.cast_spell(0,cards['Swords to Plowshares'],target=protected.card.id)
        definition=s.EventDefinition('artifact',frozenset({'Artifact'}),frozenset(),False,0,0,frozenset())
        artifact=s.Card('artifact','artifact','artifact',event_definition=definition,
                        printed_types=('Artifact',),is_token=True)
        sim.enter_creature(artifact,sim.players[1])
        with self.assertRaisesRegex(ValueError,'legal permanent'):
            sim.cast_spell(0,cards['Swords to Plowshares'],target=artifact.id)
        self.assertIn(cards['Swords to Plowshares'],sim.players[0].hand)
        sim.invariant()
