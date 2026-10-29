"""Attack-only continuous effects exclude a subtype and vanish outside combat."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
import test_enchantment_abilities as h
class AttackingAnthemTests(unittest.TestCase):
    setUpClass=classmethod(h.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(h.EnchantmentChecks.tearDownClass.__func__)
    fixture=h.EnchantmentChecks.fixture
    put=h.EnchantmentChecks.put
    token=h.EnchantmentChecks.token
    def test_unseen_amounts_and_unknown_remainder(self):
        raw=dict(self.lookup['Ferocity of the Wilds'],name='Unseen battle anthem')
        card=s.import_diagnostic_card(self.rules,raw,0,'new',set())
        self.assertEqual(card.kind,'enchantment')
        self.assertTrue(all(e.subject.attacking for e in card.event_definition.static_effects))
        raw['oracleText']='Attacking non-Elf creatures you control get +2/+1 and have lifelink and trample.'
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'variant',set()).kind,'enchantment')
        raw['oracleText']+='\nUnknown bonus.'
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'bad',set()).kind,'unsupported')
    def test_live_attack_only_and_nonhuman_filter(self):
        sim,cards=self.fixture(['Ferocity of the Wilds'])
        banner=self.put(sim,cards['Ferocity of the Wilds'])
        goblin=self.token(sim,'goblin',subtypes=('Goblin',))
        human=self.token(sim,'human',subtypes=('Human',))
        reserve=self.token(sim,'reserve',subtypes=('Goblin',))
        enemy=self.token(sim,'enemy',seat=1,subtypes=('Goblin',))
        for item in sim.players[0].battlefield:item.fresh=False
        self.assertEqual(sim.effective_card(goblin).power,2)
        sim.phase='attack';sim.stack.priority=sim.active
        sim.declare_attackers([goblin.card.id,human.card.id])
        self.assertEqual(sim.effective_card(goblin).power,3)
        self.assertIn('trample',sim.effective_card(goblin).traits)
        for item in (human,reserve,enemy):
            self.assertEqual(sim.effective_card(item).power,2)
        sim.send_to_destination(sim.players[0],banner)
        self.assertEqual(sim.effective_card(goblin).power,2)
        sim.invariant()
