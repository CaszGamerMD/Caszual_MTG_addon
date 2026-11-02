"""Fourth batch of independent full-Oracle teaching-deck grammar families."""
from dataclasses import replace
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from card_events import parse_card
import simulator as s
import test_enchantment_abilities as fixtures


class DeckCompletionWaveFour(unittest.TestCase):
    setUpClass=classmethod(fixtures.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.EnchantmentChecks.tearDownClass.__func__)
    fixture=fixtures.EnchantmentChecks.fixture
    put=fixtures.EnchantmentChecks.put
    token=fixtures.EnchantmentChecks.token
    drain=fixtures.EnchantmentChecks.drain
    ready=fixtures.EnchantmentChecks.ready

    def raw(self,name):return dict(self.lookup[name])

    def test_cycle_one_mobilize_uses_live_power_attacks_and_sacrifices_exact_tokens(self):
        raw=self.raw('Infantry Shield')
        definition=parse_card(raw)
        self.assertTrue(definition.supported,definition.reason)
        self.assertTrue(definition.equipment_mobilize)
        self.assertEqual(definition.attachment,
                         ('equipment','{2}',frozenset({'menace'}),0,0))
        sim,cards=self.fixture(['Infantry Shield'])
        host=self.token(sim,'host',power=3,toughness=3)
        shield=self.put(sim,cards['Infantry Shield'])
        sim.activate_equip(0,shield.card.id,host.card.id);self.drain(sim)
        self.assertTrue(sim.event_game('main').has(sim.event_game('main').battlefield['host'],'menace'))
        self.ready(sim);sim.declare_attackers([host.card.id])
        self.assertTrue(any(frame.payload[0].get('operation')=='equipment_mobilize'
                            for frame in sim.stack.items))
        self.assertFalse(any(p.card.name=='Warrior' for p in sim.players[0].battlefield))
        host.counters+=1 # Live power at triggered ability resolution, after attacking.
        self.drain(sim)
        tokens=[p for p in sim.players[0].battlefield if p.card.name=='Warrior']
        self.assertEqual(len(tokens),4)
        self.assertTrue(all(p.tapped and p.card.is_token for p in tokens))
        self.assertTrue(all(p.card.event_definition.colors==frozenset({'Red'}) and
                            (p.card.power,p.card.toughness)==(1,1) for p in tokens))
        self.assertEqual(len(sim.group_combat['attackers']),5)
        self.assertEqual(sim.group_combat['declared'],['host'])
        self.assertEqual(len(sim.pending_token_sacrifices),1)
        sim.declare_blockers({})
        sim.group_damage_step();self.drain(sim)
        self.assertEqual(sim.players[1].life,32) # Four-power host plus four Warriors.
        sim.phase='end_step';sim._step()
        self.assertTrue(any(frame.payload[0].get('operation')=='delayed_sacrifice_tokens'
                            for frame in sim.stack.items))
        self.assertEqual(len([p for p in sim.players[0].battlefield if p.card.name=='Warrior']),4)
        self.drain(sim)
        self.assertFalse(any(p.card.name=='Warrior' for p in sim.players[0].battlefield))
        self.assertFalse(sim.pending_token_sacrifices)
        sim.invariant()

    def test_cycle_one_mobilize_source_leaves_and_unfamiliar_names_fail_closed(self):
        raw=self.raw('Infantry Shield')
        renamed=dict(raw,name='Unfamiliar Rallying Plate',oracleText=raw['oracleText'].replace(
            'has menace and mobilize','has trample and mobilize').replace('Equip {2}','Equip {1}{R}'))
        compiled=parse_card(renamed)
        self.assertTrue(compiled.supported,compiled.reason)
        self.assertEqual(compiled.attachment[1],'{1}{R}')
        self.assertEqual(compiled.attachment[2],frozenset({'trample'}))
        self.assertFalse(parse_card(dict(renamed,oracleText=renamed['oracleText']+
                                         '\nYou win the game.')).supported)
        self.assertFalse(parse_card(dict(renamed,oracleText=renamed['oracleText'].replace(
            'where X is its power','where X is its toughness'))).supported)
        self.assertFalse(parse_card(dict(renamed,types=['Creature'])).supported)

        sim,cards=self.fixture(['Infantry Shield'])
        host=self.token(sim,'host',power=3,toughness=2)
        shield=self.put(sim,cards['Infantry Shield'])
        sim.activate_equip(0,shield.card.id,host.card.id);self.drain(sim)
        self.ready(sim);sim.declare_attackers([host.card.id])
        sim.send_to_destination(sim.players[0],host)
        sim.send_to_destination(sim.players[0],shield)
        self.drain(sim)
        warriors=[p for p in sim.players[0].battlefield if p.card.name=='Warrior']
        self.assertEqual(len(warriors),3) # Last known attacker's power.
        self.assertTrue(all(p.card.id in sim.group_combat['attackers'] for p in warriors))
        sim.invariant()

    def test_cycle_two_untap_symbol_is_paid_before_stack_and_pump_survives_equipment(self):
        parsed=parse_card(self.raw('Umbral Mantle'))
        self.assertTrue(parsed.supported,parsed.reason)
        self.assertEqual(parsed.equipped_untap_pump,('{3}',2,2))
        self.assertEqual(parsed.attachment[1],'{0}')
        sim,cards=self.fixture(['Umbral Mantle'])
        host=self.token(sim,'elf',power=2,toughness=2)
        mantle=self.put(sim,cards['Umbral Mantle'])
        sim.activate_equip(0,mantle.card.id,host.card.id);self.drain(sim)
        host.tapped=True;host.fresh=True
        with self.assertRaises(ValueError):sim.activate_untap_pump(0,mantle.card.id,host.card.id)
        self.assertFalse(sim.untap_pump_choices(0))
        host.fresh=False
        choices=[c for c in sim.priority_observation(0).legal_actions
                 if c.kind=='activate_untap_pump']
        self.assertEqual(len(choices),1)
        self.assertEqual(choices[0].target_permanent,host.card.id)
        sim.activate_untap_pump(0,mantle.card.id,host.card.id)
        self.assertFalse(host.tapped)
        self.assertEqual(sim.effective_card(host).power,2)
        self.assertEqual(sum(p.tapped for p in sim.players[0].battlefield if p.card.kind=='land'),3)
        sim.send_to_destination(sim.players[0],mantle)
        self.drain(sim)
        self.assertEqual((sim.effective_card(host).power,sim.effective_card(host).toughness),(4,4))
        sim.phase='cleanup';sim._step()
        self.assertEqual((sim.effective_card(host).power,sim.effective_card(host).toughness),(2,2))
        sim.invariant()

    def test_cycle_two_untap_grant_uses_creature_controller_and_rejects_extra_text(self):
        raw=self.raw('Umbral Mantle')
        renamed=dict(raw,name='Unseen Tangle Harness',oracleText=raw['oracleText'].replace(
            '{3}, {Q}', '{2}{G}, {Q}').replace('+2/+2','+4/+1'))
        self.assertEqual(parse_card(renamed).equipped_untap_pump,('{2}{G}',4,1))
        self.assertFalse(parse_card(dict(renamed,oracleText=renamed['oracleText']+
                                         '\nDraw seven cards.')).supported)
        self.assertFalse(parse_card(dict(renamed,oracleText=renamed['oracleText'].replace(
            '{Q}','{T}'))).supported)
        sim,cards=self.fixture(['Umbral Mantle'])
        host=self.token(sim,'opponent-elf',seat=1)
        mantle=self.put(sim,cards['Umbral Mantle'])
        mantle.attached_to=host.card.id
        host.tapped=True
        sim.players[1].mana_pool[5]=3
        self.assertFalse(sim.untap_pump_choices(0))
        self.assertEqual(len(sim.untap_pump_choices(1)),1)
        sim.stack.priority=1
        sim.activate_untap_pump(1,mantle.card.id,host.card.id)
        self.assertEqual(sim.players[1].mana_pool[5],0)
        self.assertFalse(host.tapped)
        self.drain(sim)
        self.assertEqual(sim.effective_card(host).power,4)
        sim.invariant()

    def test_cycle_three_transformation_is_live_layered_and_reversible(self):
        raw=self.raw("Kenrith's Transformation")
        parsed=parse_card(raw)
        self.assertTrue(parsed.supported,parsed.reason)
        self.assertEqual(parsed.aura_transformation,('Green','Elk',3,3))
        sim,cards=self.fixture(["Kenrith's Transformation",'Shadowspear'])
        host=self.token(sim,'host',power=7,toughness=5,keywords=('flying','trample'),
                        colors=('Blue',),subtypes=('Elf','Warrior'))
        host.card=replace(host.card,event_definition=replace(host.card.event_definition,
                          types=frozenset({'Artifact','Creature'}),self_pump=('{1}',1,1)))
        self.assertTrue(any(c.kind=='activate_self_pump' and c.card_id=='host'
                            for c in sim.token_ability_choices(0)))
        host.counters=2
        aura=self.put(sim,cards["Kenrith's Transformation"],host.card.id)
        game=sim.event_game('main');state=game.battlefield['host']
        self.assertEqual(state.definition.types,frozenset({'Creature'}))
        self.assertEqual(state.definition.subtypes,frozenset({'Elk'}))
        self.assertEqual(state.definition.colors,frozenset({'Green'}))
        self.assertEqual(game.stats(state),(5,5)) # Base 3/3 plus existing counters.
        self.assertFalse(game.has(state,'flying'))
        self.assertFalse(game.has(state,'trample'))
        self.assertFalse(state.definition.self_pump)
        self.assertFalse(any(c.kind=='activate_self_pump' and c.card_id=='host'
                             for c in sim.token_ability_choices(0)))
        self.assertEqual(sim.effective_card(host).colors,('Green',))
        # A real Equipment granted later applies after the Aura's timestamp.
        self.drain(sim)
        equipment=self.put(sim,cards['Shadowspear'])
        sim.activate_equip(0,equipment.card.id,host.card.id);self.drain(sim)
        game=sim.event_game('main');state=game.battlefield['host']
        self.assertTrue(game.has(state,'lifelink'))
        self.assertTrue(game.has(state,'trample'))
        self.assertEqual(game.stats(state),(6,6))
        sim.send_to_destination(sim.players[0],aura)
        game=sim.event_game('main');state=game.battlefield['host']
        self.assertEqual(state.definition.types,frozenset({'Artifact','Creature'}))
        self.assertEqual(state.definition.subtypes,frozenset({'Elf','Warrior'}))
        self.assertEqual(state.definition.colors,frozenset({'Blue'}))
        self.assertTrue(game.has(state,'flying'))
        self.assertTrue(any(c.kind=='activate_self_pump' and c.card_id=='host'
                            for c in sim.token_ability_choices(0)))
        self.assertEqual(game.stats(state),(10,8)) # Printed 7/5, 2 counters, Equipment +1/+1.
        sim.invariant()

    def test_cycle_three_aura_entry_draw_uses_stack_and_survives_aura_departure(self):
        raw=self.raw("Kenrith's Transformation")
        renamed=dict(raw,name='Nameless Elk Curse',oracleText=raw['oracleText'].replace(
            'green Elk','red Fox').replace('3/3','2/4'))
        compiled=parse_card(renamed)
        self.assertTrue(compiled.supported,compiled.reason)
        self.assertEqual(compiled.aura_transformation,('Red','Fox',2,4))
        self.assertFalse(parse_card(dict(renamed,oracleText=renamed['oracleText']+
                                        '\nYou win the game.')).supported)
        self.assertFalse(parse_card(dict(renamed,types=['Creature'])).supported)
        self.assertFalse(parse_card(dict(renamed,oracleText=renamed['oracleText'].replace(
            'loses all abilities','keeps all abilities'))).supported)
        sim,cards=self.fixture(["Kenrith's Transformation"])
        host=self.token(sim,'host')
        start=len(sim.players[0].hand)
        aura=self.put(sim,cards["Kenrith's Transformation"],host.card.id)
        self.assertTrue(any(frame.payload[0].get('operation')=='draw_cards'
                            for frame in sim.stack.items))
        self.assertEqual(len(sim.players[0].hand),start-1)
        sim.send_to_destination(sim.players[0],aura)
        self.drain(sim)
        self.assertEqual(len(sim.players[0].hand),start)
        self.assertEqual(sim.effective_card(host).power,2)
        sim.invariant()

    def test_cycle_four_squeak_counts_base_one_and_autoequips_at_resolution(self):
        raw=self.raw('Sword of the Squeak')
        parsed=parse_card(raw)
        self.assertTrue(parsed.supported,parsed.reason)
        self.assertEqual(parsed.equipment_base_one_scale,(1,1))
        self.assertEqual(parsed.equipment_tribal_entry_attach,
                         ('Hamster','Mouse','Rat','Squirrel'))
        sim,cards=self.fixture(['Sword of the Squeak'])
        host=self.token(sim,'big-host',power=4,toughness=4)
        small=self.token(sim,'small-elf',power=2,toughness=1,subtypes=('Elf',))
        small.counters+=3 # Counters do not change printed base toughness of 1.
        sword=self.put(sim,cards['Sword of the Squeak'])
        sim.activate_equip(0,sword.card.id,host.card.id);self.drain(sim)
        self.assertEqual((sim.effective_card(host).power,sim.effective_card(host).toughness),(5,5))
        rat_definition=s.EventDefinition('New Rat',frozenset({'Creature'}),
            frozenset({'Rat'}),False,1,4,frozenset())
        rat=s.Card('new-rat','New Rat','creature','{0}','1;4;',1,4,
                   event_definition=rat_definition,is_token=True)
        pending=sim.enter_creature(rat,sim.players[0]);sim.resolve_entry_triggers(pending,rat)
        rat_item=next(p for p in sim.players[0].battlefield if p.card.id=='new-rat')
        self.assertEqual(sword.attached_to,host.card.id)
        self.assertEqual(sim.effective_card(host).power,6)
        self.assertTrue(any(frame.payload[0].get('operation')=='tribal_equipment_attach'
                            for frame in sim.stack.items))
        self.drain(sim)
        self.assertEqual(sword.attached_to,rat_item.card.id)
        self.assertEqual(sim.effective_card(rat_item).power,3) # Base 1 plus 2 counted creatures.
        self.assertEqual(sim.effective_card(host).power,4)
        sim.invariant()

    def test_cycle_four_squeak_optional_attach_and_unfamiliar_names_fail_closed(self):
        raw=self.raw('Sword of the Squeak')
        renamed=dict(raw,name='Unfamiliar Critter Whistle',oracleText=raw['oracleText']
            .replace('Hamster, Mouse, Rat, or Squirrel','Goat or Rabbit')
            .replace('+1/+1','+2/+3').replace('Equip {2}','Equip {1}{R}'))
        parsed=parse_card(renamed)
        self.assertTrue(parsed.supported,parsed.reason)
        self.assertEqual(parsed.equipment_base_one_scale,(2,3))
        self.assertEqual(parsed.equipment_tribal_entry_attach,('Goat','Rabbit'))
        self.assertFalse(parse_card(dict(renamed,oracleText=renamed['oracleText']+
                                        '\nCreate a Treasure token.')).supported)
        self.assertFalse(parse_card(dict(renamed,oracleText=renamed['oracleText'].replace(
            'base power or toughness 1','current power or toughness 1'))).supported)
        self.assertFalse(parse_card(dict(renamed,types=['Creature'])).supported)
        sim,cards=self.fixture(['Sword of the Squeak'])
        sword=self.put(sim,cards['Sword of the Squeak'])
        sim.choose_optional_tribal_equipment_attach=lambda event:False
        mouse_definition=s.EventDefinition('Mouse',frozenset({'Creature'}),
            frozenset({'Mouse'}),False,1,1,frozenset())
        mouse=s.Card('test-mouse','Mouse','creature','{0}','1;1;',1,1,
                     event_definition=mouse_definition,is_token=True)
        pending=sim.enter_creature(mouse,sim.players[0]);sim.resolve_entry_triggers(pending,mouse)
        self.drain(sim)
        self.assertIsNone(sword.attached_to)
        enemy=replace(mouse,id='opponent-mouse')
        enemy_pending=sim.enter_creature(enemy,sim.players[1])
        self.assertFalse(any(e.get('operation')=='tribal_equipment_attach'
                             for e in enemy_pending))
        sim.invariant()


if __name__=='__main__':unittest.main()
