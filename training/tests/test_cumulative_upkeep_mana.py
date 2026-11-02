"""Generalized cumulative upkeep when the upkeep instruction produces mana."""
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
from cumulative_upkeep_mana import parse


TEXT=('Cumulative upkeep—Add {R}. (At the beginning of your upkeep, put an age '
      'counter on this permanent, then sacrifice it unless you pay its upkeep '
      'cost for each age counter on it.)')


class CumulativeUpkeepManaChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.rules=s.RulesBridge()
    @classmethod
    def tearDownClass(cls):cls.rules.close()

    def source(self,text=TEXT,name='Unfamiliar growing flame'):
        raw=dict(name=name,layout='normal',types=['Enchantment'],subTypes=[],
                 superTypes=[],manaCost='{1}{R}',colors=['Red'],oracleText=text)
        return s.import_diagnostic_card(self.rules,raw,0,'age-'+name,{'Red'})

    def fixture(self,source=None):
        source=source or self.source()
        sim=s.Simulator(self.rules,47,decks=(s.demo_deck(0)+[source],s.demo_deck(1)),
                        diagnostic=True)
        self.assertFalse(sim.finished,sim.questions)
        owner=sim.players[0]
        (owner.hand if source in owner.hand else owner.library).remove(source)
        owner.battlefield.append(s.Permanent(source))
        sim.manual_priority=True
        return sim,source

    def upkeep(self,sim,source):
        sim.active=0
        events=[e for e in sim.event_game('upkeep').upkeep_triggers()
                if e.get('operation')=='cumulative_upkeep_mana']
        self.assertEqual(len(events),1)
        sim._resolve_entry_effects(events,source)

    def test_real_braid_and_unknown_name_share_program(self):
        deck=json.loads((Path(__file__).resolve().parents[1]/'decks/14509839-mono-red-gobs.json').read_text())
        raw=next(c for c in deck['mainboard'] if c['name']=='Braid of Fire')
        real=s.import_diagnostic_card(self.rules,raw,0,'real-braid',{'Red'})
        self.assertEqual(real.kind,'enchantment')
        self.assertEqual(real.event_definition.cumulative_upkeep_mana,
                         self.source().event_definition.cumulative_upkeep_mana)

    def test_age_counters_and_repeated_mana_grow_each_owner_upkeep(self):
        sim,source=self.fixture()
        permanent=sim.players[0].battlefield[-1]
        for count in (1,2,3):
            self.upkeep(sim,source)
            self.assertEqual(permanent.age_counters,count)
            self.assertEqual(sim.players[0].mana_pool[3],sum(range(1,count+1)))
        self.assertEqual(sim.players[1].mana_pool[3],0)
        sim.invariant()

    def test_other_players_upkeep_does_not_trigger_and_leaving_fizzles(self):
        sim,source=self.fixture()
        sim.active=1
        self.assertFalse(any(e.get('operation')=='cumulative_upkeep_mana'
                             for e in sim.event_game('upkeep').upkeep_triggers()))
        sim.active=0
        event=next(e for e in sim.event_game('upkeep').upkeep_triggers()
                   if e.get('operation')=='cumulative_upkeep_mana')
        sim.send_to_destination(sim.players[0],sim.players[0].battlefield[-1])
        sim._resolve_entry_effects([event],source)
        self.assertEqual(sim.players[0].mana_pool[3],0)
        sim.invariant()

    def test_parameterized_mana_color_and_unknown_clause_rejected(self):
        changed=self.source(TEXT.replace('{R}','{G}'),name='New green reserves')
        sim,source=self.fixture(changed)
        self.upkeep(sim,source)
        self.assertEqual(sim.players[0].mana_pool[4],1)
        self.assertEqual(sim.players[0].mana_pool[3],0)
        self.assertEqual(self.source(TEXT+' Draw a card.').kind,'unsupported')
        self.assertEqual(self.source(TEXT.replace('Add {R}','Pay {R}')).kind,'unsupported')
        self.assertIsNone(parse(TEXT,['Instant']))
        sim.invariant()


if __name__=='__main__':unittest.main()
