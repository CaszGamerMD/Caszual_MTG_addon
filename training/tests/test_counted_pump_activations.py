"""Targeted tap-cost activations with a live battlefield quantity."""
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from counted_pump_activations import parse
from counted_effect_blocks import BattlefieldCount
import simulator as s


ORACLE=('{T}: Target creature gets +X/+X until end of turn, where X is '
        'the number of Elves on the battlefield.')


class CountedPumpChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.rules=s.RulesBridge()
    @classmethod
    def tearDownClass(cls):cls.rules.close()

    def card(self,text=ORACLE,name='Unseen ability creature',types=('Creature',)):
        raw=dict(name=name,layout='normal',types=list(types),subTypes=['Elf'],
            superTypes=[],colors=['Green'],manaCost='{2}{G}',oracleText=text,
            power='2',toughness='2')
        return s.import_diagnostic_card(self.rules,raw,0,'counted-source',{'Green'})

    @staticmethod
    def creature(uid,subtype,seat=0,abilities=()):
        return s.Card(uid,uid,'creature',power=2,toughness=2,traits='2;2;'+','.join(abilities),
            event_definition=s.EventDefinition(uid,frozenset({'Creature'}),
                frozenset({subtype}),False,2,2,frozenset(abilities)))

    def fixture(self,source):
        allies=[self.creature('other-elf','Elf'),self.creature('friendly-human','Human')]
        enemy=[self.creature('enemy-elf','Elf',1),self.creature('enemy-goblin','Goblin',1)]
        sim=s.Simulator(self.rules,91,
            decks=(s.demo_deck(0)+[source]+allies,s.demo_deck(1)+enemy),diagnostic=True)
        self.assertFalse(sim.finished,sim.questions)
        sim.manual_priority=True;sim.phase='main'
        for seat,group in ((0,[source]+allies),(1,enemy)):
            p=sim.players[seat]
            for card in group:(p.hand if card in p.hand else p.library).remove(card)
            p.battlefield.extend(s.Permanent(c) for c in group)
        next(p for p in sim.players[0].battlefield if p.card==source).fresh=False
        return sim,allies,enemy

    @staticmethod
    def drain(sim):
        while sim.stack.items:sim.pass_priority(sim.stack.priority)

    def test_real_timberwatch_and_unknown_grammar(self):
        deck=json.loads((Path(__file__).resolve().parents[1]/'decks/14435337-lupitas-elves.json').read_text())
        raw=next(c for c in deck['mainboard'] if c['name']=='Timberwatch Elf')
        actual=s.import_diagnostic_card(self.rules,raw,0,'timber',{'Green'})
        self.assertEqual(actual.kind,'creature')
        self.assertEqual(actual.event_definition.counted_pump_activation,
                         self.card().event_definition.counted_pump_activation)
        self.assertEqual(self.card(name='Unknown grove keeper').kind,'creature')

    def test_tap_and_target_bind_before_resolution_count_after(self):
        source=self.card()
        sim,allies,enemies=self.fixture(source)
        candidates=[c for c in sim.legal(0) if c.kind=='activate_counted_pump']
        self.assertEqual(len(candidates),5)  # source, own 2, opponent 2
        sim.activate_counted_pump(0,source.id,allies[1].id)
        self.assertTrue(next(p for p in sim.players[0].battlefield if p.card==source).tapped)
        self.assertEqual(len(sim.stack.items),1)
        # Battlefield count changes after activation but before resolution.
        dead=next(p for p in sim.players[1].battlefield if p.card==enemies[0])
        sim.players[1].battlefield.remove(dead);sim.players[1].graveyard.append(dead.card)
        self.drain(sim)
        game=sim.event_game('main')
        self.assertEqual(game.stats(game.battlefield[allies[1].id]),(4,4))
        self.assertEqual(game.stats(game.battlefield[allies[0].id]),(2,2))
        self.assertEqual(next(e for e in sim.events if e['kind']=='counted_pump')['details']['amount'],2)
        sim.invariant()

    def test_changed_subtype_and_control_scope_and_target_fizzle(self):
        text=ORACLE.replace('Elves on the battlefield','Goblins you control')
        source=self.card(text,name='Other tap ability')
        self.assertEqual(source.kind,'creature')
        sim,allies,_=self.fixture(source)
        sim.activate_counted_pump(0,source.id,allies[0].id)
        target=next(p for p in sim.players[0].battlefield if p.card==allies[0])
        sim.players[0].battlefield.remove(target);sim.players[0].graveyard.append(target.card)
        self.drain(sim)
        self.assertTrue(any(e['kind']=='counted_pump_fizzle' for e in sim.events))
        sim.invariant()

    def test_illegal_targets_summoning_sickness_and_tapping(self):
        source=self.card()
        sim,allies,_=self.fixture(source)
        permanent=next(p for p in sim.players[0].battlefield if p.card==source)
        permanent.fresh=True
        self.assertFalse(sim.counted_pump_choices(0))
        with self.assertRaises(ValueError):sim.activate_counted_pump(0,source.id,allies[0].id)
        self.assertFalse(permanent.tapped)
        permanent.fresh=False
        with self.assertRaises(ValueError):sim.activate_counted_pump(0,source.id,'missing')
        self.assertFalse(permanent.tapped)
        sim.stack.priority=1
        with self.assertRaises(ValueError):sim.activate_counted_pump(0,source.id,allies[0].id)
        self.assertFalse(permanent.tapped)

    def test_source_leaves_stack_ability_and_changeling_count(self):
        source=self.card()
        sim,allies,_=self.fixture(source)
        sim.activate_counted_pump(0,source.id,allies[1].id)
        gone=next(p for p in sim.players[0].battlefield if p.card==source)
        sim.players[0].battlefield.remove(gone)
        sim.players[0].graveyard.append(gone.card)
        self.drain(sim)
        game=sim.event_game('main')
        self.assertEqual(game.stats(game.battlefield[allies[1].id]),(4,4))
        sim.invariant()
        kernel=s.EventGame()
        changeling=s.EventDefinition('Shapeshifter',frozenset({'Creature'}),
            frozenset({'Shapeshifter'}),False,1,1,frozenset({'changeling'}))
        kernel.enter(s.EventPermanent('changer',changeling,0))
        self.assertEqual(BattlefieldCount('any',card_type='Creature',subtype='Elf').evaluate(kernel,0),1)

    def test_unknown_extra_clauses_reject_complete_card(self):
        for text in (ORACLE+' Draw a card.',ORACLE.replace('+X/+X','+X/+1'),
                     ORACLE.replace('number of Elves','number of cards'),
                     ORACLE.replace('Elves','Equipments'),
                     ORACLE.replace('Target creature','Each creature')):
            with self.subTest(text=text):
                self.assertIsNone(parse(text,['Creature']))
                self.assertEqual(self.card(text).kind,'unsupported')
        self.assertEqual(self.card(types=('Sorcery',)).kind,'unsupported')


if __name__=='__main__':unittest.main()
