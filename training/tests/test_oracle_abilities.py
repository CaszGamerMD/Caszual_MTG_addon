import sys
from pathlib import Path
import unittest
from dataclasses import replace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from card_events import parse_card, Game, Permanent, Definition
from oracle_abilities import compile_abilities
import simulator as s

class OracleGrammarChecks(unittest.TestCase):
    def test_real_anthem_import_and_hybrid_liege_boundary(self):
        import json
        root=Path(__file__).resolve().parents[1]
        lookup={c['name']:c for p in (root/'decks').glob('*.json') for c in json.loads(p.read_text())['mainboard']}
        with s.RulesBridge() as rules:
            anthem=s.import_diagnostic_card(rules,lookup['Glorious Anthem'],0,'anthem',{'White'})
            self.assertEqual(anthem.kind,'enchantment')
            self.assertTrue(parse_card(lookup['Glen Elendra Liege']).supported)
            liege=s.import_diagnostic_card(rules,lookup['Glen Elendra Liege'],0,'liege',{'Blue','Black'})
            self.assertEqual(liege.kind,'unsupported')  # Hybrid costs are not implemented.

    def test_color_anthems_stack_for_multicolored_creatures_and_cease(self):
        lord=self.definition('Flying\nOther blue creatures you control get +1/+1.\nOther black creatures you control get +1/+1.')
        g=Game();g.enter(Permanent('lord',lord,0))
        for identifier,colors,controller in [('both',{'Blue','Black'},0),('blue',{'Blue'},0),('red',{'Red'},0),('enemy',{'Blue','Black'},1)]:
            g.enter(Permanent(identifier,replace(self.definition(''),colors=frozenset(colors)),controller))
        self.assertEqual(g.stats(g.battlefield['both']),(4,4))
        self.assertEqual(g.stats(g.battlefield['blue']),(3,3))
        self.assertEqual(g.stats(g.battlefield['red']),(2,2))
        self.assertEqual(g.stats(g.battlefield['enemy']),(2,2))
        self.assertEqual(g.stats(g.battlefield['lord']),(2,2))
        g.leave('lord');self.assertEqual(g.stats(g.battlefield['both']),(2,2))

    def test_global_creature_bonus_includes_source_when_it_is_a_creature(self):
        g=Game();g.enter(Permanent('source',self.definition('Creatures you control get +2/+3.'),0))
        self.assertEqual(g.stats(g.battlefield['source']),(4,5))
        self.assertFalse(self.definition('Creatures you control get +2/+3.\nThey have ward {2}.').supported)

    def test_irregular_type_plurals_and_unknown_inflections(self):
        for plural,singular in [('Allies','Ally'),('Faeries','Faerie'),('Zombies','Zombie'),('Elves','Elf'),('Mice','Mouse')]:
            d=self.definition(f'Other {plural} you control get +1/+1.')
            self.assertTrue(d.supported)
            self.assertEqual(d.static_effects[0].subject.subtype,singular)
        self.assertFalse(self.definition('Other Mysteries you control get +1/+1.').supported)

    def definition(self,text,name='Unseen card'):
        return parse_card(dict(name=name,types=['Creature'],subTypes=['Wizard'],power='2',toughness='2',oracleText=text))

    def test_name_does_not_select_behavior(self):
        text='Whenever another Goblin you control enters, each opponent loses 3 life.'
        a=self.definition(text,'Brand new card'); b=self.definition(text,'Obyra, Dreaming Duelist')
        self.assertTrue(a.supported); self.assertEqual(a.triggers,b.triggers)
        self.assertEqual(a.triggers[0].effect.amount,3)
        self.assertEqual(a.triggers[0].subject.subtype,'Goblin')

    def test_subtype_controller_and_other_are_independent_filters(self):
        d=self.definition('Whenever another Goblin creature you control enters, each opponent loses 3 life.')
        g=Game();g.enter(Permanent('source',d,0))
        for i,(types,subtype,controller) in enumerate([
                ({'Creature'},{'Faerie'},0),({'Creature'},{'Goblin'},1),
                ({'Enchantment'},{'Goblin'},0),({'Creature'},{'Goblin'},0)]):
            token=Definition('Subject',frozenset(types),frozenset(subtype),False,1,1,frozenset())
            g.enter(Permanent(str(i),token,controller))
        triggers=[e for e in g.events if e['kind']=='trigger']
        self.assertEqual([e['entered'] for e in triggers],['3'])
        self.assertEqual(triggers[0]['amount'],3)

    def test_subtype_without_creature_restriction_counts_kindred(self):
        g=Game();g.enter(Permanent('s',self.definition('Whenever another Goblin you control enters, each opponent loses 2 life.'),0))
        g.enter(Permanent('k',Definition('Kindred',frozenset({'Enchantment'}),frozenset({'Goblin'}),False,0,0,frozenset()),0))
        self.assertEqual(len([e for e in g.events if e['kind']=='trigger']),1)

    def test_death_trigger_effect_amounts_and_self_reference(self):
        text='Whenever Unknown Sage or another creature you control dies, each opponent loses 2 life and you gain 3 life.'
        d=self.definition(text,'Unknown Sage'); self.assertTrue(d.supported)
        g=Game();g.enter(Permanent('s',d,0))
        e=g.death_triggers(['s'])[0]
        self.assertEqual((e['amount'],e['gain'],e['recipient']),(2,3,'each opponent'))

    def test_compound_keywords_and_multiple_abilities(self):
        d=self.definition('Flying, lifelink\nWhen this creature enters, scry 4.\nWhenever another Faerie you control enters, each opponent loses 2 life.')
        self.assertTrue(d.supported); self.assertEqual(len(d.triggers),2)
        self.assertEqual(d.abilities,frozenset({'flying','lifelink'}))

    def test_continuous_effects_generalize_types_amounts_and_names(self):
        lord=self.definition('Other Wizards you control get +2/+3.','Unseen lord')
        counted=self.definition('This creature gets +3/+1 for each other Wizard on the battlefield.','Unseen counter')
        self.assertTrue(lord.supported and counted.supported)
        g=Game();g.enter(Permanent('lord',lord,0));g.enter(Permanent('counted',counted,0))
        self.assertEqual(g.stats(g.battlefield['lord']),(2,2))
        self.assertEqual(g.stats(g.battlefield['counted']),(7,6))
        enemy=self.definition('','Enemy wizard');g.enter(Permanent('enemy',enemy,1))
        self.assertEqual(g.stats(g.battlefield['counted']),(10,7))
        self.assertEqual(g.stats(g.battlefield['enemy']),(2,2))
        g.leave('lord')
        self.assertEqual(g.stats(g.battlefield['counted']),(5,3))

    def test_color_condition_is_read_from_text(self):
        d=self.definition('This creature gets +2/+4 as long as you control another red creature.')
        g=Game();g.enter(Permanent('source',d,0))
        ally=replace(self.definition(''),colors=frozenset({'Red'}))
        g.enter(Permanent('ally',ally,0));self.assertEqual(g.stats(g.battlefield['source']),(4,6))
        g.leave('ally');self.assertEqual(g.stats(g.battlefield['source']),(2,2))

    def test_unknown_remainder_is_never_dropped(self):
        valid='Whenever another Goblin you control enters, each opponent loses 3 life.'
        for text in (valid+'\nDraw a card.',valid+' Draw a card.',
                     'Whenever another Goblin you control enters, if you control a Forest, each opponent loses 3 life.',
                     'Whenever one or more Goblins you control enter, each opponent loses 3 life.',
                     'Whenever another Goblin you control enters, you may have each opponent lose 3 life.'):
            self.assertFalse(self.definition(text).supported,text)

    def test_arbitrary_card_enters_real_diagnostic_import_and_resolution(self):
        raw=dict(name='Unknown test card',types=['Creature'],subTypes=['Goblin'],power='2',toughness='2',
                 manaCost='{1}{R}',oracleText='When this creature enters, each opponent loses 3 life and you gain 2 life.')
        with s.RulesBridge() as rules:
            card=s.import_diagnostic_card(rules,raw,0,'unknown',{'Red'})
            self.assertEqual(card.kind,'creature')
            sim=s.Simulator(rules,42,decks=(s.demo_deck(0)+[card],s.demo_deck(1)),diagnostic=True)
            p=sim.players[0]; (p.hand if card in p.hand else p.library).remove(card)
            sim.resolve_entry_triggers(sim.enter_creature(card,p),card)
            self.assertEqual([x.life for x in sim.players],[42,37]); sim.invariant()

if __name__=='__main__': unittest.main()
