"""Reusable enchantment-sourced ability copy, full-text grammar, and stack timing."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
import test_enchantment_abilities as fixtures


class EnchantmentCopyChecks(unittest.TestCase):
    setUpClass=classmethod(fixtures.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.EnchantmentChecks.tearDownClass.__func__)
    token=fixtures.EnchantmentChecks.token
    put=fixtures.EnchantmentChecks.put

    def prepare(self):
        raw=dict(self.lookup['Weaver of Harmony'])
        card=s.import_diagnostic_card(self.rules,raw,0,'copier',{'Green'})
        self.assertEqual(card.kind,'creature')
        self.assertEqual(card.event_definition.enchantment_copy_cost,'{G}')
        sim=s.Simulator(self.rules,42,decks=(s.demo_deck(0)+[card],s.demo_deck(1)),
                        diagnostic=True)
        sim.manual_priority=True
        player=sim.players[0]
        (player.hand if card in player.hand else player.library).remove(card)
        player.battlefield.append(s.Permanent(card,tapped=False,fresh=False))
        # Paying green is deliberately separate from the tap cost of Weaver.
        player.mana_pool[4]=2
        sim.phase='main';sim.stack.priority=0
        return sim,card

    def test_full_oracle_composition_and_unfamiliar_name(self):
        raw=dict(self.lookup['Weaver of Harmony'])
        changed=dict(raw,name='Unseen Enchantment Mimic',
                     oracleText=raw['oracleText'].replace(
                         'Other enchantment creatures you control get +1/+1.',
                         'Other enchantment creatures you control get +3/+2.'))
        card=s.import_diagnostic_card(self.rules,changed,0,'mimic',{'Green'})
        self.assertEqual(card.kind,'creature')
        self.assertEqual(card.event_definition.static_effects[0].power,3)
        changed['oracleText']+='\nDraw ten cards whenever unknown.'
        self.assertEqual(s.import_diagnostic_card(self.rules,changed,0,'bad',{'Green'}).kind,
                         'unsupported')

    def test_stack_ability_copied_not_cast_and_targeted_before_paying(self):
        sim,card=self.prepare()
        aura=s.Card('enchantment-source','Enchantment Source','enchantment',
                    event_definition=s.EventDefinition('Enchantment Source',
                        frozenset({'Enchantment'}),frozenset(),False,0,0,frozenset()),
                    is_token=True)
        sim.enter_creature(aura,sim.players[0])
        event=dict(operation='gain_life',effect='gain 3 life',amount=3,
                   recipient='controller',controller=0,source=aura.id,name=aura.name)
        original=sim.stack.push(0,(event,aura),'An enchantment trigger')
        legal=sim.enchantment_copy_choices(0)
        self.assertEqual(len(legal),1)
        self.assertEqual(legal[0].target_stack,original.id)
        old_life=sim.players[0].life
        sim.activate_enchantment_copy(0,card.id,original.id)
        self.assertTrue(next(p for p in sim.players[0].battlefield if p.card.id==card.id).tapped)
        self.assertEqual(len(sim.stack.items),2)
        # Activated copy resolves, creating a second independent stack object.
        sim.pass_priority(0);sim.pass_priority(1)
        self.assertEqual(len(sim.stack.items),2)
        self.assertTrue(any(frame.payload[0].get('copied') for frame in sim.stack.items))
        for _ in range(4):
            sim.pass_priority(0);sim.pass_priority(1)
        self.assertEqual(sim.players[0].life,old_life+6)
        self.assertEqual(sum(e['kind']=='cast' for e in sim.events if
                             e['details'].get('card')=='Enchantment Source'),0)
        sim.invariant()

    def test_ability_copy_target_filter_and_fizzle(self):
        sim,card=self.prepare()
        origin=card
        spell=sim.stack.push(0,({'operation':'spell','controller':0},card),'Spell')
        opposing=sim.stack.push(1,({'operation':'draw_cards','controller':1,
                        'source':card.id,'amount':1},card),'Opposing ability')
        self.assertEqual(sim.enchantment_copy_targets(0),())
        for _ in range(2):sim.stack.items.pop()
        aura=s.Card('e-source','Effect enchantment','enchantment',
                    event_definition=s.EventDefinition('Effect enchantment',
                    frozenset({'Enchantment'}),frozenset(),False,0,0,frozenset()),is_token=True)
        sim.enter_creature(aura,sim.players[0])
        target=sim.stack.push(0,({'operation':'gain_life','controller':0,
              'source':aura.id,'amount':2},aura),'Triggered ability')
        sim.activate_enchantment_copy(0,card.id,target.id)
        # Countered or otherwise removed target must cause a legal fizzle.
        sim.stack.items.remove(target)
        sim.pass_priority(0);sim.pass_priority(1)
        self.assertFalse(sim.stack.items)
        self.assertTrue(any(e['kind']=='ability_copy_fizzle' for e in sim.events))
        sim.invariant()
