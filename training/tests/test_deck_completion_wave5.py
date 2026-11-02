"""Fifth batch of independent full-Oracle rule families for teaching decks."""
from dataclasses import replace
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from card_events import parse_card
import simulator as s
import test_enchantment_abilities as fixtures


class DeckCompletionWaveFive(unittest.TestCase):
    setUpClass=classmethod(fixtures.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.EnchantmentChecks.tearDownClass.__func__)
    fixture=fixtures.EnchantmentChecks.fixture
    put=fixtures.EnchantmentChecks.put
    token=fixtures.EnchantmentChecks.token
    drain=fixtures.EnchantmentChecks.drain
    ready=fixtures.EnchantmentChecks.ready

    def raw(self,name):return dict(self.lookup[name])

    def test_cycle_one_automaton_targets_both_owners_and_attaches_at_resolution(self):
        definition=parse_card(self.raw('Armory Automaton'))
        self.assertTrue(definition.supported,definition.reason)
        self.assertTrue(definition.multi_equipment_entrance)
        sim,cards=self.fixture(['Armory Automaton','Shadowspear','Umbral Mantle'])
        spear=self.put(sim,cards['Shadowspear'])
        mantle=self.put(sim,cards['Umbral Mantle'])
        sim.players[0].battlefield.remove(mantle)
        sim.players[1].battlefield.append(mantle)
        host=self.put(sim,cards['Armory Automaton'])
        event=sim.stack.items[-1].payload[0]
        self.assertEqual(event['operation'],'attach_any_equipment')
        self.assertEqual(set(identifier for identifier,_ in event['targetEntries']),
                         {spear.card.id,mantle.card.id})
        self.assertIsNone(spear.attached_to)
        self.assertIsNone(mantle.attached_to)
        self.drain(sim)
        self.assertEqual(spear.attached_to,host.card.id)
        self.assertEqual(mantle.attached_to,host.card.id)
        self.assertIn(mantle,sim.players[1].battlefield) # Equipment controller never changes.
        self.assertEqual(sim.effective_card(host).power,3) # Base 2/2 plus Shadowspear.
        sim.invariant()

        # Its separate attack trigger can resolve after one Equipment departs.
        spear.attached_to=None;mantle.attached_to=None
        self.ready(sim);sim.declare_attackers([host.card.id])
        event=sim.stack.items[-1].payload[0]
        self.assertEqual(event['operation'],'attach_any_equipment')
        self.assertEqual(len(event['targetEntries']),2)
        sim.send_to_destination(sim.players[0],spear)
        self.drain(sim)
        self.assertEqual(mantle.attached_to,host.card.id)
        self.assertTrue(any(x['kind']=='multi_equipment_attach' and
                            spear.card.id in x['details'].get('illegal',[]) for x in sim.events))
        sim.invariant()

    def test_cycle_one_automaton_choice_fizzle_and_unseen_names(self):
        raw=self.raw('Armory Automaton')
        renamed=dict(raw,name='An Unknown Armored Construct',oracleText=raw['oracleText']
                     .replace('this creature','An Unknown Armored Construct'))
        self.assertTrue(parse_card(renamed).supported)
        self.assertFalse(parse_card(dict(renamed,oracleText=renamed['oracleText']+
                                        '\nDraw two cards.')).supported)
        self.assertFalse(parse_card(dict(renamed,oracleText=renamed['oracleText'].replace(
            'any number','exactly one'))).supported)
        self.assertFalse(parse_card(dict(renamed,types=['Artifact'])).supported)
        sim,cards=self.fixture(['Armory Automaton','Shadowspear'])
        spear=self.put(sim,cards['Shadowspear'])
        sim.choose_multi_equipment_targets=lambda event,candidates:()
        host=self.put(sim,cards['Armory Automaton'])
        self.assertEqual(sim.stack.items[-1].payload[0]['targetEntries'],())
        self.drain(sim)
        self.assertIsNone(spear.attached_to)
        # With a selected target, the host's departure makes the trigger fizzle.
        sim.choose_multi_equipment_targets=lambda event,candidates:(candidates[0].id,)
        host.fresh=False
        self.ready(sim);sim.declare_attackers([host.card.id])
        sim.send_to_destination(sim.players[0],host)
        self.drain(sim)
        self.assertIsNone(spear.attached_to)
        sim.invariant()

    def test_cycle_two_wave_reveals_exact_x_checks_mana_value_and_batches_entries(self):
        sim,cards=self.fixture(['Genesis Wave','Shadowspear','Umbral Mantle',
                                'Excalibur, Sword of Eden'])
        wave=cards['Genesis Wave']
        self.assertEqual(wave.kind,'x_spell')
        self.assertEqual(wave.x_effect,'wave')
        player=sim.players[0]
        land=next(p for p in player.battlefield if p.card.kind=='land')
        player.battlefield.remove(land)
        player.library.append(land.card)
        for name in ('Excalibur, Sword of Eden','Shadowspear','Umbral Mantle'):
            item=cards[name];player.hand.remove(item)
            player.library.append(item)
        bottom=len(player.library)
        sim.cast_spell(0,wave,x=4)
        self.assertEqual(wave not in player.hand,True)
        self.assertFalse(any(p.card.name=='Shadowspear' for p in player.battlefield))
        self.drain(sim)
        self.assertEqual(len(player.library),bottom-4)
        self.assertTrue(any(p.card.name=='Shadowspear' for p in player.battlefield))
        self.assertTrue(any(p.card.name=='Umbral Mantle' for p in player.battlefield))
        self.assertTrue(any(p.card.id==land.card.id for p in player.battlefield))
        self.assertFalse(any(p.card.name=='Excalibur, Sword of Eden' for p in player.battlefield))
        self.assertIn(cards['Excalibur, Sword of Eden'],player.graveyard)
        self.assertIn(wave,player.graveyard)
        self.assertTrue(any(e['kind']=='wave_reveal' and e['details']['chosenX']==4
                            and len(e['details']['permanents'])==3 for e in sim.events))
        sim.invariant()

    def test_cycle_two_wave_optional_choice_unknown_names_and_extra_clauses(self):
        raw=self.raw('Genesis Wave')
        renamed=dict(raw,name='Unknown Spring of Worlds')
        with s.RulesBridge() as rules:
            compiled=s.import_diagnostic_card(rules,renamed,0,'unseen',{'Green'})
            self.assertEqual((compiled.kind,compiled.x_effect),('x_spell','wave'))
            self.assertEqual(s.import_diagnostic_card(rules,dict(renamed,oracleText=
                renamed['oracleText']+'\nDraw a card.'),0,'extra',{'Green'}).kind,'unsupported')
            self.assertEqual(s.import_diagnostic_card(rules,dict(renamed,oracleText=
                renamed['oracleText'].replace('mana value X or less','mana value X or more')),
                0,'changed',{'Green'}).kind,'unsupported')
        sim,cards=self.fixture(['Genesis Wave','Shadowspear'])
        player=sim.players[0];spear=cards['Shadowspear']
        player.hand.remove(spear);player.library.append(spear)
        sim.choose_wave_permanents=lambda event,candidates:()
        sim.cast_spell(0,cards['Genesis Wave'],x=1)
        self.drain(sim)
        self.assertIn(spear,player.graveyard)
        self.assertFalse(any(p.card.id==spear.id for p in player.battlefield))
        sim.invariant()

    def test_cycle_three_equipped_combat_die_stacks_counter_then_doubles(self):
        parsed=parse_card(self.raw('Sword of Hours'))
        self.assertTrue(parsed.supported,parsed.reason)
        self.assertEqual(parsed.equipped_attack_counters,1)
        self.assertEqual(parsed.equipped_combat_die,12)
        sim,cards=self.fixture(['Sword of Hours'])
        host=self.token(sim,'host',power=2,toughness=2)
        equipment=self.put(sim,cards['Sword of Hours'])
        sim.activate_equip(0,equipment.card.id,host.card.id);self.drain(sim)
        self.ready(sim);sim.declare_attackers([host.card.id])
        self.assertEqual(host.counters,0)
        self.assertTrue(any(frame.payload[0].get('operation')=='equipped_attack_counter'
                            for frame in sim.stack.items))
        self.drain(sim)
        self.assertEqual(host.counters,1)
        sim.roll_die=lambda sides:12
        sim.declare_blockers({})
        sim.group_damage_step()
        self.assertEqual(host.counters,1)
        self.assertTrue(any(frame.payload[0].get('operation')=='combat_die_counters'
                            for frame in sim.stack.items))
        self.drain(sim)
        self.assertEqual(host.counters,2)
        self.assertTrue(any(e['kind']=='combat_die_counters' and
                            e['details']['damage']==3 and e['details']['roll']==12
                            for e in sim.events))
        sim.invariant()

    def test_cycle_three_die_on_creature_damage_and_parameterized_fail_closed(self):
        raw=self.raw('Sword of Hours')
        renamed=dict(raw,name='A New Timepiece',oracleText=raw['oracleText']
            .replace('a d12','a d20').replace('result is 12','result is 20')
            .replace('Equip {2}','Equip {1}{R}'))
        parsed=parse_card(renamed)
        self.assertTrue(parsed.supported,parsed.reason)
        self.assertEqual(parsed.equipped_combat_die,20)
        self.assertEqual(parsed.attachment[1],'{1}{R}')
        self.assertFalse(parse_card(dict(renamed,oracleText=renamed['oracleText']+
                                        '\nYou draw seven cards.')).supported)
        self.assertFalse(parse_card(dict(renamed,oracleText=renamed['oracleText'].replace(
            'result is 20','result is 19'))).supported)
        self.assertFalse(parse_card(dict(renamed,types=['Creature'])).supported)
        sim,cards=self.fixture(['Sword of Hours'])
        host=self.token(sim,'host',power=3,toughness=4)
        blocker=self.token(sim,'blocker',seat=1,power=1,toughness=4)
        equipment=self.put(sim,cards['Sword of Hours'])
        sim.activate_equip(0,equipment.card.id,host.card.id);self.drain(sim)
        self.ready(sim);sim.declare_attackers([host.card.id]);self.drain(sim)
        self.assertEqual(host.counters,1)
        sim.roll_die=lambda sides:1
        sim.declare_blockers({host.card.id:[blocker.card.id]})
        sim.group_damage_step();self.drain(sim)
        self.assertEqual(host.counters,1) # Roll not greater than 4 damage.
        self.assertTrue(any(e['kind']=='combat_die_counters' and
                            e['details']['damage']==4 and not e['details']['qualified']
                            for e in sim.events))
        sim.invariant()


if __name__=='__main__':unittest.main()
