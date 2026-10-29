"""Full-stack regression for a generic group-attack draw trigger."""
import unittest
import test_enchantment_abilities as fixtures
import simulator as s

class SessionLearningAttackDraw(unittest.TestCase):
    setUpClass=classmethod(fixtures.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.EnchantmentChecks.tearDownClass.__func__)
    fixture=fixtures.EnchantmentChecks.fixture
    put=fixtures.EnchantmentChecks.put
    token=fixtures.EnchantmentChecks.token
    ready=fixtures.EnchantmentChecks.ready
    drain=fixtures.EnchantmentChecks.drain

    def raw(self,name,oracle):
        return dict(name=name,oracleText=oracle,types=['Enchantment'],subTypes=[],
                    superTypes=[],colors=['White'],colorIdentity=['White'],
                    manaCost='{1}{W}',quantity=1,layout='normal')

    def prepare(self,name,text):
        self.lookup[name]=self.raw(name,text)
        sim,cards=self.fixture([name])
        source=self.put(sim,cards[name])
        return sim,source

    def test_unseen_name_parameterized_threshold_and_reject_extra_clause(self):
        text='Whenever you attack with three or more creatures, draw two cards.'
        card=s.import_diagnostic_card(self.rules,self.raw('Unknown alliance',text),0,'u',{'White'})
        self.assertNotEqual(card.kind,'unsupported')
        self.assertEqual(card.event_definition.attack_group_draw,(3,2))
        self.assertEqual(s.import_diagnostic_card(self.rules,
            self.raw('Unknown alliance',text+'\nCreate an unknown thing.'),0,'bad',{'White'}).kind,'unsupported')

    def test_two_attackers_draw_only_after_trigger_resolves(self):
        sim,source=self.prepare('Unseen battle chronicler',
            'Whenever you attack with two or more creatures, draw a card.')
        a=self.token(sim,'first');b=self.token(sim,'second')
        self.ready(sim)
        before=len(sim.players[0].hand)
        sim.declare_attackers([a.card.id,b.card.id])
        self.assertEqual(len(sim.players[0].hand),before)
        self.assertEqual(len(sim.stack.items),1)
        sim.send_to_destination(sim.players[0],source)
        self.drain(sim)
        self.assertEqual(len(sim.players[0].hand),before+1)
        sim.invariant()

    def test_one_attacker_does_not_trigger(self):
        sim,_=self.prepare('Unknown one attacker observer',
            'Whenever you attack with two or more creatures, draw a card.')
        a=self.token(sim,'only')
        self.ready(sim)
        sim.declare_attackers([a.card.id])
        self.assertFalse(any(item.payload[0].get('operation')=='draw_cards' for item in sim.stack.items))
        sim.invariant()
