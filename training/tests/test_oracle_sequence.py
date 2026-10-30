"""General ordered instructions: parse => trigger => stack => execute, fail closed."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
from oracle_abilities import compile_abilities,effect
from oracle_sequence import parse_sequence


def new_card(text, name="Unknown green apprentice"):
    return dict(name=name,manaCost='{1}{G}',types=['Creature'],
                superTypes=[],subTypes=['Elf','Druid'],
                colors=['Green'],colorIdentity=['Green'],
                oracleText=text,power='2',toughness='2',layout='normal',faces=[],
                quantity=1)


class OracleSequenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rules=s.RulesBridge()

    @classmethod
    def tearDownClass(cls):
        cls.rules.close()

    def test_effect_is_ordered_and_keeps_full_token_payload(self):
        text=('create a 1/1 green Elf Warrior creature token, '
              'then draw a card.')
        e=effect(text)
        self.assertEqual(e.operation,'ordered_effects')
        self.assertEqual([p.operation for p in e.steps],
                         ['create_tokens','draw_cards'])
        self.assertEqual(e.steps[0].token.subtypes,('Elf','Warrior'))
        self.assertEqual(e.steps[0].token.colors,('Green',))

    def test_legacy_and_new_compositions_share_same_kernel(self):
        for body,expected in [
            ('you gain 2 life and draw a card.',('gain_life','draw_cards')),
            ('draw two cards, then gain 3 life.',('draw_cards','gain_life')),
            ('put a +1/+1 counter on this creature, then draw a card.',
             ('self_counter','draw_cards')),
            ('create a 1/1 green Elf creature token and draw a card.',
             ('create_tokens','draw_cards')),
        ]:
            with self.subTest(body=body):
                action=effect(body)
                self.assertIsNotNone(action)
                self.assertEqual(tuple(p.operation for p in action.steps),expected)

    def test_unknown_extra_clauses_reject_entire_ability(self):
        for text in (
            'draw a card, then teleport a creature.',
            'create a 1/1 green Elf creature token and rewrite the rules.',
            'draw a card, then destroy target creature.',
            'draw a card, then',
            'draw a card and then draw a second card.',
        ):
            # Do not accept unsupported/ambiguous grammar and silently skip it.
            self.assertIsNone(effect(text),text)
        bad=new_card('When this creature enters, create a 1/1 green Elf creature token, then teleport another permanent.')
        self.assertEqual(s.import_diagnostic_card(self.rules,bad,0,'bad',{'Green'}).kind,
                         'unsupported')

    def test_self_entry_sequence_enters_stack_and_resolves_in_order(self):
        raw=new_card('When this creature enters, create a 1/1 green Elf Warrior creature token, then draw a card.')
        card=s.import_diagnostic_card(self.rules,raw,0,'new-elf',{'Green'})
        self.assertEqual(card.kind,'creature')
        self.assertEqual(len(card.event_definition.triggers),1)
        s0=s.Simulator(self.rules,42,decks=(s.demo_deck(0)+[card],s.demo_deck(1)),
                       diagnostic=True)
        s0.manual_priority=True
        s0.phase='main'
        owner=s0.players[0]
        (owner.hand if card in owner.hand else owner.library).remove(card)
        owner.hand.append(card)
        before=len(owner.hand)
        owner.hand.remove(card)
        triggers=s0.enter_creature(card,owner)
        s0.resolve_entry_triggers(triggers,card)
        self.assertGreater(len(s0.stack.items),0)
        self.assertEqual(len([x for x in owner.battlefield if x.card.is_token]),0)
        while s0.stack.items:
            s0.pass_priority(s0.stack.priority)
        self.assertEqual(len([x for x in owner.battlefield if x.card.is_token]),1)
        self.assertEqual(len(owner.hand),before)  # cast consumes 1 then draws 1
        token=next(x for x in owner.battlefield if x.card.is_token)
        self.assertEqual(token.card.event_definition.subtypes,frozenset(('Elf','Warrior')))
        s0.invariant()

    def test_nonself_token_multiplication_is_not_silently_accepted(self):
        text=('Whenever another Elf you control enters, create a 1/1 green Elf creature token, '
              'then draw a card.')
        self.assertIsNone(compile_abilities(text))
        self.assertEqual(s.import_diagnostic_card(self.rules,new_card(text),0,'loop',{'Green'}).kind,
                         'unsupported')


if __name__=='__main__':
    unittest.main()
