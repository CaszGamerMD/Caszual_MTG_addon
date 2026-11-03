"""Great Henge's composed self-cost, mana/life, and nontoken-entry abilities."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
import test_enchantment_abilities as fixtures


class GreatHengeChecks(unittest.TestCase):
    setUpClass=classmethod(fixtures.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.EnchantmentChecks.tearDownClass.__func__)
    fixture=fixtures.EnchantmentChecks.fixture
    put=fixtures.EnchantmentChecks.put
    token=fixtures.EnchantmentChecks.token
    drain=fixtures.EnchantmentChecks.drain

    def test_real_card_and_renamed_text_compose_all_three_fragments(self):
        raw=dict(self.lookup['The Great Henge'])
        card=s.import_diagnostic_card(self.rules,raw,0,'henge',{'Green'})
        self.assertEqual(card.kind,'artifact')
        definition=card.event_definition
        self.assertTrue(definition.self_greatest_power_cost_reduction)
        self.assertEqual(definition.scaled_mana_tap,'fixed:G:2')
        self.assertEqual(definition.scaled_mana_life_gain,2)
        self.assertEqual(len(definition.triggers),1)
        trigger=definition.triggers[0]
        self.assertEqual((trigger.event,trigger.subject.relation,
                          trigger.subject.creature,trigger.subject.nontoken),
                         ('enters','controller',True,True))
        self.assertEqual(trigger.effect.operation,'ordered_effects')
        self.assertEqual([step.operation for step in trigger.effect.steps],
                         ['entered_counter','draw_cards'])

        raw['name']='Unknown Green Artifact'
        renamed=s.import_diagnostic_card(self.rules,raw,0,'renamed',{'Green'})
        self.assertEqual(renamed.kind,'artifact')
        raw['oracleText']+='\nGain an extra turn.'
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'bad',{'Green'}).kind,
                         'unsupported')

    def test_self_cost_reduction_uses_live_greatest_power(self):
        sim,cards=self.fixture(['The Great Henge'])
        creature=self.token(sim,'power-test',power=4,toughness=4)
        plan=sim.payment(cards['The Great Henge'],seat=0)
        self.assertTrue(plan['paid'])
        self.assertEqual(len(plan['sources']),5)

        creature.temporary_power=2
        plan=sim.payment(cards['The Great Henge'],seat=0)
        self.assertTrue(plan['paid'])
        self.assertEqual(len(plan['sources']),3)
        sim.invariant()

    def test_negative_greatest_power_does_not_increase_cost(self):
        sim,cards=self.fixture(['The Great Henge'])
        creature=self.token(sim,'negative-power',power=1,toughness=2)
        creature.temporary_power=-3
        plan=sim.payment(cards['The Great Henge'],seat=0)
        self.assertTrue(plan['paid'])
        self.assertEqual(len(plan['sources']),9)  # A negative greatest power is no reduction.
        sim.invariant()

    def test_artifact_tap_adds_two_green_and_gains_two_life(self):
        sim,cards=self.fixture(['The Great Henge'])
        source=self.put(sim,cards['The Great Henge'])
        self.assertEqual(sim.players[0].life,40)
        sim.activate_scaled_mana(0,source.card.id,4)
        self.assertTrue(source.tapped)
        self.assertEqual(sim.players[0].mana_pool[4],2)
        self.assertEqual(sim.players[0].life,42)
        sim.invariant()

    def test_only_nontoken_entries_trigger_and_effect_targets_that_creature(self):
        sim,cards=self.fixture(['The Great Henge','Elvish Mystic'])
        self.put(sim,cards['The Great Henge'])
        player=sim.players[0]

        token_definition=s.EventDefinition('Test token',frozenset({'Creature'}),
            frozenset({'Elf'}),False,1,1,frozenset())
        token=s.Card('henge-token','Test token','creature','{0}',power=1,toughness=1,
                     event_definition=token_definition,is_token=True)
        token_triggers=sim.enter_creature(token,player)
        sim.resolve_entry_triggers(token_triggers,token)
        self.assertFalse(sim.stack.items)

        creature=cards['Elvish Mystic']
        player.hand.remove(creature)
        before_hand=len(player.hand)
        pending=sim.enter_creature(creature,player)
        sim.resolve_entry_triggers(pending,creature)
        entered=next(p for p in player.battlefield if p.card.id==creature.id)
        self.assertEqual(entered.counters,0)
        self.assertEqual(len(sim.stack.items),1)
        self.drain(sim)
        self.assertEqual(entered.counters,1)
        self.assertEqual(len(player.hand),before_hand+1)
        sim.invariant()

    def test_old_entry_trigger_does_not_counter_same_card_after_reentry(self):
        sim,cards=self.fixture(['The Great Henge','Elvish Mystic'])
        self.put(sim,cards['The Great Henge'])
        player=sim.players[0]
        creature=cards['Elvish Mystic']
        player.hand.remove(creature)

        first_pending=sim.enter_creature(creature,player)
        first_entry=next(p for p in player.battlefield if p.card.id==creature.id).entered_at
        sim.resolve_entry_triggers(first_pending,creature)
        self.assertEqual(len(sim.stack.items),1)

        # The first trigger still resolves, but its "it" is the object from
        # the first entry. Move that object away before the ability resolves.
        first_object=next(p for p in player.battlefield if p.card.id==creature.id)
        sim.send_to_destination(player,first_object)
        self.assertTrue(any(c.id==creature.id for c in player.graveyard))

        # Re-enter the same physical card (same id, new battlefield object).
        player.graveyard.remove(creature)
        player.hand.append(creature)
        player.hand.remove(creature)
        second_pending=sim.enter_creature(creature,player)
        second_object=next(p for p in player.battlefield if p.card.id==creature.id)
        self.assertNotEqual(second_object.entered_at,first_entry)
        sim.resolve_entry_triggers(second_pending,creature)
        self.assertEqual(len(sim.stack.items),2)

        before_hand=len(player.hand)
        self.drain(sim)
        self.assertEqual(second_object.counters,1)
        self.assertEqual(len(player.hand),before_hand+2)
        sim.invariant()

    def test_queued_entry_trigger_survives_henge_leaving(self):
        sim,cards=self.fixture(['The Great Henge','Elvish Mystic'])
        henge=self.put(sim,cards['The Great Henge'])
        player=sim.players[0]
        creature=cards['Elvish Mystic']
        player.hand.remove(creature)
        pending=sim.enter_creature(creature,player)
        sim.resolve_entry_triggers(pending,creature)
        self.assertEqual(len(sim.stack.items),1)
        sim.send_to_destination(player,henge)
        self.drain(sim)
        entered=next(p for p in player.battlefield if p.card.id==creature.id)
        self.assertEqual(entered.counters,1)
        sim.invariant()


if __name__=='__main__':
    unittest.main()
