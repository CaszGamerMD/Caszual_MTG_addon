"""Flashback grammar, alternative-cost payment, exile and counter behavior."""
import sys
import unittest
from pathlib import Path
from dataclasses import replace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
import test_enchantment_abilities as fixtures

class FlashbackRulesChecks(unittest.TestCase):
    setUpClass=classmethod(fixtures.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.EnchantmentChecks.tearDownClass.__func__)
    fixture=fixtures.EnchantmentChecks.fixture
    drain=fixtures.EnchantmentChecks.drain

    def test_real_chatter_and_unseen_name_counts_colors_and_cost(self):
        raw=dict(self.lookup['Chatter of the Squirrel'])
        parsed=s.import_diagnostic_card(self.rules,raw,0,'squirrel',{'Green'})
        self.assertEqual((parsed.kind,parsed.flashback_cost),('token_spell','{1}{G}'))
        self.assertEqual(parsed.token_count,1)
        self.assertEqual(parsed.token_definition.colors,frozenset({'G'}))
        self.assertIn('Squirrel',parsed.token_definition.subtypes)
        alternate=dict(raw,name='Unknown flashback tokens',
                       oracleText='Create two 2/3 blue Drake creature tokens with flying.\nFlashback {2}{U}{U}')
        other=s.import_diagnostic_card(self.rules,alternate,0,'dragon',set())
        self.assertEqual(other.kind,'token_spell')
        self.assertEqual((other.flashback_cost,other.token_count,other.token_definition.power),
                         ('{2}{U}{U}',2,2))
        for suffix in ('\nDraw a bonus card.','\nFlashback {2}{U}', '\nSurprise effect.'):
            modified=dict(alternate,oracleText=alternate['oracleText']+suffix)
            self.assertEqual(s.import_diagnostic_card(self.rules,modified,0,'bad',set()).kind,'unsupported')

    def test_hand_cast_goes_graveyard_then_flashback_exiles_and_creates_tokens(self):
        sim,cards=self.fixture(['Chatter of the Squirrel'])
        spell=cards['Chatter of the Squirrel']
        sim.cast_spell(0,spell);self.drain(sim)
        self.assertIn(spell,sim.players[0].graveyard)
        self.assertEqual(len([p for p in sim.players[0].battlefield if p.card.is_token]),1)
        legal=sim.legal(0)
        candidate=next(c for c in legal if c.kind=='cast_flashback' and c.card_id==spell.id)
        self.assertEqual(candidate.id,spell.id+':flashback')
        sim.cast_spell(0,spell,flashback=True)
        self.assertNotIn(spell,sim.players[0].graveyard)
        self.drain(sim)
        self.assertIn(spell,sim.players[0].exile)
        self.assertEqual(len([p for p in sim.players[0].battlefield if p.card.is_token]),2)
        self.assertFalse(any(c.kind=='cast_flashback' for c in sim.legal(0)))
        sim.invariant()

    def test_flashback_countered_spell_exiles_not_graveyard(self):
        sim,cards=self.fixture(['Chatter of the Squirrel'])
        spell=cards['Chatter of the Squirrel']
        sim.players[0].hand.remove(spell);sim.players[0].graveyard.append(spell)
        sim.cast_spell(0,spell,flashback=True)
        frame=sim.stack.items[-1]
        sim.counter_stack_item(frame)
        self.assertNotIn(spell,sim.players[0].graveyard)
        self.assertIn(spell,sim.players[0].exile)
        self.assertFalse(any(p.card.is_token for p in sim.players[0].battlefield))
        sim.invariant()

    def test_cannot_flashback_from_hand_or_exile_or_without_supported_permission(self):
        sim,cards=self.fixture(['Chatter of the Squirrel'])
        spell=cards['Chatter of the Squirrel']
        with self.assertRaisesRegex(ValueError,'casting zone'):
            sim.cast_spell(0,spell,flashback=True)
        ordinary=replace(spell,id='ordinary',flashback_cost='')
        with self.assertRaisesRegex(ValueError,'flashback permission'):
            sim.cast_spell(0,ordinary,flashback=True)
        sim.players[0].hand.remove(spell);sim.players[0].exile.append(spell)
        with self.assertRaisesRegex(ValueError,'casting zone'):
            sim.cast_spell(0,spell,flashback=True)
        sim.invariant()

    def test_flashback_mana_cost_is_distinct_from_original_and_pays_once(self):
        sim,cards=self.fixture(['Chatter of the Squirrel'])
        spell=cards['Chatter of the Squirrel']
        sim.players[0].hand.remove(spell);sim.players[0].graveyard.append(spell)
        for land in sim.players[0].battlefield:
            if land.card.id not in ('mana0',):land.tapped=True
        with self.assertRaisesRegex(ValueError,'Cannot pay'):
            sim.cast_spell(0,spell,flashback=True)
        self.assertIn(spell,sim.players[0].graveyard)
        for land in sim.players[0].battlefield:
            if land.card.id=='mana1':land.tapped=False
        sim.cast_spell(0,spell,flashback=True);self.drain(sim)
        self.assertIn(spell,sim.players[0].exile);sim.invariant()

