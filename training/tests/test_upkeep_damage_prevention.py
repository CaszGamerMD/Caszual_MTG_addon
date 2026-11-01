"""Each-player upkeep damage and continuous life-gain prevention."""
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
from upkeep_damage_prevention import parse


TEXT=("At the beginning of each player's upkeep, this enchantment deals 2 damage "
      'to that player.\nIf a player would gain life, that player gains no life instead.')


class UpkeepDamagePreventionChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.rules=s.RulesBridge()
    @classmethod
    def tearDownClass(cls):cls.rules.close()

    def enchantment(self,text=TEXT,name='Unfamiliar pressure field'):
        raw=dict(name=name,layout='normal',types=['Enchantment'],subTypes=[],
                 superTypes=[],manaCost='{1}{R}{R}',colors=['Red'],oracleText=text)
        return s.import_diagnostic_card(self.rules,raw,0,'pressure-'+name,{'Red'})

    def fixture(self,source=None):
        source=source or self.enchantment()
        sim=s.Simulator(self.rules,73,decks=(s.demo_deck(0)+[source],s.demo_deck(1)),
                        diagnostic=True)
        self.assertFalse(sim.finished,sim.questions)
        owner=sim.players[0]
        (owner.hand if source in owner.hand else owner.library).remove(source)
        owner.battlefield.append(s.Permanent(source))
        sim.manual_priority=True;sim.phase='upkeep'
        return sim,source

    def test_real_card_and_renamed_card_have_same_program(self):
        deck=json.loads((Path(__file__).resolve().parents[1]/'decks/14509839-mono-red-gobs.json').read_text())
        raw=next(c for c in deck['mainboard'] if c['name']=='Sulfuric Vortex')
        real=s.import_diagnostic_card(self.rules,raw,0,'real-vortex',{'Red'})
        unknown=self.enchantment()
        self.assertEqual(real.kind,'enchantment')
        self.assertEqual(real.event_definition.upkeep_damage_prevention,
                         unknown.event_definition.upkeep_damage_prevention)

    def test_each_players_upkeep_takes_damage_from_owner_enchantment(self):
        sim,source=self.fixture()
        for active in (0,1):
            sim.active=active
            triggers=sim.event_game('upkeep').upkeep_triggers()
            events=[event for event in triggers if event['operation']=='upkeep_damage_player']
            self.assertEqual(len(events),1)
            self.assertEqual(events[0]['targetPlayer'],active)
            sim._resolve_entry_effects(events,source)
        self.assertEqual([p.life for p in sim.players],[38,38])
        self.assertEqual(sim.damage_to_players[0],{source.id})
        self.assertEqual(sim.damage_to_players[1],{source.id})
        sim.invariant()

    def test_life_gain_stays_prevented_for_both_players_until_source_leaves(self):
        sim,source=self.fixture()
        sim.gain_life(0,5);sim.gain_life(1,7)
        self.assertEqual([p.life for p in sim.players],[40,40])
        self.assertEqual(sim.life_gained_turn,[0,0])
        permanent=sim.players[0].battlefield[-1]
        sim.send_to_destination(sim.players[0],permanent)
        sim.gain_life(0,5);sim.gain_life(1,7)
        self.assertEqual([p.life for p in sim.players],[45,47])
        sim.invariant()

    def test_trigger_uses_snapshot_even_if_source_leaves(self):
        sim,source=self.fixture();sim.active=1
        event=next(e for e in sim.event_game('upkeep').upkeep_triggers()
                   if e['operation']=='upkeep_damage_player')
        sim.send_to_destination(sim.players[0],sim.players[0].battlefield[-1])
        sim._resolve_entry_effects([event],source)
        self.assertEqual(sim.players[1].life,38)
        sim.invariant()

    def test_parameterized_amount_and_fail_closed_unknown_rules(self):
        increased=self.enchantment(TEXT.replace('deals 2 damage','deals 4 damage'))
        sim,source=self.fixture(increased)
        events=sim.event_game('upkeep').upkeep_triggers()
        self.assertEqual(next(e['amount'] for e in events if e['operation']=='upkeep_damage_player'),4)
        self.assertEqual(self.enchantment(TEXT+' Draw a card.').kind,'unsupported')
        self.assertEqual(self.enchantment(TEXT.replace('each player\'s','your')).kind,'unsupported')
        self.assertIsNone(parse(TEXT,'Unfamiliar pressure field',['Instant']))
        sim.invariant()


if __name__=='__main__':unittest.main()
