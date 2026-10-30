"""Resolution-time subtype counts with half-rounded-down token creation."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
import test_enchantment_abilities as f

class ScaledUpkeepTokenCycle(unittest.TestCase):
    setUpClass=classmethod(f.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(f.EnchantmentChecks.tearDownClass.__func__)
    fixture=f.EnchantmentChecks.fixture
    put=f.EnchantmentChecks.put
    token=f.EnchantmentChecks.token
    drain=f.EnchantmentChecks.drain

    def upkeep(self,sim):
        sim.phase='untap';sim.stack.active=sim.active;sim.stack.priority=sim.active;sim.step()

    def zombies(self,sim):
        return [p for p in sim.players[0].battlefield if p.card.is_token and p.card.name=='Zombie']

    def test_real_unseen_name_different_stats_subtype_and_unknown_clause(self):
        raw=dict(self.lookup['Endless Ranks of the Dead'],name='Unknown tribal army')
        card=s.import_diagnostic_card(self.rules,raw,0,'new',{'Black'})
        self.assertEqual(card.kind,'enchantment')
        self.assertEqual(card.event_definition.upkeep_token_rule[2:4],('Zombie',2))
        raw['oracleText']=raw['oracleText'].replace('2/2 black Zombie','3/4 green Goblin').replace('Zombies you control','Goblins you control')
        card=s.import_diagnostic_card(self.rules,raw,0,'newer',{'Green'})
        self.assertEqual(card.event_definition.upkeep_token_rule[2],'Goblin')
        self.assertEqual((card.event_definition.upkeep_token_rule[-1].power,card.event_definition.upkeep_token_rule[-1].toughness),(3,4))
        raw['oracleText']+='\nEach player draws a secret mystery.'
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'bad',set()).kind,'unsupported')

    def test_no_trigger_on_opponent_upkeep_and_zero_tokens_for_one(self):
        sim,cards=self.fixture(['Endless Ranks of the Dead'])
        self.put(sim,cards['Endless Ranks of the Dead'])
        self.token(sim,'one',subtypes=('Zombie',))
        sim.active=1;self.upkeep(sim)
        self.assertFalse(sim.stack.items)
        sim.active=0;self.upkeep(sim)
        self.assertEqual(len(sim.stack.items),1)
        self.drain(sim)
        self.assertEqual(len(self.zombies(sim)),0)
        sim.invariant()

    def test_count_at_resolution_and_token_doubler(self):
        sim,cards=self.fixture(['Endless Ranks of the Dead','Parallel Lives'])
        source=self.put(sim,cards['Endless Ranks of the Dead'])
        self.put(sim,cards['Parallel Lives'])
        for i in range(3):self.token(sim,'z'+str(i),subtypes=('Zombie',))
        self.token(sim,'not-zombie',subtypes=('Goblin',))
        self.token(sim,'enemy-zombie',seat=1,subtypes=('Zombie',))
        self.upkeep(sim)
        self.assertEqual(len(sim.stack.items),1)
        self.token(sim,'z4',subtypes=('Zombie',))
        self.drain(sim)
        self.assertEqual(len(self.zombies(sim)),4)  # floor(4/2)=2, doubled
        self.assertTrue(all((p.card.power,p.card.toughness)==(2,2) for p in self.zombies(sim)))
        sim.invariant()

    def test_trigger_persists_if_enchantment_leaves_before_resolution(self):
        sim,cards=self.fixture(['Endless Ranks of the Dead'])
        source=self.put(sim,cards['Endless Ranks of the Dead'])
        for i in range(4):self.token(sim,'z'+str(i),subtypes=('Zombie',))
        self.upkeep(sim)
        sim.send_to_destination(sim.players[0],source)
        self.drain(sim)
        self.assertEqual(len(self.zombies(sim)),2)
        sim.invariant()
