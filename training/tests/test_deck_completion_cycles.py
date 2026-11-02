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

    def test_cycle_five_multikicker_paid_on_cast_and_entry_counters_scale_elf_team(self):
        raw=self.raw('Joraga Warcaller')
        definition=parse_card(raw)
        self.assertTrue(definition.supported,definition.reason)
        self.assertEqual(definition.multikicker_rule,('{1}{G}',1))
        self.assertTrue(definition.static_effects[0].source_counter_multiplier)
        sim,cards=self.fixture(['Joraga Warcaller'])
        elf=self.token(sim,'ally-elf',subtypes=('Elf',),power=2,toughness=2)
        other=self.token(sim,'ally-human',subtypes=('Human',),power=2,toughness=2)
        enemy=self.token(sim,'enemy-elf',seat=1,subtypes=('Elf',),power=2,toughness=2)
        card=cards['Joraga Warcaller']
        offered={choice.kicker_count for choice in sim.legal(0)
                 if choice.card_id==card.id and choice.kind=='cast'}
        self.assertTrue({0,1,2}<=offered)
        sim.cast_spell(0,card,kicker_count=2)
        self.assertEqual(sim.stack.items[-1].payload[0]['kickerCount'],2)
        self.assertEqual(sum(item.tapped for item in sim.players[0].battlefield
                             if item.card.kind=='land'),5)
        self.assertEqual(sim.effective_card(elf).power,2)
        self.drain(sim)
        warcaller=next(item for item in sim.players[0].battlefield if item.card.id==card.id)
        self.assertEqual(warcaller.counters,2)
        self.assertEqual(sim.effective_card(warcaller).power,3)
        self.assertEqual((sim.effective_card(elf).power,sim.effective_card(elf).toughness),(4,4))
        self.assertEqual((sim.effective_card(other).power,sim.effective_card(enemy).power),(2,2))
        warcaller.counters=1
        self.assertEqual(sim.effective_card(elf).power,3)
        sim.send_to_destination(sim.players[0],warcaller)
        self.assertEqual(sim.effective_card(elf).power,2)
        sim.invariant()

        # Entry counter replacement sees the kicked counters as a single
        # incoming placement event, before the creature has entered.
        sim,cards=self.fixture(['Joraga Warcaller','Hardened Scales'])
        friend=self.token(sim,'friendly-elf',subtypes=('Elf',))
        self.put(sim,cards['Hardened Scales'])
        sim.cast_spell(0,cards['Joraga Warcaller'],kicker_count=2);self.drain(sim)
        source=next(item for item in sim.players[0].battlefield
                    if item.card.id==cards['Joraga Warcaller'].id)
        self.assertEqual(source.counters,3)
        self.assertEqual(sim.effective_card(friend).power,5)
        sim.invariant()

    def test_cycle_five_zero_kicks_amount_subtype_and_unknown_text(self):
        raw=self.raw('Joraga Warcaller')
        raw['name']='Unnamed Warband Mentor'
        raw['oracleText']=raw['oracleText'].replace('a +1/+1 counter','two +1/+1 counters').replace(
            'Other Elf creatures','Other Goblin creatures').replace('get +1/+1','get +2/+3')
        parsed=parse_card(raw)
        self.assertTrue(parsed.supported,parsed.reason)
        self.assertEqual(parsed.multikicker_rule,('{1}{G}',2))
        self.assertEqual((parsed.static_effects[0].subject.subtype,parsed.static_effects[0].power,
                          parsed.static_effects[0].toughness),('Goblin',2,3))
        self.assertFalse(parse_card(dict(raw,oracleText=raw['oracleText']+'\nDraw a card.')).supported)
        self.assertFalse(parse_card(dict(raw,oracleText=raw['oracleText'].replace('for each time it was kicked','when you cast a spell'))).supported)
        sim,cards=self.fixture(['Joraga Warcaller'])
        ally=self.token(sim,'ally-elf',subtypes=('Elf',))
        card=cards['Joraga Warcaller']
        with self.assertRaises(ValueError):sim.cast_spell(0,card,kicker_count=-1)
        sim.cast_spell(0,card,kicker_count=0);self.drain(sim)
        warcaller=next(item for item in sim.players[0].battlefield if item.card.id==card.id)
        self.assertEqual(warcaller.counters,0)
        self.assertEqual(sim.effective_card(ally).power,2)
        sim.invariant()

    def test_cycle_six_fire_and_ice_player_damage_then_draw_with_source_gone(self):
        raw=self.raw('Sword of Fire and Ice')
        definition=parse_card(raw)
        self.assertTrue(definition.supported,definition.reason)
        self.assertEqual(definition.attachment[2],frozenset({'protection from red','protection from blue'}))
        self.assertEqual([(op,n) for op,n,_ in definition.equipped_player_hit_steps],
                         [('damage_equipment_target',2),('draw_cards',1)])
        sim,cards=self.fixture(['Sword of Fire and Ice'])
        attacker=self.token(sim,'attacker',power=2,toughness=2)
        sword=self.put(sim,cards['Sword of Fire and Ice'])
        sim.activate_equip(0,sword.card.id,attacker.card.id);self.drain(sim)
        self.ready(sim);sim.declare_attackers([attacker.card.id]);sim.declare_blockers({})
        before_hand=len(sim.players[0].hand)
        before_lib=len(sim.players[0].library)
        sim.group_damage_step()
        event=next(item.payload[0] for item in sim.stack.items
                   if item.payload[0].get('operation')=='equipment_hit_sequence')
        self.assertEqual(event['steps'][0]['targetKind'],'player')
        self.assertEqual(event['steps'][0]['target'],1)
        self.assertEqual(sim.players[1].life,36)
        self.assertEqual(len(sim.players[0].hand),before_hand)
        sim.send_to_destination(sim.players[0],sword)
        self.drain(sim)
        self.assertEqual(sim.players[1].life,34)
        self.assertEqual(len(sim.players[0].hand),before_hand+1)
        self.assertEqual(len(sim.players[0].library),before_lib-1)
        sim.invariant()

    def test_cycle_six_damage_target_chosen_on_stack_and_illegal_target_fizzles_all(self):
        for removed in (False,True):
            sim,cards=self.fixture(['Sword of Fire and Ice'])
            attacker=self.token(sim,'attacker',power=2,toughness=2)
            enemy=self.token(sim,'enemy-target',seat=1,power=2,toughness=2)
            sword=self.put(sim,cards['Sword of Fire and Ice'])
            sim.activate_equip(0,sword.card.id,attacker.card.id);self.drain(sim)
            self.ready(sim);sim.declare_attackers([attacker.card.id]);sim.declare_blockers({})
            before_hand=len(sim.players[0].hand)
            with patch.object(sim,'choose_damage_target',return_value=('permanent',enemy.card.id)):
                sim.group_damage_step()
            hit=next(item.payload[0] for item in sim.stack.items
                     if item.payload[0].get('operation')=='equipment_hit_sequence')
            self.assertEqual(hit['steps'][0]['target'],enemy.card.id)
            self.assertEqual(enemy.marked_damage,0)
            if removed:sim.send_to_destination(sim.players[1],enemy)
            self.drain(sim)
            self.assertEqual(enemy in sim.players[1].battlefield,False)
            self.assertEqual(len(sim.players[0].hand),before_hand if removed else before_hand+1)
            sim.invariant()

    def test_cycle_six_renamed_damage_and_draw_values_fail_closed(self):
        raw=self.raw('Sword of Fire and Ice')
        raw['name']='Unseen Polar Spark Sword'
        raw['oracleText']=raw['oracleText'].replace('deals 2 damage','deals 4 damage').replace(
            'draw a card','draw two cards')
        compiled=parse_card(raw)
        self.assertTrue(compiled.supported,compiled.reason)
        self.assertEqual([step[:2] for step in compiled.equipped_player_hit_steps],
                         [('damage_equipment_target',4),('draw_cards',2)])
        self.assertFalse(parse_card(dict(raw,oracleText=raw['oracleText']+'\nDestroy all lands.')).supported)
        self.assertFalse(parse_card(dict(raw,oracleText=raw['oracleText'].replace('any target','each creature'))).supported)

    def test_cycle_seven_ezuri_paid_regeneration_and_team_boost_remain_separate(self):
        definition=parse_card(self.raw('Ezuri, Renegade Leader'))
        self.assertTrue(definition.supported,definition.reason)
        self.assertEqual(definition.paid_regenerate_rule,('{G}','Elf'))
        self.assertEqual(definition.tribal_pump_activations,
                         (('{2}{G}{G}{G}','Elf',3,3,'trample'),))
        sim,cards=self.fixture(['Ezuri, Renegade Leader'])
        ally=self.token(sim,'ally-elf',subtypes=('Elf',),power=2,toughness=2)
        outsider=self.token(sim,'ally-human',subtypes=('Human',),power=2,toughness=2)
        enemy=self.token(sim,'opposing-elf',seat=1,subtypes=('Elf',),power=2,toughness=2)
        ezuri=self.put(sim,cards['Ezuri, Renegade Leader'])
        self.assertTrue(ezuri.fresh)
        sim.activate_regenerate(0,ezuri.card.id,ally.card.id)
        self.assertFalse(ezuri.tapped)
        self.assertEqual(ally.regeneration_shields,0)
        self.assertEqual(sum(item.tapped for item in sim.players[0].battlefield
                             if item.card.kind=='land'),1)
        self.drain(sim)
        self.assertEqual(ally.regeneration_shields,1)
        ally.marked_damage=2
        self.assertTrue(sim.replace_regeneration(0,ally,sim.event_game('main')))
        self.assertEqual((ally.regeneration_shields,ally.marked_damage),(0,0))
        self.assertTrue(ally.tapped)
        sim.activate_tribal_pump(0,ezuri.card.id)
        self.assertEqual(sim.effective_card(ally).power,2)
        sim.send_to_destination(sim.players[0],ezuri)
        self.drain(sim)
        self.assertEqual((sim.effective_card(ally).power,sim.effective_card(ally).toughness),(5,5))
        self.assertIn('trample',sim.effective_card(ally).traits)
        self.assertEqual((sim.effective_card(outsider).power,sim.effective_card(enemy).power),(2,2))
        sim.invariant()

    def test_cycle_seven_ezuri_renamed_costs_and_extra_text_fail_closed(self):
        raw=self.raw('Ezuri, Renegade Leader')
        raw['name']='Strange Goblin Defender'
        raw['oracleText']=raw['oracleText'].replace('another target Elf','another target Goblin').replace(
            'Elf creatures','Goblin creatures').replace('get +3/+3','get +4/+2')
        parsed=parse_card(raw)
        self.assertTrue(parsed.supported,parsed.reason)
        self.assertEqual(parsed.paid_regenerate_rule,('{G}','Goblin'))
        self.assertEqual(parsed.tribal_pump_activations[0][1:4],('Goblin',4,2))
        self.assertFalse(parse_card(dict(raw,oracleText=raw['oracleText']+'\nYou win the game.')).supported)
        self.assertFalse(parse_card(dict(raw,oracleText=raw['oracleText'].replace('another target Goblin','each Goblin'))).supported)
        sim,cards=self.fixture(['Ezuri, Renegade Leader'])
        elf=self.token(sim,'elf',subtypes=('Elf',))
        source=self.put(sim,cards['Ezuri, Renegade Leader'])
        with self.assertRaises(ValueError):sim.activate_regenerate(0,source.card.id,source.card.id)
        elf.temporary_abilities=frozenset({'protection from green'})
        with self.assertRaises(ValueError):sim.activate_regenerate(0,source.card.id,elf.card.id)
        sim.invariant()

    def test_cycle_eight_hunting_triad_cast_creates_tokens_or_reinforces_from_hand(self):
        sim,cards=self.fixture(['Hunting Triad'])
        card=cards['Hunting Triad']
        self.assertEqual(card.kind,'token_spell')
        self.assertEqual(card.reinforce_rule,('{3}{G}',3))
        sim.cast_spell(0,card)
        self.assertFalse(any(item.card.name=='Elf Warrior' for item in sim.players[0].battlefield))
        self.drain(sim)
        tokens=[item for item in sim.players[0].battlefield if item.card.name=='Elf Warrior']
        self.assertEqual(len(tokens),3)
        self.assertTrue(all(item.card.event_definition.colors==frozenset({'Green'}) for item in tokens))
        self.assertFalse(any(c.id==card.id for c in sim.players[0].hand))
        sim.invariant()

        sim,cards=self.fixture(['Hunting Triad'])
        card=cards['Hunting Triad']
        ally=self.token(sim,'elf',subtypes=('Elf',),power=2,toughness=2)
        self.assertTrue(any(choice.kind=='activate_reinforce' and
                            choice.target_permanent==ally.card.id
                            for choice in sim.reinforce_choices(0)))
        sim.activate_reinforce(0,card.id,ally.card.id)
        self.assertNotIn(card,sim.players[0].hand)
        self.assertIn(card,sim.players[0].graveyard)
        self.assertEqual(ally.counters,0)
        self.assertEqual(sum(item.tapped for item in sim.players[0].battlefield
                             if item.card.kind=='land'),4)
        self.drain(sim)
        self.assertEqual(ally.counters,3)
        self.assertEqual(sim.effective_card(ally).power,5)
        self.assertFalse(any(item.card.name=='Elf Warrior' for item in sim.players[0].battlefield))
        sim.invariant()

    def test_cycle_eight_reinforce_target_fizzles_and_unknown_oracle_rejected(self):
        raw=self.raw('Hunting Triad')
        raw['name']='Unknown Kindred Reinforcements'
        raw['oracleText']=raw['oracleText'].replace('Reinforce 3','Reinforce 2')
        parsed=s.import_diagnostic_card(self.rules,raw,0,'unseen',{'Green'})
        self.assertEqual(parsed.reinforce_rule,('{3}{G}',2))
        self.assertEqual(s.import_diagnostic_card(self.rules,dict(raw,
                         oracleText=raw['oracleText']+'\nDraw three cards.'),0,'invalid',{'Green'}).kind,'unsupported')
        sim,cards=self.fixture(['Hunting Triad'])
        card=cards['Hunting Triad']
        enemy=self.token(sim,'enemy',seat=1,power=2,toughness=2)
        with patch.object(sim,'choose_damage_target',return_value=('player',1)):
            sim.activate_reinforce(0,card.id,enemy.card.id)
        sim.send_to_destination(sim.players[1],enemy)
        self.drain(sim)
        self.assertIn(card,sim.players[0].graveyard)
        self.assertFalse(any(item.card.id==enemy.card.id for item in sim.players[1].battlefield))
        sim.invariant()


if __name__=='__main__':unittest.main()
