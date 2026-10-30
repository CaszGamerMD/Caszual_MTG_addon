"""Reusable three-level Class: paid progression, taxation, anthem, attack stack trigger."""
import sys,unittest
from pathlib import Path
from dataclasses import replace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
import test_enchantment_abilities as fixtures


class ClassLanguageChecks(unittest.TestCase):
    setUpClass=classmethod(fixtures.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.EnchantmentChecks.tearDownClass.__func__)
    token=fixtures.EnchantmentChecks.token
    drain=fixtures.EnchantmentChecks.drain

    def prepare(self):
        raw=self.lookup['Paladin Class']
        card=s.import_diagnostic_card(self.rules,raw,0,'paladin',{'White'})
        self.assertEqual(card.kind,'enchantment')
        sim=s.Simulator(self.rules,42,decks=(s.demo_deck(0)+[card],s.demo_deck(1)),diagnostic=True)
        sim.manual_priority=True
        player=sim.players[0]
        (player.hand if card in player.hand else player.library).remove(card)
        sim.enter_creature(card,player)
        sim.phase='main';sim.active=0;sim.stack.priority=0
        player.mana_pool[0]=20
        return sim,card

    def test_real_and_unseen_classes_require_all_five_instructions(self):
        raw=dict(self.lookup['Paladin Class'],name='Unseen Knight Academy',
                 oracleText=self.lookup['Paladin Class']['oracleText'].replace(
                    'cost {1} more','cost {2} more').replace(
                    'Creatures you control get +1/+1','Creatures you control get +2/+3'))
        imported=s.import_diagnostic_card(self.rules,raw,0,'unseen',{'White'})
        self.assertEqual(imported.kind,'enchantment')
        self.assertEqual(imported.event_definition.class_program[0],2)
        self.assertEqual(imported.event_definition.class_program[2:4],(2,3))
        raw['oracleText']+='\\nWhen you win, create gold.'
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'invalid',{'White'}).kind,'unsupported')

    def test_level_abilities_use_stack_and_dynamic_creature_anthem(self):
        sim,card=self.prepare()
        host=self.token(sim,'host')
        self.assertEqual(sim.effective_card(host).power,1)
        source=next(p for p in sim.players[0].battlefield if p.card.id==card.id)
        self.assertEqual(source.class_level,1)
        choice=next(c for c in sim.legal(0) if c.kind=='activate_class_level')
        sim.activate_class_level(0,choice.card_id)
        self.assertEqual(source.class_level,1)
        sim.pass_priority(0);sim.pass_priority(1)
        self.assertEqual(source.class_level,2)
        self.assertEqual(sim.effective_card(host).power,2)
        self.assertEqual(len(sim.class_level_choices(0)),1)
        sim.activate_class_level(0,card.id)
        sim.pass_priority(0);sim.pass_priority(1)
        self.assertEqual(source.class_level,3)
        self.assertEqual(sim.class_level_choices(0),[])
        sim.invariant()

    def test_tax_is_only_for_opponent_spells_on_class_owners_turn(self):
        sim,card=self.prepare()
        opponent=s.Card('instant','Example instant','spell','{W}',instant=True)
        sim.players[1].mana_pool[0]=1
        self.assertFalse(sim.payment(opponent,seat=1)['paid'])
        self.assertTrue(sim.payment(opponent,seat=1,spell_cost=False)['paid'])
        sim.active=1
        self.assertTrue(sim.payment(opponent,seat=1)['paid'])
        sim.active=0
        source=next(p for p in sim.players[0].battlefield if p.card.id==card.id)
        sim.send_to_destination(sim.players[0],source)
        self.assertTrue(sim.payment(opponent,seat=1)['paid'])
        sim.invariant()

    def test_level_three_attack_targets_one_attacker_and_grants_temporary_double_strike(self):
        sim,card=self.prepare()
        source=next(p for p in sim.players[0].battlefield if p.card.id==card.id)
        source.class_level=3
        first=self.token(sim,'first');second=self.token(sim,'second')
        first.fresh=False;second.fresh=False
        sim.phase='attack'
        sim.declare_attackers([first.card.id,second.card.id])
        effects=[frame.payload[0] for frame in sim.stack.items
                 if frame.payload[0].get('operation')=='class_attack_boost']
        self.assertEqual(len(effects),1)
        event=effects[0];target=event['target']
        before=sim.effective_card(next(p for p in sim.players[0].battlefield if p.card.id==target)).power
        self.drain(sim)
        empowered=next(p for p in sim.players[0].battlefield if p.card.id==target)
        self.assertEqual(sim.effective_card(empowered).power,before+1)
        self.assertIn('double strike',sim.effective_card(empowered).traits)
        sim.invariant()
