"""Rules for opponent-entering creatures, life gain and tapped entry."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
import test_enchantment_abilities as base
from card_events import Game, Permanent as EventPermanent
from oracle_abilities import compile_abilities

class OpponentEntryChecks(unittest.TestCase):
    setUpClass=classmethod(base.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(base.EnchantmentChecks.tearDownClass.__func__)
    fixture=base.EnchantmentChecks.fixture
    put=base.EnchantmentChecks.put
    drain=base.EnchantmentChecks.drain

    def with_authority(self):
        sim,cards=self.fixture(['Authority of the Consuls'])
        source=self.put(sim,cards['Authority of the Consuls'])
        self.assertTrue(source.card.event_definition.opponent_creatures_enter_tapped)
        return sim,source

    def creature(self,identifier,seat):
        return s.Card(identifier,identifier,'creature',mana_cost='{0}',
                      traits='2;2;',power=2,toughness=2,is_token=True,
                      printed_types=('Creature',))

    def test_metadata_and_new_name_acceptance_but_unknown_text_rejected(self):
        raw=dict(self.lookup['Authority of the Consuls'])
        raw['name']='Unfamiliar entry law'
        parsed=s.import_diagnostic_card(self.rules,raw,0,'law',{'White'})
        self.assertEqual(parsed.kind,'enchantment')
        self.assertTrue(parsed.event_definition.opponent_creatures_enter_tapped)
        self.assertTrue(any(trigger.event=='enters' for trigger in parsed.event_definition.triggers))
        raw['oracleText']+='\nWhenever a mouse clicks, invent a trigger.'
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'invalid',{'White'}).kind,'unsupported')

    def test_opponent_creature_enters_tapped_and_creates_life_trigger(self):
        sim,_=self.with_authority()
        enemy=self.creature('enemy',1)
        pending=sim.enter_creature(enemy,sim.players[1])
        sim.resolve_entry_triggers(pending,enemy)
        item=next(p for p in sim.players[1].battlefield if p.card.id==enemy.id)
        self.assertTrue(item.tapped)
        self.assertEqual(sim.players[0].life,40)
        self.assertEqual(len(sim.stack.items),1)
        self.drain(sim)
        self.assertEqual(sim.players[0].life,41)
        self.assertEqual(sim.life_gained_turn[0],1)
        sim.invariant()

    def test_own_creature_not_tapped_and_no_trigger(self):
        sim,_=self.with_authority()
        ally=self.creature('ally',0)
        pending=sim.enter_creature(ally,sim.players[0])
        sim.resolve_entry_triggers(pending,ally)
        item=next(p for p in sim.players[0].battlefield if p.card.id==ally.id)
        self.assertFalse(item.tapped)
        self.assertFalse(sim.stack.items)
        sim.invariant()

    def test_token_enters_tapped_and_stack_trigger_persists_after_source_dies(self):
        sim,authority=self.with_authority()
        enemy=self.creature('enemy-token',1)
        pending=sim.enter_creature(enemy,sim.players[1])
        sim.resolve_entry_triggers(pending,enemy)
        sim.send_to_destination(sim.players[0],authority)
        self.assertTrue(next(p for p in sim.players[1].battlefield if p.card.id==enemy.id).tapped)
        self.drain(sim)
        self.assertEqual(sim.players[0].life,41)
        future=self.creature('future',1)
        more=sim.enter_creature(future,sim.players[1])
        sim.resolve_entry_triggers(more,future)
        self.assertFalse(next(p for p in sim.players[1].battlefield if p.card.id==future.id).tapped)
        sim.invariant()

    def test_simultaneous_entry_does_not_apply_nonexistent_replacement(self):
        sim,_=self.fixture(['Authority of the Consuls'])
        authority=sim.players[0].hand[0]
        d=authority.event_definition
        creature=s.EventDefinition('New creature',frozenset({'Creature'}),frozenset(),
                                   False,2,2,frozenset())
        game=Game()
        law=EventPermanent('law',d,0)
        opponent=EventPermanent('opponent',creature,1)
        game.enter_batch([law,opponent])
        self.assertFalse(opponent.tapped)
        # Trigger does see the simultaneous entry after both exist.
        self.assertTrue(any(e.get('operation')=='gain_life' and e.get('source')=='law'
                            for e in game.events if e.get('kind')=='trigger'))

    def test_multiple_authorities_have_independent_triggers_not_double_tap(self):
        sim,cards=self.fixture(['Authority of the Consuls'])
        law=self.put(sim,cards['Authority of the Consuls'])
        extra=s.Card('second-law',law.card.name,'enchantment',
                     event_definition=law.card.event_definition,is_token=True)
        sim.enter_creature(extra,sim.players[0])
        victim=self.creature('victim',1)
        pending=sim.enter_creature(victim,sim.players[1])
        sim.resolve_entry_triggers(pending,victim)
        self.assertTrue(next(p for p in sim.players[1].battlefield if p.card.id=='victim').tapped)
        self.assertEqual(len(sim.stack.items),2)
        self.drain(sim)
        self.assertEqual(sim.players[0].life,42)
        sim.invariant()
