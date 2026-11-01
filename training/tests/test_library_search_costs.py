"""Composed additional sacrifice costs and battlefield library searches."""
import json
import sys
import unittest
from pathlib import Path

HERE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HERE))
import simulator as s
from library_search_spells import compile_card

DECK=json.loads((HERE/'decks/14435337-lupitas-elves.json').read_text())
NATURAL=next(c for c in DECK['mainboard'] if c['name']=='Natural Order')


class AdditionalSearchCostTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.rules=s.RulesBridge()

    @classmethod
    def tearDownClass(cls):cls.rules.close()

    def spell(self,oracle=None,name='Unknown creature offering'):
        raw=dict(NATURAL,name=name,oracleText=oracle or NATURAL['oracleText'])
        return s.import_diagnostic_card(self.rules,raw,0,'search-offering',{'Green'})

    @staticmethod
    def creature(identifier,color='Green'):
        definition=s.EventDefinition(identifier,frozenset({'Creature'}),frozenset({'Elf'}),
                                     False,2,2,frozenset(),colors=frozenset({color}))
        return s.Card(identifier,identifier,'creature',power=2,toughness=2,
                      traits='2;2;',colors=(color,),printed_types=('Creature',),
                      event_definition=definition)

    def fixture(self,spell=None):
        spell=spell or self.spell()
        mana=[s.Card('cost-mana-'+str(i),'Mana','land',mask=63) for i in range(6)]
        victim=self.creature('cost-green-victim')
        library_creature=self.creature('cost-green-search-result')
        decoy=self.creature('cost-black-decoy','Black')
        sim=s.Simulator(self.rules,419,
            decks=(s.demo_deck(0)+[spell,victim,library_creature,decoy]+mana,
                   s.demo_deck(1)),diagnostic=True)
        self.assertFalse(sim.finished,sim.questions)
        sim.manual_priority=True;sim.phase='main'
        p=sim.players[0]
        for item in [spell,victim,library_creature,decoy]+mana:
            (p.hand if item in p.hand else p.library).remove(item)
        p.hand.append(spell)
        p.library.extend([library_creature,decoy])
        p.battlefield.extend(s.Permanent(c) for c in mana+[victim])
        return sim,p,spell,victim,library_creature

    @staticmethod
    def drain(sim):
        while sim.stack.items:sim.pass_priority(sim.stack.priority)

    def test_natural_order_and_unfamiliar_names_compile_full_cost_and_effect(self):
        for name in ('Natural Order','Unseen green ritual'):
            spell=self.spell(name=name)
            self.assertEqual(spell.kind,'library_search_spell')
            program=spell.library_search_program
            self.assertEqual((program.additional_cost.permanent_type,
                              program.additional_cost.color),('Creature','Green'))
            self.assertEqual((program.selector,program.color),('Creature','Green'))
            self.assertEqual(program.steps,('search','put_battlefield','shuffle'))
        unknown=(NATURAL['oracleText']+'\nDraw an extra card.')
        self.assertEqual(self.spell(unknown).kind,'unsupported')
        self.assertIsNone(compile_card(NATURAL['oracleText'].replace(
            'sacrifice a green creature','sacrifice a random creature'),['Sorcery']))

    def test_sacrifice_is_paid_on_cast_and_searched_creature_enters_at_resolution(self):
        sim,p,spell,victim,_=self.fixture()
        found=min((c for c in p.library if c.kind=='creature' and 'Green' in c.colors),
                  key=lambda c:c.id)
        before=len(p.library)
        sim.cast_spell(0,spell,sacrifice_id=victim.id)
        self.assertNotIn(victim,[perm.card for perm in p.battlefield])
        self.assertIn(victim,p.graveyard)
        self.assertIn(found,p.library)
        self.assertEqual(len(sim.stack.items),1)
        self.drain(sim)
        self.assertIn(found,[perm.card for perm in p.battlefield])
        self.assertIn(spell,p.graveyard)
        self.assertEqual(len(p.library),before-1)
        sim.invariant()

    def test_missing_wrong_color_and_nonexistent_cost_rejected_before_mana(self):
        sim,p,spell,victim,_=self.fixture()
        # Reuse the existing physical decoy from the library for the test.
        black=next(c for c in p.library if c.id=='cost-black-decoy')
        p.library.remove(black);p.battlefield.append(s.Permanent(black))
        for invalid in (None,black.id,'nonexistent'):
            with self.subTest(invalid=invalid):
                with self.assertRaisesRegex(ValueError,'Additional sacrifice cost'):
                    sim.cast_spell(0,spell,sacrifice_id=invalid)
                self.assertIn(spell,p.hand)
                self.assertFalse(sim.stack.items)
                self.assertTrue(all(not land.tapped for land in p.battlefield if land.card.kind=='land'))
        sim.invariant()

    def test_candidates_bind_payment_choice_instead_of_spell_target(self):
        sim,p,spell,victim,_=self.fixture()
        choices=sim.library_search_sacrifice_choices(0,spell,'cast')
        self.assertEqual([c.tap_ids for c in choices],[(victim.id,)])
        self.assertFalse(choices[0].target_permanent)
        self.assertNotIn('target=',choices[0].id)
        sim.invariant()

    def test_cost_can_be_parameterized_for_artifact_and_other_search_selector(self):
        oracle=('As an additional cost to cast this spell, sacrifice an artifact.\n'
                'Search your library for an enchantment card, put it onto the battlefield, then shuffle.')
        program=compile_card(oracle,['Sorcery'])
        self.assertIsNotNone(program)
        self.assertEqual((program.additional_cost.permanent_type,program.selector),
                         ('Artifact','Enchantment'))
        self.assertIsNone(compile_card(oracle+' Draw two cards.',['Sorcery']))


if __name__=='__main__':unittest.main()
