"""Saved teaching-deck Oracle families tested as executable reusable blocks."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from card_events import parse_card
import simulator as s
import test_enchantment_abilities as fixtures


class TeachingDeckCompletionCycles(unittest.TestCase):
    setUpClass=classmethod(fixtures.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.EnchantmentChecks.tearDownClass.__func__)
    fixture=fixtures.EnchantmentChecks.fixture
    put=fixtures.EnchantmentChecks.put
    token=fixtures.EnchantmentChecks.token
    drain=fixtures.EnchantmentChecks.drain
    ready=fixtures.EnchantmentChecks.ready

    def raw(self,name):return dict(self.lookup[name])

    def advance_phase(self,sim):
        sim.phase='attack';sim.stack.priority=sim.active
        with patch.object(sim,'decide',return_value=s.Candidate(
                'pass','pass',features=s.features(**{'pass':1}))):
            sim.step()
        self.assertEqual(sim.phase,'second_main')

    def test_cycle_one_unspent_green_mana_persists_and_scales_live_stats(self):
        raw=self.raw('Omnath, Locus of Mana')
        definition=parse_card(raw)
        self.assertTrue(definition.supported,definition.reason)
        self.assertEqual(definition.unspent_mana_rule,('G',1,1,'G'))
        sim,cards=self.fixture(['Omnath, Locus of Mana'])
        source=self.put(sim,cards['Omnath, Locus of Mana'])
        owner=sim.players[0]
        owner.mana_pool[4]=3;owner.mana_pool[1]=2
        sim.players[1].mana_pool[4]=7
        self.assertEqual((sim.effective_card(source).power,sim.effective_card(source).toughness),(4,4))
        self.advance_phase(sim)
        self.assertEqual(owner.mana_pool,[0,0,0,0,3,0])
        self.assertEqual(sim.players[1].mana_pool,[0]*6)
        self.assertEqual(sim.effective_card(source).power,4)
        sim.send_to_destination(owner,source)
        self.advance_phase(sim)
        self.assertEqual(owner.mana_pool,[0]*6)
        sim.invariant()

    def test_cycle_one_renamed_color_and_multiplier_fail_closed(self):
        raw=self.raw('Omnath, Locus of Mana')
        raw['name']='Unseen Blue Channeler'
        raw['oracleText']=("You don't lose unspent blue mana as steps and phases end.\n"
                           'This creature gets +2/+3 for each unspent blue mana you have.')
        self.assertEqual(parse_card(raw).unspent_mana_rule,('U',2,3,'U'))
        self.assertFalse(parse_card(dict(raw,oracleText=raw['oracleText']+'\nYou win the game.')).supported)
        self.assertFalse(parse_card(dict(raw,power=None)).supported)
        self.assertFalse(parse_card(dict(raw,types=['Enchantment'])).supported)
        self.assertFalse(parse_card(dict(raw,oracleText=raw['oracleText'].replace('unspent blue mana you have','unspent green mana you have. Draw seven cards'))).supported)

    def test_cycle_two_equipped_hit_creates_wolf_then_mills_damaged_player(self):
        raw=self.raw('Sword of Body and Mind')
        definition=parse_card(raw)
        self.assertTrue(definition.supported,definition.reason)
        self.assertEqual(definition.attachment[2],frozenset({'protection from green','protection from blue'}))
        self.assertEqual(definition.attachment[3:5],(2,2))
        self.assertEqual([(op,number) for op,number,_ in definition.equipped_player_hit_steps],
                         [('create_tokens',1),('mill_damaged_player',10)])
        sim,cards=self.fixture(['Sword of Body and Mind'])
        host=self.token(sim,'attacker',power=2,toughness=2)
        sword=self.put(sim,cards['Sword of Body and Mind'])
        sim.activate_equip(0,sword.card.id,host.card.id);self.drain(sim)
        equipped=sim.event_game('main').battlefield[host.card.id]
        for keyword in ('protection from green','protection from blue'):
            self.assertTrue(sim.event_game('main').has(equipped,keyword))
        self.assertEqual(sim.effective_card(host).power,4)
        self.ready(sim);sim.declare_attackers([host.card.id]);sim.declare_blockers({})
        target=sim.players[1]
        library_before=len(target.library)
        grave_before=len(target.graveyard)
        sim.group_damage_step()
        self.assertTrue(any(item.payload[0].get('operation')=='equipment_hit_sequence'
                            for item in sim.stack.items))
        self.assertEqual(len(target.library),library_before)
        self.assertFalse(any(item.card.name=='Wolf' for item in sim.players[0].battlefield))
        sim.send_to_destination(sim.players[0],sword)
        self.drain(sim)
        wolves=[item for item in sim.players[0].battlefield if item.card.name=='Wolf']
        self.assertEqual(len(wolves),1)
        self.assertEqual((wolves[0].card.event_definition.power,wolves[0].card.event_definition.toughness),(2,2))
        self.assertEqual(wolves[0].card.event_definition.colors,frozenset({'Green'}))
        self.assertEqual(len(target.library),library_before-10)
        self.assertEqual(len(target.graveyard),grave_before+10)
        sim.invariant()

    def test_cycle_two_renamed_equipment_and_extra_instruction_fail_closed(self):
        raw=self.raw('Sword of Body and Mind')
        raw['name']='Invented Verdant and Cerulean Blade'
        raw['oracleText']=raw['oracleText'].replace('mills ten cards','mills seven cards')
        definition=parse_card(raw)
        self.assertTrue(definition.supported,definition.reason)
        self.assertEqual(definition.equipped_player_hit_steps[1][:2],('mill_damaged_player',7))
        self.assertFalse(parse_card(dict(raw,oracleText=raw['oracleText']+'\nYou win the game.')).supported)
        self.assertFalse(parse_card(dict(raw,oracleText=raw['oracleText'].replace('you create','you secretly create'))).supported)
        self.assertFalse(parse_card(dict(raw,oracleText=raw['oracleText'].replace('and from blue','and from purple'))).supported)

    def test_cycle_three_equipped_hit_discards_then_untaps_controller_lands(self):
        definition=parse_card(self.raw('Sword of Feast and Famine'))
        self.assertTrue(definition.supported,definition.reason)
        self.assertEqual(definition.attachment[2],frozenset({'protection from black','protection from green'}))
        self.assertEqual([(op,amount) for op,amount,_ in definition.equipped_player_hit_steps],
                         [('discard_damaged_player',1),('untap_controlled_lands',0)])
        sim,cards=self.fixture(['Sword of Feast and Famine'])
        host=self.token(sim,'attacker',power=3,toughness=3)
        sword=self.put(sim,cards['Sword of Feast and Famine'])
        sim.activate_equip(0,sword.card.id,host.card.id);self.drain(sim)
        for land in sim.players[0].battlefield:
            if land.card.kind=='land':land.tapped=True
        opponent_land_card=next(c for c in sim.players[1].library if c.kind=='land')
        sim.players[1].library.remove(opponent_land_card)
        opposing_land=s.Permanent(opponent_land_card)
        opposing_land.tapped=True
        sim.players[1].battlefield.append(opposing_land)
        damaged=sim.players[1]
        if not damaged.hand:damaged.hand.append(damaged.library.pop())
        hand_before=len(damaged.hand)
        grave_before=len(damaged.graveyard)
        self.ready(sim);sim.declare_attackers([host.card.id]);sim.declare_blockers({})
        sim.group_damage_step()
        self.assertEqual(len(damaged.hand),hand_before)
        self.assertTrue(all(item.tapped for item in sim.players[0].battlefield if item.card.kind=='land'))
        sim.send_to_destination(sim.players[0],sword)
        self.drain(sim)
        self.assertEqual(len(damaged.hand),hand_before-1)
        self.assertEqual(len(damaged.graveyard),grave_before+1)
        self.assertTrue(all(not item.tapped for item in sim.players[0].battlefield if item.card.kind=='land'))
        self.assertTrue(opposing_land.tapped)
        sim.invariant()

    def test_cycle_three_renamed_discard_two_and_unknown_clause_fail_closed(self):
        raw=self.raw('Sword of Feast and Famine')
        raw['name']='Unfamiliar Ebony and Moss Equipment'
        raw['oracleText']=raw['oracleText'].replace('discards a card','discards two cards')
        definition=parse_card(raw)
        self.assertTrue(definition.supported,definition.reason)
        self.assertEqual(definition.equipped_player_hit_steps[0][:2],('discard_damaged_player',2))
        self.assertFalse(parse_card(dict(raw,oracleText=raw['oracleText']+'\nPlayers skip their draw steps.')).supported)
        self.assertFalse(parse_card(dict(raw,oracleText=raw['oracleText'].replace('you untap all lands','you destroy all lands'))).supported)
        self.assertFalse(parse_card(dict(raw,oracleText=raw['oracleText'].replace('and from green','and from violet'))).supported)

    def test_cycle_four_equipped_hit_gains_life_and_targets_graveyard_before_stack(self):
        definition=parse_card(self.raw('Sword of Light and Shadow'))
        self.assertTrue(definition.supported,definition.reason)
        self.assertEqual(definition.attachment[2],frozenset({'protection from white','protection from black'}))
        self.assertEqual([(op,amount) for op,amount,_ in definition.equipped_player_hit_steps],
                         [('gain_controller_life',3),('return_optional_graveyard_creature',1)])
        for change_zone in (False,True):
            sim,cards=self.fixture(['Sword of Light and Shadow'])
            host=self.token(sim,'attacker')
            sword=self.put(sim,cards['Sword of Light and Shadow'])
            sim.activate_equip(0,sword.card.id,host.card.id);self.drain(sim)
            owner=sim.players[0]
            target=next(card for card in owner.library if card.kind=='creature')
            owner.library.remove(target)
            owner.graveyard.append(target)
            self.ready(sim);sim.declare_attackers([host.card.id]);sim.declare_blockers({})
            life_before=owner.life
            sim.group_damage_step()
            payload=next(item.payload[0] for item in sim.stack.items
                         if item.payload[0].get('operation')=='equipment_hit_sequence')
            self.assertEqual(payload['steps'][1]['targetCreatureId'],target.id)
            self.assertEqual(owner.life,life_before)
            if change_zone:
                owner.graveyard.remove(target)
                owner.hand.append(target)
            sim.send_to_destination(owner,sword)
            self.drain(sim)
            self.assertEqual(owner.life,life_before+3)
            self.assertIn(target,owner.hand)
            self.assertNotIn(target,owner.graveyard)
            self.assertEqual(owner.hand.count(target),1)
            sim.invariant()

    def test_cycle_four_declined_target_and_unfamiliar_amount_fail_closed(self):
        raw=self.raw('Sword of Light and Shadow')
        raw['name']='Strange Dawn and Dusk Equipment'
        raw['oracleText']=raw['oracleText'].replace('gain 3 life','gain 5 life')
        self.assertEqual(parse_card(raw).equipped_player_hit_steps[0][:2],('gain_controller_life',5))
        self.assertFalse(parse_card(dict(raw,oracleText=raw['oracleText']+'\nSacrifice an artifact.')).supported)
        self.assertFalse(parse_card(dict(raw,oracleText=raw['oracleText'].replace('target creature card','target planeswalker card'))).supported)
        sim,cards=self.fixture(['Sword of Light and Shadow'])
        host=self.token(sim,'attacker')
        sword=self.put(sim,cards['Sword of Light and Shadow'])
        sim.activate_equip(0,sword.card.id,host.card.id);self.drain(sim)
        owner=sim.players[0]
        creature=next(card for card in owner.library if card.kind=='creature')
        owner.library.remove(creature);owner.graveyard.append(creature)
        self.ready(sim);sim.declare_attackers([host.card.id]);sim.declare_blockers({})
        with patch.object(sim,'choose_equipment_graveyard_target',return_value=None):
            sim.group_damage_step()
        trigger=next(item.payload[0] for item in sim.stack.items
                     if item.payload[0].get('operation')=='equipment_hit_sequence')
        self.assertIsNone(trigger['steps'][1]['targetCreatureId'])
        self.drain(sim)
        self.assertIn(creature,owner.graveyard)
        self.assertEqual(owner.life,43)
        sim.invariant()


if __name__=='__main__':unittest.main()
