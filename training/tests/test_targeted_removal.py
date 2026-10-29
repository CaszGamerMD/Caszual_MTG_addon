"""General 'Destroy target artifact or enchantment' spell resolution."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
import test_enchantment_abilities as fixtures

class ArtifactEnchantmentRemovalChecks(unittest.TestCase):
    setUpClass=classmethod(fixtures.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.EnchantmentChecks.tearDownClass.__func__)
    fixture=fixtures.EnchantmentChecks.fixture
    drain=fixtures.EnchantmentChecks.drain

    def permanent(self,sim,identifier,types,seat=1,abilities=()):
        definition=s.EventDefinition(identifier,frozenset(types),frozenset(),
                     False,2 if 'Creature' in types else 0,
                     2 if 'Creature' in types else 0,frozenset(abilities))
        card=s.Card(identifier,identifier,
                    'creature' if 'Creature' in types else
                    'artifact' if 'Artifact' in types else 'enchantment',
                    mana_cost='{0}',event_definition=definition,is_token=True,
                    printed_types=tuple(types),power=definition.power,
                    toughness=definition.toughness)
        sim.enter_creature(card,sim.players[seat])
        return sim.players[seat].battlefield[-1]

    def test_real_oracle_and_renamed_spell_are_playable_fail_closed(self):
        for name in ('Naturalize',"Nature's Chant"):
            raw=dict(self.lookup[name],name='Unfamiliar destruction')
            card=s.import_diagnostic_card(self.rules,raw,0,'unknown',{'Green','White'})
            self.assertEqual(card.kind,'removal_spell',name)
            self.assertEqual(card.removal,'destroy_artifact_enchantment')
            raw['oracleText']+='\nDraw a mysterious extra card.'
            self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'bad',set()).kind,'unsupported')

    def test_artifact_target_stays_until_spell_resolves(self):
        sim,cards=self.fixture(['Naturalize'])
        target=self.permanent(sim,'target-artifact',('Artifact',))
        spell=cards['Naturalize']
        sim.cast_spell(0,spell,target=target.card.id)
        self.assertIn(target,sim.players[1].battlefield)
        self.assertEqual(len(sim.stack.items),1)
        self.drain(sim)
        self.assertNotIn(target,sim.players[1].battlefield)
        self.assertIn(spell,sim.players[0].graveyard)
        sim.invariant()

    def test_enchantment_and_artifact_creature_are_legal_targets(self):
        for types in (('Enchantment',),('Creature','Artifact')):
            sim,cards=self.fixture(['Naturalize'])
            target=self.permanent(sim,'target',types)
            sim.cast_spell(0,cards['Naturalize'],target=target.card.id)
            self.drain(sim)
            self.assertNotIn(target,sim.players[1].battlefield)
            sim.invariant()

    def test_plain_creatures_are_not_legal_targets(self):
        sim,cards=self.fixture(['Naturalize'])
        target=self.permanent(sim,'plain-creature',('Creature',))
        with self.assertRaisesRegex(ValueError,'legal permanent'):
            sim.cast_spell(0,cards['Naturalize'],target=target.card.id)
        self.assertIn(cards['Naturalize'],sim.players[0].hand)
        self.assertIn(target,sim.players[1].battlefield)
        sim.invariant()

    def test_indestructible_target_remains_after_resolution(self):
        sim,cards=self.fixture(['Naturalize'])
        target=self.permanent(sim,'indestructible-artifact',('Artifact',),abilities=('indestructible',))
        sim.cast_spell(0,cards['Naturalize'],target=target.card.id)
        self.drain(sim)
        self.assertIn(target,sim.players[1].battlefield)
        sim.invariant()

    def test_hexproof_opposing_permanent_disallows_cast_but_own_remains_legal(self):
        sim,cards=self.fixture(['Naturalize'])
        target=self.permanent(sim,'hexproof-artifact',('Artifact',),abilities=('hexproof',))
        with self.assertRaisesRegex(ValueError,'legal permanent'):
            sim.cast_spell(0,cards['Naturalize'],target=target.card.id)
        ally=self.permanent(sim,'own-hexproof',('Artifact',),seat=0,abilities=('hexproof',))
        sim.cast_spell(0,cards['Naturalize'],target=ally.card.id)
        self.drain(sim)
        self.assertNotIn(ally,sim.players[0].battlefield)
        sim.invariant()

    def test_target_disappears_before_resolution_spell_fizzles(self):
        sim,cards=self.fixture(['Naturalize'])
        target=self.permanent(sim,'target-artifact',('Artifact',))
        other=self.permanent(sim,'other-artifact',('Artifact',))
        sim.cast_spell(0,cards['Naturalize'],target=target.card.id)
        sim.send_to_destination(sim.players[1],target)
        self.drain(sim)
        self.assertIn(other,sim.players[1].battlefield)
        sim.invariant()

    def test_hybrid_natures_chant_pays_and_destroys_enchantment(self):
        sim,cards=self.fixture(["Nature's Chant"])
        target=self.permanent(sim,'enchantment',('Enchantment',))
        sim.cast_spell(0,cards["Nature's Chant"],target=target.card.id)
        self.drain(sim)
        self.assertNotIn(target,sim.players[1].battlefield)
        sim.invariant()
