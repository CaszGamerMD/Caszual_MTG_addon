"""Target-free spells reuse the ordered Oracle effect interpreter, fail closed."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s


class StandaloneOracleSequenceChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.rules=s.RulesBridge()

    @classmethod
    def tearDownClass(cls):cls.rules.close()

    def card(self,text,name="Night's Whisper",types=('Sorcery',),cost='{1}{B}'):
        raw=dict(name=name,layout='normal',types=list(types),superTypes=[],subTypes=[],
                 manaCost=cost,oracleText=text,colors=['B'])
        return s.import_diagnostic_card(self.rules,raw,0,'oracle-sequence',{'Black'})

    def fixture(self,card):
        lands=[s.Card('sequence-mana-'+str(i),'Sequence mana','land',mask=63)
               for i in range(5)]
        sim=s.Simulator(self.rules,42,
                        decks=(s.demo_deck(0)+[card]+lands,s.demo_deck(1)),
                        diagnostic=True)
        sim.manual_priority=True;sim.phase='main'
        player=sim.players[0]
        for c in [card]+lands:
            (player.hand if c in player.hand else player.library).remove(c)
        player.hand.append(card)
        player.battlefield.extend(s.Permanent(c) for c in lands)
        return sim

    def drain(self,sim):
        while sim.stack.items:sim.pass_priority(sim.stack.priority)

    def test_real_nights_whisper_and_changed_name_numbers_and_cost(self):
        card=self.card('You draw two cards and lose 2 life.')
        self.assertEqual(card.kind,'sequence_spell')
        self.assertEqual([(step.operation,step.amount) for step in card.sequence_effects],
                         [('draw_cards',2),('lose_life',2)])
        variant=self.card('You draw three cards and lose 4 life.',
                          name='Unfamiliar Whispering Spell',types=('Instant',),cost='{2}{B}')
        self.assertEqual(variant.kind,'sequence_spell')
        self.assertTrue(variant.instant)
        self.assertEqual([(step.operation,step.amount) for step in variant.sequence_effects],
                         [('draw_cards',3),('lose_life',4)])

    def test_casting_uses_stack_and_executes_both_in_order(self):
        card=self.card('You draw two cards and lose 2 life.')
        sim=self.fixture(card)
        player=sim.players[0];other=sim.players[1]
        original_library=len(player.library);original_hand=len(player.hand)
        sim.cast_spell(0,card)
        self.assertEqual(len(player.library),original_library)
        self.assertEqual(player.life,40)
        self.assertEqual(len(player.hand),original_hand-1)
        self.assertNotIn(card,player.graveyard)
        self.drain(sim)
        self.assertEqual(len(player.library),original_library-2)
        self.assertEqual(len(player.hand),original_hand+1)
        self.assertEqual((player.life,other.life),(38,40))
        self.assertEqual(player.graveyard.count(card),1)
        drawn=next(i for i,entry in enumerate(sim.events)
                   if entry['kind']=='draw_trigger' and entry['details'].get('source')==card.id)
        lost=next(i for i,entry in enumerate(sim.events)
                  if entry['details'].get('operation')=='lose_life'
                  and entry['details'].get('source')==card.id)
        self.assertLess(drawn,lost)
        sim.invariant()

    def test_shared_subject_in_multiple_coordinated_effects(self):
        card=self.card('You gain 3 life and draw two cards and lose 1 life.',
                       name='Unseen life exchange')
        self.assertEqual(card.kind,'sequence_spell')
        self.assertEqual([step.operation for step in card.sequence_effects],
                         ['gain_life','draw_cards','lose_life'])
        sim=self.fixture(card)
        before=len(sim.players[0].library)
        sim.cast_spell(0,card);self.drain(sim)
        self.assertEqual(sim.players[0].life,42)
        self.assertEqual(len(sim.players[0].library),before-2)
        sim.invariant()

    def test_unknown_remainder_targets_choices_and_nonspells_reject(self):
        for text in ('You draw two cards and lose 2 life. Gain 4 life.',
                     'You draw two cards and lose 2 life.\nChoose a player.',
                     'You draw two cards and target player loses 2 life.',
                     'You draw two cards and exile target creature.',
                     'You draw two cards and win the game.',
                     'You draw two cards and lose 2 life unless you pay {1}.'):
            with self.subTest(text=text):
                self.assertEqual(self.card(text).kind,'unsupported')
        self.assertEqual(self.card('You draw two cards and lose 2 life.',
                         types=('Creature',)).kind,'unsupported')


if __name__=='__main__':unittest.main()
