"""Activation-time same-name cost and condition, then independent stack draw."""
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from conditional_draw_activations import parse
import simulator as s


ORACLE=('{2}, {T}: Draw a card. Activate only if you control three or more '
        'lands with the same name.')


class ConditionalDrawChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.rules=s.RulesBridge()
    @classmethod
    def tearDownClass(cls):cls.rules.close()

    def card(self,text=ORACLE,name='Unknown artifact',types=('Artifact',)):
        definition=dict(name=name,layout='normal',types=list(types),subTypes=[],
            superTypes=[],colors=[],manaCost='{2}',oracleText=text)
        return s.import_diagnostic_card(self.rules,definition,0,'draw-device',set())

    def fixture(self,card,lands=('Mountain','Mountain','Mountain'),extras=()):
        sources=[s.Card('name-land-'+str(i),name,'land',mask=63)
                 for i,name in enumerate(lands)]
        sim=s.Simulator(self.rules,510,
            decks=(s.demo_deck(0)+[card]+sources+list(extras),s.demo_deck(1)),diagnostic=True)
        self.assertFalse(sim.finished,sim.questions)
        sim.manual_priority=True;sim.phase='main'
        p=sim.players[0]
        for item in [card]+sources+list(extras):
            (p.hand if item in p.hand else p.library).remove(item)
        p.battlefield.extend([s.Permanent(card)]+[s.Permanent(item) for item in sources+list(extras)])
        return sim,card,sources

    @staticmethod
    def drain(sim):
        while sim.stack.items:sim.pass_priority(sim.stack.priority)

    def test_real_endless_atlas_and_unfamiliar_names(self):
        deck=json.loads((Path(__file__).resolve().parents[1]/'decks/14509839-mono-red-gobs.json').read_text())
        raw=next(c for c in deck['mainboard'] if c['name']=='Endless Atlas')
        real=s.import_diagnostic_card(self.rules,raw,0,'real-atlas',{'Red'})
        self.assertEqual(real.kind,'artifact')
        self.assertEqual(real.event_definition.conditional_draw_activation,self.card().event_definition.conditional_draw_activation)
        self.assertEqual(self.card(name='Never printed artifact').kind,'artifact')

    def test_cost_taps_two_lands_and_source_draws_on_stack(self):
        card=self.card()
        sim,_,lands=self.fixture(card)
        options=[c for c in sim.legal(0) if c.kind=='activate_conditional_draw']
        self.assertEqual(len(options),1)
        p=sim.players[0];before=len(p.library)
        sim.activate_conditional_draw(0,card.id)
        self.assertEqual(len(p.library),before)
        self.assertEqual(sum(x.tapped for x in p.battlefield),3)
        self.assertEqual(len(sim.stack.items),1)
        # The condition is checked at activation, not again at resolution.
        removed=next(x for x in p.battlefield if x.card==lands[0])
        p.battlefield.remove(removed);p.graveyard.append(removed.card)
        self.drain(sim)
        self.assertEqual(len(p.library),before-1)
        self.assertTrue(any(e['kind']=='conditional_draw' for e in sim.events))
        sim.invariant()

    def test_invalid_name_condition_rejects_before_tapping_or_mana(self):
        sim,card,_=self.fixture(self.card(),('Mountain','Mountain','Forest'))
        self.assertFalse(any(c.kind=='activate_conditional_draw' for c in sim.legal(0)))
        with self.assertRaises(ValueError):sim.activate_conditional_draw(0,card.id)
        self.assertFalse(any(p.tapped for p in sim.players[0].battlefield))
        self.assertFalse(sim.stack.items)
        sim.invariant()

    def test_changed_cost_and_count_with_priorities(self):
        text=('{1}{G}, {T}: Draw two cards. Activate only if you control '
              '2 or more artifacts with the same name.')
        card=self.card(text)
        self.assertEqual(card.kind,'artifact')
        twin=s.Card('another-copy',card.name,'artifact',event_definition=card.event_definition)
        sim,_,_=self.fixture(card,extras=(twin,))
        self.assertEqual(len(sim.conditional_draw_choices(0)),2)
        sim.stack.priority=1
        with self.assertRaises(ValueError):sim.activate_conditional_draw(0,card.id)
        self.assertFalse(any(p.tapped for p in sim.players[0].battlefield))
        sim.stack.priority=0
        before=len(sim.players[0].library)
        sim.activate_conditional_draw(0,card.id)
        self.drain(sim)
        self.assertEqual(len(sim.players[0].library),before-2)
        sim.invariant()

    def test_rejects_extra_text_unsupported_costs_and_wrong_type(self):
        for oracle in (ORACLE+' Draw another card.',
                       ORACLE.replace('same name','same creature type'),
                       ORACLE.replace('{2}','{X}'),
                       ORACLE.replace('three or more','one or more')):
            with self.subTest(oracle=oracle):
                self.assertIsNone(parse(oracle,['Artifact']))
                self.assertEqual(self.card(oracle).kind,'unsupported')
        self.assertEqual(self.card(types=('Instant',)).kind,'unsupported')


if __name__=='__main__':unittest.main()
