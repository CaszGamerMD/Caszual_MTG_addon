"""Variable-X permanent search and verified spell self-shuffle instructions."""
import json
import sys
import unittest
from pathlib import Path

HERE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HERE))
import simulator as s
from library_search_spells import compile_card

DECK=json.loads((HERE/'decks/14435337-lupitas-elves.json').read_text())
ZENITH=next(c for c in DECK['mainboard'] if c['name']=="Green Sun's Zenith")


class VariableLibrarySearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.rules=s.RulesBridge()

    @classmethod
    def tearDownClass(cls):cls.rules.close()

    def spell(self,raw=None):
        return s.import_diagnostic_card(self.rules,raw or ZENITH,0,'zenith',{'Green'})

    @staticmethod
    def creature(uid,mana_value,color='Green'):
        definition=s.EventDefinition(uid,frozenset({'Creature'}),frozenset({'Elf'}),
            False,2,2,frozenset(),colors=frozenset({color}))
        return s.Card(uid,uid,'creature',traits='2;2;',power=2,toughness=2,
            printed_types=('Creature',),printed_mana_value=mana_value,
            colors=(color,),event_definition=definition)

    def fixture(self,spell=None):
        spell=spell or self.spell()
        mana=[s.Card('x-mana-'+str(i),'Mana','land',mask=63) for i in range(7)]
        small=self.creature('x-cheap',2)
        expensive=self.creature('x-expensive',5)
        wrong=self.creature('x-black',1,'Black')
        sim=s.Simulator(self.rules,499,
            decks=(s.demo_deck(0)+[spell,small,expensive,wrong]+mana,s.demo_deck(1)),
            diagnostic=True)
        self.assertFalse(sim.finished,sim.questions)
        sim.manual_priority=True;sim.phase='main'
        p=sim.players[0]
        for c in [spell,small,expensive,wrong]+mana:
            (p.hand if c in p.hand else p.library).remove(c)
        p.hand.append(spell)
        p.library.extend((small,expensive,wrong))
        p.battlefield.extend(s.Permanent(c) for c in mana)
        return sim,p,spell,small,expensive,wrong

    @staticmethod
    def drain(sim):
        while sim.stack.items:sim.pass_priority(sim.stack.priority)

    def test_saved_zenith_and_unseen_self_name_use_same_compiler(self):
        real=self.spell()
        self.assertEqual(real.kind,'library_search_spell')
        program=real.library_search_program
        self.assertTrue(program.mana_value_limit_x)
        self.assertTrue(program.shuffle_self)
        self.assertEqual(program.steps,('search','put_battlefield','shuffle','shuffle_self'))
        raw=dict(ZENITH,name='Unknown Emerald Search',oracleText=ZENITH['oracleText'].replace(
            "Green Sun's Zenith",'Unknown Emerald Search'))
        self.assertEqual(self.spell(raw).kind,'library_search_spell')
        self.assertEqual(self.spell(dict(raw,name='Mismatched name')).kind,'unsupported')
        self.assertEqual(self.spell(dict(raw,oracleText=raw['oracleText']+' Draw a card.')).kind,'unsupported')
        self.assertIsNone(compile_card(ZENITH['oracleText'],['Sorcery']))

    def test_x_limit_is_paid_and_applied_to_mana_value_at_resolution(self):
        sim,p,spell,small,expensive,wrong=self.fixture()
        before=len(p.library)
        sim.cast_spell(0,spell,x=2)
        self.assertEqual(len(sim.stack.items),1)
        self.assertNotIn(small,[item.card for item in p.battlefield])
        self.drain(sim)
        self.assertIn(small,[item.card for item in p.battlefield])
        self.assertIn(expensive,p.library)
        self.assertIn(wrong,p.library)
        self.assertIn(spell,p.library)
        self.assertNotIn(spell,p.graveyard)
        # One creature left the library, then the spell shuffled itself in.
        self.assertEqual(len(p.library),before)
        self.assertEqual(sum(e['kind']=='library_shuffle' for e in sim.events),1)
        self.assertEqual(sum(e['kind']=='search_shuffle_self' for e in sim.events),1)
        sim.invariant()

    def test_zero_x_no_match_still_shuffles_spell_into_owner_library(self):
        sim,p,spell,small,_,_=self.fixture()
        before=len(p.library)
        sim.cast_spell(0,spell,x=0);self.drain(sim)
        self.assertIn(small,p.library)
        self.assertIn(spell,p.library)
        self.assertEqual(len(p.library),before+1)
        self.assertFalse(any(e['kind']=='search_put_battlefield' for e in sim.events))
        sim.invariant()

    def test_missing_invalid_x_rejected_before_payment_or_card_move(self):
        sim,p,spell,_,_,_=self.fixture()
        for invalid in (None,-1,1.5,1001):
            with self.subTest(invalid=invalid):
                with self.assertRaisesRegex(ValueError,'valid declared X'):
                    sim.cast_spell(0,spell,x=invalid)
                self.assertIn(spell,p.hand)
                self.assertFalse(sim.stack.items)
                self.assertTrue(all(not land.tapped for land in p.battlefield))
        sim.invariant()

    def test_x_choices_are_affordable_and_include_zero(self):
        sim,p,spell,_,_,_=self.fixture()
        choices=sim.library_search_x_choices(0,spell,'cast')
        amounts=[choice.x_value for choice in choices]
        self.assertIn(0,amounts)
        self.assertIn(4,amounts)
        self.assertTrue(all(choice.card_id==spell.id for choice in choices))
        sim.invariant()


if __name__=='__main__':unittest.main()
