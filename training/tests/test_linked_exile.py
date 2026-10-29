"""Separate linked exile/return triggers are not an Aura-style 'until' effect."""
import unittest
import test_enchantment_abilities as fixtures
import simulator as s

class LinkedExileChecks(unittest.TestCase):
    setUpClass=classmethod(fixtures.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.EnchantmentChecks.tearDownClass.__func__)
    fixture=fixtures.EnchantmentChecks.fixture
    put=fixtures.EnchantmentChecks.put
    drain=fixtures.EnchantmentChecks.drain

    def prepare(self, text=None):
        sim,cards=self.fixture(['Lifelink'])
        raw=dict(self.lookup['Journey to Nowhere'])
        if text is not None:raw['oracleText']=text
        card=s.import_diagnostic_card(self.rules,raw,0,'linked',{'White'})
        sim.players[0].hand.remove(cards['Lifelink'])
        sim.players[0].hand.append(card)
        target=next(c for c in sim.players[1].library if c.kind=='creature')
        sim.players[1].library.remove(target)
        sim.enter_creature(target,sim.players[1])
        return sim,card,target

    def test_complete_oracle_unseen_name_and_unknown_text_rejected(self):
        raw=dict(self.lookup['Journey to Nowhere'],name='Unnamed holding cell')
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'a',{'White'}).kind,'enchantment')
        raw['oracleText']+='\nCreate an unknown effect.'
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'b',{'White'}).kind,'unsupported')
        raw['oracleText']=raw['oracleText'].replace('target creature.','target creature an opponent controls.').replace('\nCreate an unknown effect.','')
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'c',{'White'}).kind,'enchantment')

    def test_exile_on_stack_and_return_on_separate_leave_trigger(self):
        sim,card,target=self.prepare()
        source=self.put(sim,card)
        self.assertIn(target.id,{p.card.id for p in sim.players[1].battlefield})
        self.drain(sim)
        self.assertIn(target.id,{c.id for c in sim.players[1].exile})
        sim.send_to_destination(sim.players[0],source)
        self.assertIn(target.id,{c.id for c in sim.players[1].exile})
        sim.resolve_entry_triggers([],card)
        self.drain(sim)
        self.assertIn(target.id,{p.card.id for p in sim.players[1].battlefield})
        sim.invariant()

    def test_leave_before_entry_resolves_does_not_prevent_permanent_exile(self):
        sim,card,target=self.prepare()
        source=self.put(sim,card)
        sim.send_to_destination(sim.players[0],source)
        sim.resolve_entry_triggers([],card)
        self.drain(sim)
        self.assertIn(target.id,{c.id for c in sim.players[1].exile})
        self.assertNotIn(target.id,{p.card.id for p in sim.players[1].battlefield})
        sim.invariant()

    def test_illegal_target_on_resolution_fizzles(self):
        sim,card,target=self.prepare()
        self.put(sim,card)
        permanent=next(p for p in sim.players[1].battlefield if p.card.id==target.id)
        permanent.temporary_abilities=frozenset({'hexproof'})
        self.drain(sim)
        self.assertIn(target.id,{p.card.id for p in sim.players[1].battlefield})
        sim.invariant()
