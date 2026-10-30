"""Indestructible is an executable keyword on lands, not discarded flavor text."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
from land_abilities import compile_land


def bridge(name='Unseen Ironwood Bridge', colors=('R','G')):
    mana=' or '.join('{'+c+'}' for c in colors)
    return dict(name=name,types=['Land'],subTypes=[],superTypes=[],
                manaCost='',colors=[],colorIdentity=['Red','Green'],
                oracleText='Indestructible\nThis land enters tapped.\n{T}: Add '+mana+'.')


class IndestructibleLandTests(unittest.TestCase):
    def test_keyword_and_entry_tap_compose_with_dual_mana(self):
        for name in ('Unseen Ironwood Bridge','Unknown Sliver Crossing'):
            raw=bridge(name)
            p=compile_land(raw,raw['oracleText'])
            self.assertIsNotNone(p)
            self.assertTrue(p['tapped'])
            self.assertEqual(p['mask'],(1<<3)|(1<<4))
            self.assertIn('indestructible',p['land_program'].keywords)

    def test_extra_instruction_is_not_ignored(self):
        raw=bridge()
        for text in (raw['oracleText']+'\nDraw three cards.',
                     raw['oracleText'].replace('Indestructible','Flying'),
                     raw['oracleText'].replace('Indestructible','Indestructible and flying')):
            with self.subTest(text=text):
                self.assertIsNone(compile_land(dict(raw,oracleText=text),text))

    @classmethod
    def setUpClass(cls):cls.rules=s.RulesBridge()
    @classmethod
    def tearDownClass(cls):cls.rules.close()

    def test_import_and_tapped_mana_execution(self):
        raw=bridge()
        card=s.import_diagnostic_card(self.rules,raw,0,'bridge',{'Red','Green'})
        self.assertEqual(card.kind,'land')
        self.assertTrue(card.enters_tapped)
        self.assertIn('indestructible',card.event_definition.abilities)
        sim=s.Simulator(self.rules,42,decks=(s.demo_deck(0)+[card],
                                            s.demo_deck(1)),diagnostic=True)
        sim.manual_priority=True
        sim.phase='main'
        p=sim.players[0]
        if card in p.hand:p.hand.remove(card)
        elif card in p.library:p.library.remove(card)
        sim.enter_creature(card,p)
        item=next(x for x in p.battlefield if x.card.id==card.id)
        self.assertTrue(item.tapped)
        self.assertNotIn(card.id,dict(sim.mana_sources(0)))
        state=sim.event_game('main').battlefield[card.id]
        self.assertTrue(sim.event_game('main').has(state,'indestructible'))
        item.tapped=False
        sources=dict(sim.mana_sources(0))
        self.assertIn(card.id,sources)
        self.assertEqual(len(sources[card.id]),2)
        sim.invariant()


if __name__=='__main__':
    unittest.main()
