"""Typed, targeted Equipment attachment activation and priority-stack tests."""
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from equipment_attach_activations import parse
import simulator as s


ORACLE='{T}: Attach target Equipment you control to target creature you control.'


class EquipmentAttachChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.rules=s.RulesBridge()
    @classmethod
    def tearDownClass(cls):cls.rules.close()

    def source(self,text=ORACLE,name='Unknown attachment worker',types=('Creature',)):
        raw=dict(name=name,layout='normal',types=list(types),subTypes=[],superTypes=[],
            colors=[],manaCost='{3}',oracleText=text,power='1',toughness='3')
        return s.import_diagnostic_card(self.rules,raw,0,'worker',set())

    @staticmethod
    def creature(uid,seat=0):
        return s.Card(uid,uid,'creature',power=2,toughness=2,traits='2;2;',
            event_definition=s.EventDefinition(uid,frozenset({'Creature'}),
                frozenset(),False,2,2,frozenset()))

    def fixture(self,source,land_count=3):
        equipment=s.Card('collar','Training collar','equipment',
            event_definition=s.EventDefinition('Training collar',frozenset({'Artifact'}),
                frozenset({'Equipment'}),False,0,0,frozenset(),
                attachment=('equipment','{2}',frozenset({'deathtouch'}),0,0)))
        allies=[self.creature('attached-first'),self.creature('attach-second')]
        enemy=self.creature('enemy',1)
        lands=[s.Card('attach-land-'+str(i),'Mana land','land',mask=63)
               for i in range(land_count)]
        sim=s.Simulator(self.rules,35,
            decks=(s.demo_deck(0)+[source,equipment]+allies+lands,
                   s.demo_deck(1)+[enemy]),diagnostic=True)
        self.assertFalse(sim.finished,sim.questions)
        sim.manual_priority=True;sim.phase='main'
        for seat,group in ((0,[source,equipment]+allies+lands),(1,[enemy])):
            p=sim.players[seat]
            for card in group:(p.hand if card in p.hand else p.library).remove(card)
            p.battlefield.extend(s.Permanent(c) for c in group)
        for item in sim.players[0].battlefield:item.fresh=False
        collar=next(p for p in sim.players[0].battlefield if p.card==equipment)
        collar.attached_to=allies[0].id
        return sim,equipment,allies,enemy

    @staticmethod
    def drain(sim):
        while sim.stack.items:sim.pass_priority(sim.stack.priority)

    def test_real_brass_squire_and_unfamiliar_source(self):
        deck=json.loads((Path(__file__).resolve().parents[1]/'decks/14509839-mono-red-gobs.json').read_text())
        raw=next(c for c in deck['mainboard'] if c['name']=='Brass Squire')
        card=s.import_diagnostic_card(self.rules,raw,0,'real-squire',{'Red'})
        self.assertEqual(card.kind,'creature')
        self.assertEqual(card.event_definition.attach_equipment_activation,
                         self.source().event_definition.attach_equipment_activation)
        self.assertEqual(self.source(name='Other equipment engineer').kind,'creature')

    def test_cast_time_targets_tap_and_resolve_after_source_leaves(self):
        source=self.source()
        sim,equipment,allies,_=self.fixture(source)
        options=[a for a in sim.legal(0) if a.kind=='activate_equipment_attach']
        self.assertTrue(any(a.tap_ids==(equipment.id,)
                            and a.target_permanent==allies[1].id for a in options))
        self.assertTrue(any(a.tap_ids==(equipment.id,)
                            and a.target_permanent==allies[0].id for a in options))
        sim.activate_equipment_attach(0,source.id,equipment.id,allies[1].id)
        squire=next(p for p in sim.players[0].battlefield if p.card==source)
        collar=next(p for p in sim.players[0].battlefield if p.card==equipment)
        self.assertTrue(squire.tapped)
        self.assertEqual(collar.attached_to,allies[0].id)  # no early attachment
        sim.players[0].battlefield.remove(squire);sim.players[0].graveyard.append(squire.card)
        self.drain(sim)
        self.assertEqual(collar.attached_to,allies[1].id)
        self.assertIn('deathtouch',sim.effective_card(next(
            p for p in sim.players[0].battlefield if p.card==allies[1])).traits)
        sim.invariant()

    def test_two_targets_fizzle_when_equipment_leaves(self):
        source=self.source()
        sim,equipment,allies,_=self.fixture(source)
        sim.activate_equipment_attach(0,source.id,equipment.id,allies[1].id)
        collar=next(p for p in sim.players[0].battlefield if p.card==equipment)
        sim.players[0].battlefield.remove(collar);sim.players[0].graveyard.append(collar.card)
        self.drain(sim)
        self.assertTrue(any(e['kind']=='equipment_attach_fizzle' for e in sim.events))
        sim.invariant()

    def test_creature_target_leaves_before_resolution(self):
        source=self.source()
        sim,equipment,allies,_=self.fixture(source)
        sim.activate_equipment_attach(0,source.id,equipment.id,allies[1].id)
        target=next(p for p in sim.players[0].battlefield if p.card==allies[1])
        sim.players[0].battlefield.remove(target)
        sim.players[0].graveyard.append(target.card)
        self.drain(sim)
        collar=next(p for p in sim.players[0].battlefield if p.card==equipment)
        self.assertEqual(collar.attached_to,allies[0].id)
        self.assertTrue(any(e['kind']=='equipment_attach_fizzle' for e in sim.events))
        sim.invariant()

    def test_cost_variant_and_illegal_targets_before_payment(self):
        source=self.source('{1}{G}, '+ORACLE,name='Unknown green engineer',types=('Artifact',))
        self.assertEqual(source.kind,'artifact')
        sim,equipment,allies,enemy=self.fixture(source)
        with self.assertRaises(ValueError):
            sim.activate_equipment_attach(0,source.id,equipment.id,enemy.id)
        self.assertFalse(any(p.tapped for p in sim.players[0].battlefield))
        sim.activate_equipment_attach(0,source.id,equipment.id,allies[1].id)
        self.assertEqual(sum(p.tapped for p in sim.players[0].battlefield),3)
        self.drain(sim)
        self.assertEqual(next(p for p in sim.players[0].battlefield
                              if p.card==equipment).attached_to,allies[1].id)
        sim.invariant()

    def test_fail_closed_on_extra_clauses_and_wrong_target_types(self):
        for oracle in (ORACLE+' Draw a card.',
                       ORACLE.replace('Equipment','artifact'),
                       ORACLE.replace('creature you control','creature'),
                       ORACLE.replace('{T}','{Q}')):
            with self.subTest(oracle=oracle):
                self.assertIsNone(parse(oracle,['Creature']))
                self.assertEqual(self.source(oracle).kind,'unsupported')
        self.assertEqual(self.source(types=('Instant',)).kind,'unsupported')


if __name__=='__main__':unittest.main()
