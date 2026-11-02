"""Toxic grants poison on positive combat damage to players, not life loss."""
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
from toxic_programs import parse


TEXT='Toxic 2 (Players dealt combat damage by this creature also get two poison counters.)'


class ToxicProgramChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.rules=s.RulesBridge()
    @classmethod
    def tearDownClass(cls):cls.rules.close()

    def source(self,text=TEXT,name='Unfamiliar toxic creature'):
        raw=dict(name=name,layout='normal',types=['Creature'],subTypes=['Elf'],
                 superTypes=[],manaCost='{2}{G}',colors=['Green'],power='3',
                 toughness='1',oracleText=text)
        return s.import_diagnostic_card(self.rules,raw,0,'toxic-'+name,{'Green'})

    def fixture(self,source=None):
        source=source or self.source()
        sim=s.Simulator(self.rules,41,decks=(s.demo_deck(0)+[source],s.demo_deck(1)),
                        diagnostic=True)
        self.assertFalse(sim.finished,sim.questions)
        owner=sim.players[0]
        (owner.hand if source in owner.hand else owner.library).remove(source)
        owner.battlefield.append(s.Permanent(source,fresh=False))
        sim.manual_priority=True;sim.active=0;sim.phase='group_damage_start'
        sim.group_combat=dict(attackers=[source.id],blocks={},blocked=set(),early=None)
        return sim,source

    def test_real_branchblight_and_unknown_name_compile_same_number(self):
        deck=json.loads((Path(__file__).resolve().parents[1]/'decks/14435337-lupitas-elves.json').read_text())
        raw=next(c for c in deck['mainboard'] if c['name']=='Branchblight Stalker')
        real=s.import_diagnostic_card(self.rules,raw,0,'real-toxic',{'Green'})
        self.assertEqual(real.kind,'creature')
        self.assertEqual(real.event_definition.toxic,self.source().event_definition.toxic)
        self.assertEqual(real.event_definition.toxic,2)

    def test_group_combat_damage_loses_life_and_gets_fixed_poison(self):
        sim,source=self.fixture()
        sim.group_damage_step()
        self.assertEqual(sim.players[1].life,37)
        self.assertEqual(sim.players[1].poison_counters,2)
        self.assertEqual(sim.players[0].poison_counters,0)
        self.assertEqual(sim.state()['players'][1]['poisonCounters'],2)
        sim.invariant()

    def test_blocked_or_prevented_combat_adds_no_poison(self):
        sim,source=self.fixture()
        blocker=s.Card('blocker','New blocker','creature',power=1,toughness=4,
            traits='1;4;',event_definition=s.EventDefinition('New blocker',
                frozenset({'Creature'}),frozenset(),False,1,4,frozenset()),is_token=True)
        sim.players[1].battlefield.append(s.Permanent(blocker,fresh=False))
        sim.group_combat['blocks']={source.id:[blocker.id]}
        sim.group_combat['blocked']={source.id}
        sim.group_damage_step()
        self.assertEqual(sim.players[1].poison_counters,0)
        sim2,source2=self.fixture()
        sim2.combat_damage_prevented=True
        sim2.group_damage_step()
        self.assertEqual(sim2.players[1].poison_counters,0)
        sim.invariant();sim2.invariant()

    def test_legacy_strike_pipeline_and_poison_loss_condition(self):
        sim,source=self.fixture()
        sim.group_combat=None
        sim.combat_context=dict(attacker=source.id,blocker=None,early=set(),blocked=False)
        sim.players[1].poison_counters=9
        sim.strike_damage_step(False)
        self.assertEqual(sim.players[1].life,37)
        self.assertEqual(sim.players[1].poison_counters,11)
        sim.outcome()
        self.assertTrue(sim.finished)
        self.assertEqual(sim.winner,0)

    def test_toxic_number_is_not_damage_multiplier_and_unknown_text_rejected(self):
        changed=self.source(TEXT.replace('Toxic 2','Toxic 3').replace('two poison','three poison'))
        self.assertEqual(changed.event_definition.toxic,3)
        sim,card=self.fixture(changed)
        sim.group_damage_step()
        self.assertEqual(sim.players[1].life,37)
        self.assertEqual(sim.players[1].poison_counters,3)
        self.assertEqual(self.source(TEXT+' Draw a card.').kind,'unsupported')
        self.assertEqual(parse('Toxic 2',['Instant']),0)
        sim.invariant()


if __name__=='__main__':unittest.main()
