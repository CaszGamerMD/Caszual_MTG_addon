"""Linked Aura exile uses real zone changes, target legality and source identity."""
import unittest
import test_enchantment_abilities as fixtures
import simulator as s
from dataclasses import replace

class LandAuraExileChecks(unittest.TestCase):
    setUpClass=classmethod(fixtures.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.EnchantmentChecks.tearDownClass.__func__)
    fixture=fixtures.EnchantmentChecks.fixture
    put=fixtures.EnchantmentChecks.put
    drain=fixtures.EnchantmentChecks.drain

    def prepare(self,name):
        sim,cards=self.fixture(['Lifelink'])
        raw=self.lookup[name]
        aura=s.import_diagnostic_card(self.rules,raw,0,'exile-aura',{'White'})
        self.assertEqual(aura.kind,'aura')
        sim.players[0].hand.remove(cards['Lifelink'])
        sim.players[0].hand.append(aura)
        land=next(item for item in sim.players[0].battlefield if item.card.kind=='land')
        land.card=replace(land.card,land_subtypes=('Mountain',) if name=='Chained to the Rocks' else ('Plains',),
                          snow=name=='On Thin Ice')
        target=next(c for c in sim.players[1].library if c.kind=='creature')
        sim.players[1].library.remove(target)
        sim.enter_creature(target,sim.players[1])
        return sim,aura,land,target

    def test_real_and_renamed_auras_reject_extra_clauses(self):
        for name in ('On Thin Ice','Chained to the Rocks'):
            raw=dict(self.lookup[name],name='Unseen frost chain')
            card=s.import_diagnostic_card(self.rules,raw,0,'x',{'White'})
            self.assertEqual(card.kind,'aura')
            self.assertTrue(card.event_definition.aura_exile)
            raw['oracleText']+='\nDraw a mystery card.'
            self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'bad',{'White'}).kind,'unsupported')

    def test_exile_waits_for_trigger_then_returns_to_owner(self):
        for name in ('On Thin Ice','Chained to the Rocks'):
            with self.subTest(name=name):
                sim,aura,land,target=self.prepare(name)
                attached=self.put(sim,aura,land.card.id)
                self.assertIn(target.id,{p.card.id for p in sim.players[1].battlefield})
                self.assertEqual(len(sim.stack.items),1)
                self.drain(sim)
                self.assertNotIn(target.id,{p.card.id for p in sim.players[1].battlefield})
                self.assertIn(target.id,{c.id for c in sim.players[1].exile})
                sim.send_to_destination(sim.players[0],attached)
                self.assertIn(target.id,{p.card.id for p in sim.players[1].battlefield})
                self.assertNotIn(target.id,{c.id for c in sim.players[1].exile})
                sim.invariant()

    def test_departure_before_trigger_or_illegal_target_prevents_exile(self):
        sim,aura,land,target=self.prepare('On Thin Ice')
        attached=self.put(sim,aura,land.card.id)
        sim.send_to_destination(sim.players[0],attached)
        self.drain(sim)
        self.assertIn(target.id,{p.card.id for p in sim.players[1].battlefield})
        self.assertNotIn(target.id,{c.id for c in sim.players[1].exile})
        sim.invariant()
        sim,aura,land,target=self.prepare('On Thin Ice')
        self.put(sim,aura,land.card.id)
        enemy=next(p for p in sim.players[1].battlefield if p.card.id==target.id)
        enemy.temporary_abilities=frozenset({'hexproof'})
        self.drain(sim)
        self.assertIn(target.id,{p.card.id for p in sim.players[1].battlefield})
        sim.invariant()
