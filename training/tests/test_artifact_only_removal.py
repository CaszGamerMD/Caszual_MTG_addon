"""Full-text artifact-only removal incl. nonregeneration instruction."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
import test_enchantment_abilities as f

class ArtifactOnlyRemovalTests(unittest.TestCase):
    setUpClass=classmethod(f.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(f.EnchantmentChecks.tearDownClass.__func__)
    fixture=f.EnchantmentChecks.fixture
    put=f.EnchantmentChecks.put
    drain=f.EnchantmentChecks.drain

    def test_saved_oxidize_and_renamed_variants_and_strict_remainder(self):
        original=dict(self.lookup['Oxidize'],name='Unknown artifact removal')
        card=s.import_diagnostic_card(self.rules,original,0,'destroy',{'Green'})
        self.assertEqual((card.kind,card.removal),('removal_spell','destroy_artifact'))
        for oracle in ('Destroy target artifact.','Destroy target artifact. It can\'t be regenerated.'):
            changed=dict(original,oracleText=oracle)
            self.assertEqual(s.import_diagnostic_card(self.rules,changed,0,'v',set()).removal,'destroy_artifact')
        extra=dict(original,oracleText=original['oracleText']+'\nCreate an illegal additional token.')
        self.assertEqual(s.import_diagnostic_card(self.rules,extra,0,'bad',set()).kind,'unsupported')

    def test_destroy_artifact_and_reject_enchantment_and_creature_target(self):
        sim,cards=self.fixture(['Oxidize','Basilisk Collar','Anthem of Champions'])
        collar=self.put(sim,cards['Basilisk Collar'])
        source=cards['Oxidize']
        self.assertIn(collar.card.id,{p.card.id for _,p in sim.removal_targets(0,source)})
        aura=self.put(sim,cards['Anthem of Champions'])
        self.assertNotIn(aura.card.id,{p.card.id for _,p in sim.removal_targets(0,source)})
        with self.assertRaisesRegex(ValueError,'legal permanent target'):
            sim.cast_spell(0,source,target=aura.card.id)
        sim.cast_spell(0,source,target=collar.card.id);self.drain(sim)
        self.assertFalse(any(p.card.id==collar.card.id for p in sim.players[0].battlefield))
        self.assertIn(collar.card,sim.players[0].graveyard)
        sim.invariant()

    def test_indestructible_artifact_not_destroyed(self):
        sim,cards=self.fixture(['Oxidize','Basilisk Collar'])
        collar=self.put(sim,cards['Basilisk Collar'])
        from dataclasses import replace
        collar.card=replace(collar.card,traits='0;0;indestructible',
            event_definition=replace(collar.card.event_definition,
                                     abilities=frozenset({'indestructible'})))
        sim.cast_spell(0,cards['Oxidize'],target=collar.card.id);self.drain(sim)
        self.assertTrue(any(p.card.id==collar.card.id for p in sim.players[0].battlefield))
        sim.invariant()
