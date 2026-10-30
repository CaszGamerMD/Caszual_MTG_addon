"""Use real mirrored teaching deck fixtures to test transferable mechanic paths."""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from deck_adaptive_strategy import analyze_deck
from strategy_building_blocks import map_mechanics
from report_mirror_teaching import opening_stats

DECKS=Path(__file__).resolve().parents[1]/'decks'

class MirroredTeachingStrategyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.goblin=json.loads((DECKS/'14509839-mono-red-gobs.json').read_text())
        cls.elf=json.loads((DECKS/'14435337-lupitas-elves.json').read_text())

    def test_both_active_decks_have_100_cards(self):
        for d in (self.goblin,self.elf):
            self.assertEqual(sum(c['quantity'] for c in d['mainboard']),99)
            self.assertEqual(len(d['commanders']),1)
            self.assertEqual(d['commanders'][0]['quantity'],1)
        self.assertNotIn('Skullclamp',[c['name'] for c in self.elf['mainboard']])
        self.assertIn('Hordeling Outburst',[c['name'] for c in self.goblin['mainboard']])

    def test_same_combat_goal_different_mechanic_paths(self):
        g,e=analyze_deck(self.goblin),analyze_deck(self.elf)
        self.assertEqual(g.primary,'tribal_swarm')
        self.assertEqual(e.primary,'tribal_swarm')
        gr=next(x for x in g.routes if x.goal=='combat_damage')
        er=next(x for x in e.routes if x.goal=='combat_damage')
        self.assertIn('equipment_engine',gr.steps)
        self.assertIn('mana_engine',er.steps)
        self.assertIn('board_amplifier',er.steps)
        self.assertNotEqual(gr.steps,er.steps)
        gm=dict(gr.strengths)
        em=dict(er.strengths)
        self.assertGreater(gm['equipment_engine'],em['equipment_engine'])
        self.assertGreater(em['mana_engine'],gm['mana_engine'])
        # No name-based character/archetype rules: renamed deck must keep plan.
        renamed=dict(self.goblin,name='Anonymous',sourceDeckId=-1)
        self.assertEqual(g.routes,analyze_deck(renamed).routes)

    def test_opening_baseline_is_deterministic_and_not_claimed_to_be_rules_legal(self):
        g=opening_stats(self.goblin,500)
        e=opening_stats(self.elf,500)
        self.assertGreater(g['playableProxyRate'],0)
        self.assertGreater(e['playableProxyRate'],0)
        self.assertLess(abs(g['playableProxyRate']-e['playableProxyRate']),0.15)
        self.assertEqual(g,opening_stats(self.goblin,500))
        self.assertIn('not rules-validated',g['proxyDefinition'])

    def test_mirror_routes_use_real_rules_text(self):
        g=map_mechanics(self.goblin)
        e=map_mechanics(self.elf)
        names={c.name for c in g}
        self.assertIn('Krenko, Mob Boss',names)
        self.assertIn('Marwyn, the Nurturer',{c.name for c in e})
        self.assertTrue(any(c.blocks for c in g))
        self.assertTrue(any(c.blocks for c in e))


if __name__=='__main__':
    unittest.main()
