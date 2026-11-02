"""Each-upkeep tokens combined with subtype-entry toughness life gain."""
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
from upkeep_token_entry_life import parse


TEXT=('At the beginning of each upkeep, create a 1/1 green Elf Warrior creature token.\n'
      'Whenever another Elf you control enters, you gain life equal to its toughness.')


class UpkeepTokenEntryLifeChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.rules=s.RulesBridge()
    @classmethod
    def tearDownClass(cls):cls.rules.close()

    def source(self,text=TEXT,name='Unfamiliar grove riders'):
        raw=dict(name=name,layout='normal',types=['Creature'],subTypes=['Elf','Warrior'],
                 superTypes=[],manaCost='{4}{G}{G}',colors=['Green'],power='4',toughness='4',
                 oracleText=text)
        return s.import_diagnostic_card(self.rules,raw,0,'grove-'+name,{'Green'})

    def creature(self,identifier,subtypes,power=2,toughness=3):
        definition=s.EventDefinition(identifier,frozenset({'Creature'}),frozenset(subtypes),
            False,power,toughness,frozenset())
        return s.Card(identifier,identifier,'creature',power=power,toughness=toughness,
                      traits=f'{power};{toughness};',event_definition=definition,is_token=True)

    def fixture(self,source=None):
        source=source or self.source()
        sim=s.Simulator(self.rules,37,decks=(s.demo_deck(0)+[source],s.demo_deck(1)),
                        diagnostic=True)
        self.assertFalse(sim.finished,sim.questions)
        owner=sim.players[0]
        (owner.hand if source in owner.hand else owner.library).remove(source)
        owner.battlefield.append(s.Permanent(source))
        sim.manual_priority=True;sim.phase='main'
        return sim,source

    def test_real_wolverine_riders_matches_unfamiliar_renamed_card(self):
        deck=json.loads((Path(__file__).resolve().parents[1]/'decks/14435337-lupitas-elves.json').read_text())
        raw=next(c for c in deck['mainboard'] if c['name']=='Wolverine Riders')
        real=s.import_diagnostic_card(self.rules,raw,0,'real-riders',{'Green'})
        self.assertEqual(real.kind,'creature')
        self.assertEqual(real.event_definition.upkeep_token_entry_life,
                         self.source().event_definition.upkeep_token_entry_life)

    def test_both_players_upkeep_create_controlled_elf_tokens_and_trigger_life(self):
        sim,source=self.fixture()
        for seat in (0,1):
            sim.active=seat;sim.stack.active=seat;sim.stack.priority=seat
            events=[e for e in sim.event_game('upkeep').upkeep_triggers()
                    if e.get('effect')=='create tokens at beginning of each upkeep']
            self.assertEqual(len(events),1)
            self.assertEqual(events[0]['controller'],0)
            sim._resolve_entry_effects(events,source)
            token=[p for p in sim.players[0].battlefield if p.card.is_token]
            self.assertEqual(len(token),seat+1)
            self.assertEqual(token[-1].card.event_definition.subtypes,
                             frozenset({'Elf','Warrior'}))
            # The entry-life ability uses the ordinary trigger stack.
            self.assertTrue(any(frame.payload[0].get('operation')=='gain_life_entrant_toughness'
                                for frame in sim.stack.items))
            sim.pass_priority(seat);sim.pass_priority(1-seat)
        self.assertEqual(sim.players[0].life,42)
        self.assertEqual(sim.players[1].life,40)
        sim.invariant()

    def test_entry_life_uses_controller_subtype_and_current_toughness(self):
        sim,source=self.fixture()
        elf=self.creature('new-elf',['Elf'],toughness=3)
        pending=sim.enter_creature(elf,sim.players[0])
        event=next(e for e in pending if e.get('operation')=='gain_life_entrant_toughness')
        entrant=next(p for p in sim.players[0].battlefield if p.card.id==elf.id)
        entrant.counters=2
        sim._resolve_entry_effects([event],source)
        self.assertEqual(sim.players[0].life,45)
        sim.enter_creature(self.creature('opponent-elf',['Elf']),sim.players[1])
        sim.enter_creature(self.creature('owner-goblin',['Goblin']),sim.players[0])
        self.assertEqual(sim.players[0].life,45)
        sim.invariant()

    def test_trigger_survives_entrant_death_using_last_known_toughness(self):
        sim,source=self.fixture()
        elf=self.creature('departing-elf',['Elf'],toughness=4)
        pending=sim.enter_creature(elf,sim.players[0])
        event=next(e for e in pending if e.get('operation')=='gain_life_entrant_toughness')
        sim.send_to_destination(sim.players[0],next(p for p in sim.players[0].battlefield
                                                      if p.card.id==elf.id))
        sim._resolve_entry_effects([event],source)
        self.assertEqual(sim.players[0].life,44)
        sim.invariant()

    def test_variable_token_and_subtype_and_fail_closed_unknown_sentence(self):
        different=TEXT.replace('1/1 green Elf Warrior','2/3 green Goblin Warrior').replace(
            'another Elf','another Goblin')
        changed=self.source(different,name='Unknown Goblin shepherd')
        self.assertEqual(changed.kind,'creature')
        program=changed.event_definition.upkeep_token_entry_life
        self.assertEqual((program.token.power,program.token.toughness),(2,3))
        self.assertEqual(program.entry_subtype,'Goblin')
        self.assertEqual(self.source(TEXT+' Draw a card.').kind,'unsupported')
        self.assertIsNone(parse(TEXT,['Enchantment']))


if __name__=='__main__':unittest.main()
