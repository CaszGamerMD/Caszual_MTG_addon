"""Landfall ability words compose with generic land-entry events and executable effects."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from card_events import Game, Permanent, parse_card
import simulator as s


def lagac(name='Unseen Ember Lizard', subtype='Lizard', damage=1):
    return dict(name=name,types=['Creature'],subTypes=[subtype],superTypes=[],
                manaCost='{3}{R}',colors=['Red'],colorIdentity=['Red'],
                oracleText=(f'Landfall — Whenever a land you control enters, '
                            f'{name} deals {damage} damage to each opponent.'),
                power='3',toughness='4')


def land(name='Unseen Grove'):
    return dict(name=name,types=['Land'],subTypes=[],superTypes=[],
                manaCost='',colors=[],colorIdentity=[],oracleText='')


class GenericLandfallTests(unittest.TestCase):
    def test_generic_names_subtypes_and_amounts(self):
        for tribe in ('Lizard','Goblin','Elf'):
            for amount in (1,2,3):
                raw=lagac('Unknown '+tribe+' Pyromancer',tribe,amount)
                d=parse_card(raw)
                self.assertTrue(d.supported,d.reason)
                self.assertEqual(len(d.triggers),1)
                t=d.triggers[0]
                self.assertEqual(t.event,'enters')
                self.assertEqual(t.subject.permanent_type,'Land')
                self.assertEqual(t.subject.relation,'controller')
                self.assertEqual((t.effect.operation,t.effect.amount),('damage',amount))

    def test_rejects_unknown_remainder_and_false_landfall_labels(self):
        raw=lagac()
        for bad in (raw['oracleText']+'\nSacrifice the moon.',
                    raw['oracleText']+' Then take another turn.',
                    'Landfall — Whenever a creature you control enters, draw a card.',
                    'Landfall — Draw a card.'):
            with self.subTest(text=bad):
                self.assertFalse(parse_card(dict(raw,oracleText=bad)).supported)

    def test_only_own_land_entry_triggers_and_each_entry_is_distinct(self):
        d=parse_card(lagac())
        g=Game()
        watcher=Permanent('watcher',d,0)
        g.enter_batch([watcher])
        g.events.clear()
        ldef=parse_card(land())
        g.enter_batch([Permanent('enemy-land',ldef,1)])
        self.assertFalse(any(e['kind']=='trigger' for e in g.events))
        g.events.clear()
        g.enter_batch([Permanent('mine-a',ldef,0),Permanent('mine-b',ldef,0)])
        events=[e for e in g.events if e['kind']=='trigger']
        self.assertEqual(len(events),2)
        self.assertEqual({e['entered'] for e in events},{'mine-a','mine-b'})
        self.assertTrue(all(e['operation']=='damage' and e['amount']==1 for e in events))

    @classmethod
    def setUpClass(cls):
        cls.rules=s.RulesBridge()

    @classmethod
    def tearDownClass(cls):
        cls.rules.close()

    def test_import_and_stack_resolve_landfall_without_early_damage(self):
        raw=lagac('Spitfire Lagac')
        creature=s.import_diagnostic_card(self.rules,raw,0,'lagac',{'Red'})
        self.assertEqual(creature.kind,'creature')
        grove=s.Card('grove','Unseen Grove','land',mask=1)
        sim=s.Simulator(self.rules,42,decks=(s.demo_deck(0)+[creature,grove],
                                            s.demo_deck(1)),diagnostic=True)
        sim.manual_priority=True
        sim.phase='main'
        p=sim.players[0]
        for card in (creature,grove):
            if card in p.hand:p.hand.remove(card)
            elif card in p.library:p.library.remove(card)
        p.hand.extend([creature,grove])
        p.hand.remove(creature)
        sim.resolve_entry_triggers(sim.enter_creature(creature,p),creature)
        before=sim.players[1].life
        p.hand.remove(grove)
        pending=sim.enter_creature(grove,p)
        self.assertEqual(len([e for e in pending if e.get('operation')=='damage']),1)
        sim.resolve_entry_triggers(pending,grove)
        self.assertEqual(sim.players[1].life,before)
        self.assertTrue(sim.stack.items)
        while sim.stack.items:sim.pass_priority(sim.stack.priority)
        self.assertEqual(sim.players[1].life,before-1)
        sim.invariant()


if __name__=='__main__':
    unittest.main()
