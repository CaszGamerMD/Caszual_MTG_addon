"""Creature-entry optional mana triggered by shared creature types."""
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
from shared_type_mana import parse


TEXT=('Whenever a creature enters, you may add an amount of {C} equal to '
      'the number of creatures you control that share a creature type with it.')


class SharedTypeManaChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.rules=s.RulesBridge()
    @classmethod
    def tearDownClass(cls):cls.rules.close()

    def enchantment(self,text=TEXT,name='Unknown tribal resonance'):
        raw=dict(name=name,layout='normal',types=['Enchantment'],subTypes=[],
                 superTypes=[],manaCost='{2}{R}{R}',colors=['Red'],oracleText=text)
        return s.import_diagnostic_card(self.rules,raw,0,'resonance-'+name,{'Red'})

    def fixture(self):
        source=self.enchantment()
        sim=s.Simulator(self.rules,83,decks=(s.demo_deck(0)+[source],s.demo_deck(1)),
                        diagnostic=True)
        self.assertFalse(sim.finished,sim.questions)
        owner=sim.players[0]
        (owner.hand if source in owner.hand else owner.library).remove(source)
        owner.battlefield.append(s.Permanent(source))
        sim.manual_priority=True;sim.phase='main'
        return sim,source

    def creature(self,identifier,subtypes,changeling=False):
        definition=s.EventDefinition(identifier,frozenset({'Creature'}),
            frozenset(subtypes),False,1,1,
            frozenset({'changeling'}) if changeling else frozenset())
        return s.Card(identifier,identifier,'creature',power=1,toughness=1,
                      printed_types=frozenset({'Creature'}),event_definition=definition,
                      is_token=True)

    def trigger(self,sim,card,seat):
        pending=sim.enter_creature(card,sim.players[seat])
        matching=[e for e in pending if e.get('operation')=='shared_type_mana']
        self.assertEqual(len(matching),1)
        return matching[0]

    def test_real_mana_echoes_and_renamed_text_compile_identically(self):
        deck=json.loads((Path(__file__).resolve().parents[1]/'decks/14509839-mono-red-gobs.json').read_text())
        raw=next(c for c in deck['mainboard'] if c['name']=='Mana Echoes')
        real=s.import_diagnostic_card(self.rules,raw,0,'actual-echoes',{'Red'})
        self.assertEqual(real.kind,'enchantment')
        self.assertEqual(real.event_definition.shared_type_mana,
                         self.enchantment().event_definition.shared_type_mana)

    def test_opponents_creature_entry_counts_only_controllers_matching_creatures(self):
        sim,source=self.fixture()
        a=self.creature('own-goblin-a',['Goblin'])
        b=self.creature('own-goblin-b',['Goblin'])
        for card in (a,b):sim.enter_creature(card,sim.players[0])
        other=self.creature('other-goblin',['Goblin'])
        event=self.trigger(sim,other,1)
        sim._resolve_entry_effects([event],source)
        self.assertEqual(sim.players[0].mana_pool[5],2)
        self.assertEqual(sim.players[1].mana_pool[5],0)
        sim.invariant()

    def test_self_entry_included_and_creature_type_changelings_match(self):
        sim,source=self.fixture()
        gob=self.creature('gob',['Goblin'])
        elf=self.creature('elf',['Elf'])
        sim.enter_creature(gob,sim.players[0])
        sim.enter_creature(elf,sim.players[0])
        change=self.creature('change',['Shapeshifter'],changeling=True)
        event=self.trigger(sim,change,0)
        sim._resolve_entry_effects([event],source)
        self.assertEqual(sim.players[0].mana_pool[5],3)
        sim.invariant()

    def test_count_evaluates_at_resolution_and_handles_departed_entry_source(self):
        sim,source=self.fixture()
        first=self.creature('gob-first',['Goblin'])
        second=self.creature('gob-second',['Goblin'])
        sim.enter_creature(first,sim.players[0])
        event=self.trigger(sim,second,1)
        late=self.creature('late-gob',['Goblin'])
        sim.enter_creature(late,sim.players[0])
        departing=next(p for p in sim.players[1].battlefield if p.card.id==second.id)
        sim.send_to_destination(sim.players[1],departing)
        sim._resolve_entry_effects([event],source)
        self.assertEqual(sim.players[0].mana_pool[5],2)
        sim.invariant()

    def test_nonsharing_creature_produces_zero_and_unknown_clause_rejects(self):
        sim,source=self.fixture()
        sim.enter_creature(self.creature('elf',['Elf']),sim.players[0])
        event=self.trigger(sim,self.creature('goblin',['Goblin']),1)
        sim._resolve_entry_effects([event],source)
        self.assertEqual(sim.players[0].mana_pool[5],0)
        self.assertEqual(self.enchantment(TEXT+' Draw a card.').kind,'unsupported')
        self.assertIsNone(parse(TEXT,['Creature']))
        sim.invariant()


if __name__=='__main__':unittest.main()
