"""Generic per-token triggers: create, sacrifice, and distinct death/exile."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
from oracle_abilities import compile_abilities
import test_enchantment_abilities as fixtures

class TokenActionTriggersChecks(unittest.TestCase):
    setUpClass=classmethod(fixtures.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.EnchantmentChecks.tearDownClass.__func__)
    fixture=fixtures.EnchantmentChecks.fixture
    put=fixtures.EnchantmentChecks.put
    token=fixtures.EnchantmentChecks.token
    drain=fixtures.EnchantmentChecks.drain

    def create(self,sim,seat=0,count=2):
        event=dict(operation='create_tokens',effect='create tokens',source='external',
                   name='Unknown creator',controller=seat,
                   tokenSpec=dict(amount=count,power=1,toughness=1,
                      subtypes=['Squirrel'],colors=['Green'],keywords=[],tapped=False))
        sim._resolve_entry_effects([event],s.Card('external','Unknown creator','spell'))

    def test_real_mirkwood_bats_and_unknown_name_compile_without_ignoring_text(self):
        raw=dict(self.lookup['Mirkwood Bats'],name='Unfamiliar token watcher')
        result=s.import_diagnostic_card(self.rules,raw,0,'bat',{'Black'})
        self.assertEqual(result.kind,'creature')
        self.assertIn('flying',result.event_definition.abilities)
        self.assertEqual(result.event_definition.token_action_triggers,
                         (('create','opponent_loss',1),('sacrifice','opponent_loss',1)))
        raw['oracleText']+='\nWhenever a player flies, create something imaginary.'
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'bad',{'Black'}).kind,'unsupported')
        self.assertIsNone(compile_abilities('Whenever you create a token, you invent ten cards.'))

    def test_two_token_creation_events_queue_one_trigger_per_token(self):
        sim,cards=self.fixture(['Mirkwood Bats'])
        self.put(sim,cards['Mirkwood Bats'])
        self.create(sim,count=2)
        self.assertEqual(sim.players[1].life,40)
        self.assertEqual(len(sim.stack.items),2)
        self.drain(sim)
        self.assertEqual(sim.players[1].life,38)
        sim.invariant()

    def test_parallel_lives_doubling_is_counted_before_triggers(self):
        sim,cards=self.fixture(['Mirkwood Bats','Parallel Lives'])
        self.put(sim,cards['Mirkwood Bats'])
        self.put(sim,cards['Parallel Lives'])
        self.create(sim,count=2)
        self.assertEqual(len(sim.stack.items),4)
        self.drain(sim)
        self.assertEqual(sim.players[1].life,36)
        sim.invariant()

    def test_opponent_creating_tokens_does_not_trigger_own_bats(self):
        sim,cards=self.fixture(['Mirkwood Bats'])
        self.put(sim,cards['Mirkwood Bats'])
        self.create(sim,seat=1,count=3)
        self.assertFalse(sim.stack.items)
        self.assertEqual([p.life for p in sim.players],[40,40])
        sim.invariant()

    def test_two_watchers_trigger_independently(self):
        sim,cards=self.fixture(['Mirkwood Bats'])
        first=self.put(sim,cards['Mirkwood Bats'])
        second=s.Card('second-bat','Unfamiliar watcher','creature',power=2,toughness=3,
                      event_definition=first.card.event_definition,is_token=True)
        sim.enter_creature(second,sim.players[0])
        self.create(sim,count=2)
        self.assertEqual(len(sim.stack.items),4)
        self.drain(sim)
        self.assertEqual(sim.players[1].life,36)
        sim.invariant()

    def test_trigger_stays_queued_after_watcher_leaves(self):
        sim,cards=self.fixture(['Mirkwood Bats'])
        watcher=self.put(sim,cards['Mirkwood Bats'])
        self.create(sim,count=2)
        sim.send_to_destination(sim.players[0],watcher)
        self.drain(sim)
        self.assertEqual(sim.players[1].life,38)
        sim.invariant()

    def test_token_sacrifice_is_distinct_from_token_destruction(self):
        sim,cards=self.fixture(['Mirkwood Bats'])
        self.put(sim,cards['Mirkwood Bats'])
        one=self.token(sim,'first')
        two=self.token(sim,'second')
        sim.send_to_destination(sim.players[0],one)  # Not a sacrifice.
        self.assertFalse(sim.stack.items)
        sim.sacrifice_token(0,two.card.id)  # Internal helper after validated cost.
        self.assertFalse(any(p.card.id==two.card.id for p in sim.players[0].battlefield))
        self.assertEqual(len(sim.stack.items),1)
        self.drain(sim)
        self.assertEqual(sim.players[1].life,39)
        sim.invariant()

    def test_sacrifice_has_no_free_legal_action_and_non_token_is_rejected(self):
        sim,cards=self.fixture(['Mirkwood Bats'])
        watcher=self.put(sim,cards['Mirkwood Bats'])
        with self.assertRaisesRegex(ValueError,'controlled token'):
            sim.sacrifice_token(0,watcher.card.id)
        with self.assertRaisesRegex(ValueError,'controlled token'):
            sim.sacrifice_token(1,watcher.card.id)
        self.assertFalse(any('sacrifice_token'==candidate.kind for candidate in sim.legal(0)))
        sim.invariant()

    def test_token_creature_death_triggers_can_coexist_with_sacrifice(self):
        sim,cards=self.fixture(['Mirkwood Bats'])
        self.put(sim,cards['Mirkwood Bats'])
        squirrel=self.token(sim,'squirrel',subtypes=('Squirrel',))
        sim.sacrifice_token(0,squirrel.card.id)
        self.assertEqual(len(sim.stack.items),1)
        self.drain(sim)
        self.assertEqual(sim.players[1].life,39)
        sim.invariant()

    def test_token_spell_dispatches_creation_events_on_stack(self):
        sim,cards=self.fixture(['Mirkwood Bats'])
        self.put(sim,cards['Mirkwood Bats'])
        definition=s.EventDefinition('Wolf',frozenset({'Creature'}),frozenset({'Wolf'}),
                                     False,2,2,frozenset())
        spell=s.Card('unseen-spell','Unseen wolf pack','token_spell',
                     mana_cost='{0}',token_count=3,token_definition=definition,
                     printed_types=('Sorcery',))
        sim.players[0].hand.append(spell)
        sim.card_owners[spell.id]=0
        sim.total_cards=tuple(n+(i==0) for i,n in enumerate(sim.total_cards))
        sim.cast_spell(0,spell)
        self.assertEqual(sim.players[1].life,40)
        self.drain(sim)
        self.assertEqual(sim.players[1].life,37)
        self.assertEqual(sum(p.card.name=='Wolf' for p in sim.players[0].battlefield),3)
        sim.invariant()

    def test_role_token_creation_is_counted_by_same_event_rule(self):
        sim,cards=self.fixture(['Mirkwood Bats','Ellivere of the Wild Court'])
        self.put(sim,cards['Mirkwood Bats'])
        self.token(sim,'role-host')
        self.put(sim,cards['Ellivere of the Wild Court'])
        self.drain(sim)
        self.assertEqual(sim.players[1].life,39)
        roles=[p for p in sim.players[0].battlefield if
               p.card.event_definition and p.card.event_definition.role]
        self.assertEqual(len(roles),1)
        sim.invariant()

    def test_zero_created_tokens_does_not_trigger_and_noncreature_token_counts(self):
        sim,cards=self.fixture(['Mirkwood Bats'])
        self.put(sim,cards['Mirkwood Bats'])
        self.create(sim,count=0)
        self.assertFalse(sim.stack.items)
        game=sim.event_game('main')
        self.assertEqual(game.token_action_events('create',0,0),[])
        self.assertEqual(len(game.token_action_events('create',0,3)),3)
        sim.invariant()
