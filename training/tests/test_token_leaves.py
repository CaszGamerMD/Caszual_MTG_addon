"""Token leaves battlefield: sacrifice, destruction and exile share one trigger."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
from oracle_abilities import compile_abilities
import test_enchantment_abilities as fixtures

class TokenLeaveChecks(unittest.TestCase):
    setUpClass=classmethod(fixtures.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.EnchantmentChecks.tearDownClass.__func__)
    fixture=fixtures.EnchantmentChecks.fixture
    put=fixtures.EnchantmentChecks.put
    token=fixtures.EnchantmentChecks.token
    drain=fixtures.EnchantmentChecks.drain

    def test_real_nadier_and_unseen_name_compile_whole_text(self):
        raw=dict(self.lookup["Nadier's Nightblade"],name='Unknown departing-token watcher')
        card=s.import_diagnostic_card(self.rules,raw,0,'nightblade',{'Black'})
        self.assertEqual(card.kind,'creature')
        self.assertEqual(card.event_definition.token_leave_triggers,
                         (('opponent_loss_gain',1,1),))
        raw['oracleText']+='\nMake one imaginary extra spell.'
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'bad',{'Black'}).kind,'unsupported')
        self.assertIsNone(compile_abilities('Whenever a token leaves your control, you gain unlimited mana.'))

    def test_sacrifice_token_queues_drain_after_token_leaves(self):
        sim,cards=self.fixture(["Nadier's Nightblade"])
        self.put(sim,cards["Nadier's Nightblade"])
        squirrel=self.token(sim,'squirrel')
        sim.sacrifice_token(0,squirrel.card.id)
        self.assertFalse(any(p.card.id==squirrel.card.id for p in sim.players[0].battlefield))
        self.assertEqual([p.life for p in sim.players],[40,40])
        self.assertEqual(len(sim.stack.items),1)
        self.drain(sim)
        self.assertEqual([p.life for p in sim.players],[41,39])
        sim.invariant()

    def test_destroy_token_is_leaving_not_sacrificing(self):
        sim,cards=self.fixture(["Nadier's Nightblade",'Mirkwood Bats'])
        self.put(sim,cards["Nadier's Nightblade"])
        self.put(sim,cards['Mirkwood Bats'])
        squirrel=self.token(sim,'squirrel')
        sim.destroy_batch(((0,squirrel),),cards['Mirkwood Bats'])
        self.assertEqual(len(sim.stack.items),1)
        self.drain(sim)
        self.assertEqual([p.life for p in sim.players],[41,39])
        sim.invariant()

    def test_sacrifice_queues_both_token_action_and_token_leave_triggers(self):
        sim,cards=self.fixture(["Nadier's Nightblade",'Mirkwood Bats'])
        self.put(sim,cards["Nadier's Nightblade"])
        self.put(sim,cards['Mirkwood Bats'])
        squirrel=self.token(sim,'squirrel')
        sim.sacrifice_token(0,squirrel.card.id)
        self.assertEqual(len(sim.stack.items),2)
        self.drain(sim)
        self.assertEqual([p.life for p in sim.players],[41,38])
        sim.invariant()

    def test_opponent_token_leaving_does_not_trigger_my_nightblade(self):
        sim,cards=self.fixture(["Nadier's Nightblade"])
        self.put(sim,cards["Nadier's Nightblade"])
        enemy=self.token(sim,'enemy',seat=1)
        sim.destroy_batch(((1,enemy),),cards["Nadier's Nightblade"])
        self.assertFalse(sim.stack.items)
        self.assertEqual([p.life for p in sim.players],[40,40])
        sim.invariant()

    def test_nontoken_creature_dying_does_not_count(self):
        sim,cards=self.fixture(["Nadier's Nightblade"])
        self.put(sim,cards["Nadier's Nightblade"])
        definition=s.EventDefinition('normal',frozenset({'Creature'}),frozenset(),False,2,2,frozenset())
        card=s.Card('normal','normal','creature',power=2,toughness=2,
                    traits='2;2;',event_definition=definition,printed_types=('Creature',))
        sim.players[0].library.append(card)
        sim.card_owners[card.id]=0
        sim.total_cards=tuple(n+(i==0) for i,n in enumerate(sim.total_cards))
        sim.players[0].library.remove(card)
        sim.enter_creature(card,sim.players[0])
        permanent=next(p for p in sim.players[0].battlefield if p.card.id=='normal')
        sim.destroy_batch(((0,permanent),),card)
        self.assertFalse(sim.stack.items)
        self.assertEqual([p.life for p in sim.players],[40,40])
        sim.invariant()

    def test_token_exiled_by_swords_counts_as_leaving_without_sacrifice(self):
        sim,cards=self.fixture(["Nadier's Nightblade",'Mirkwood Bats','Swords to Plowshares'])
        self.put(sim,cards["Nadier's Nightblade"])
        self.put(sim,cards['Mirkwood Bats'])
        target=self.token(sim,'squirrel',power=2,toughness=2)
        sim.cast_spell(0,cards['Swords to Plowshares'],target=target.card.id)
        self.drain(sim)
        self.assertFalse(any(p.card.id==target.card.id for p in sim.players[0].battlefield))
        self.assertEqual([p.life for p in sim.players],[43,39])
        sim.invariant()

    def test_aura_role_token_and_host_both_leaving_are_counted(self):
        sim,cards=self.fixture(["Nadier's Nightblade",'Ellivere of the Wild Court'])
        self.put(sim,cards["Nadier's Nightblade"])
        host=self.token(sim,'host',power=9,toughness=9)
        self.put(sim,cards['Ellivere of the Wild Court'])
        self.drain(sim)
        roles=[p for p in sim.players[0].battlefield
               if p.card.event_definition and p.card.event_definition.role]
        self.assertEqual(len(roles),1)
        sim.send_to_destination(sim.players[0],host)
        sim.resolve_entry_triggers([],host.card)
        self.assertEqual(len(sim.stack.items),2)
        self.drain(sim)
        self.assertEqual([p.life for p in sim.players],[42,38])
        self.assertFalse(any(p.card.event_definition and p.card.event_definition.role
                             for p in sim.players[0].battlefield))
        sim.invariant()

    def test_life_replacement_modifies_nightblade_gain_but_not_loss(self):
        sim,cards=self.fixture(["Nadier's Nightblade",'Boon Reflection'])
        self.put(sim,cards["Nadier's Nightblade"])
        self.put(sim,cards['Boon Reflection'])
        target=self.token(sim,'squirrel')
        sim.sacrifice_token(0,target.card.id)
        self.drain(sim)
        self.assertEqual([p.life for p in sim.players],[42,39])
        self.assertEqual(sim.life_gained_turn[0],2)
        sim.invariant()

    def test_two_tokens_destroyed_together_queue_separate_triggers(self):
        sim,cards=self.fixture(["Nadier's Nightblade"])
        self.put(sim,cards["Nadier's Nightblade"])
        first=self.token(sim,'first')
        second=self.token(sim,'second')
        sim.destroy_batch(((0,first),(0,second)),cards["Nadier's Nightblade"])
        self.assertEqual(len(sim.stack.items),2)
        self.drain(sim)
        self.assertEqual([p.life for p in sim.players],[42,38])
        sim.invariant()

    def test_watcher_leaving_does_not_undo_previously_queued_trigger(self):
        sim,cards=self.fixture(["Nadier's Nightblade"])
        watcher=self.put(sim,cards["Nadier's Nightblade"])
        target=self.token(sim,'squirrel')
        sim.sacrifice_token(0,target.card.id)
        sim.send_to_destination(sim.players[0],watcher)
        self.drain(sim)
        self.assertEqual([p.life for p in sim.players],[41,39])
        sim.invariant()
