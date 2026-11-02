"""Three independent Oracle composition cycles against saved deck cards.

All grammar variants are renamed and parameterized: card names never dispatch
behavior.  Unparsed extra sentences must reject the entire card.
"""
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from card_events import parse_card, Game, Permanent
from oracle_abilities import cast_matches
import simulator as s
import test_enchantment_abilities as fixtures


class ComposedOracleCycles(unittest.TestCase):
    setUpClass=classmethod(fixtures.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.EnchantmentChecks.tearDownClass.__func__)
    fixture=fixtures.EnchantmentChecks.fixture
    put=fixtures.EnchantmentChecks.put
    token=fixtures.EnchantmentChecks.token
    drain=fixtures.EnchantmentChecks.drain
    ready=fixtures.EnchantmentChecks.ready

    def real(self,name):
        return dict(self.lookup[name])

    def test_cycle_one_cast_payment_composes_with_live_elf_anthem(self):
        raw=self.real('Leaf-Crowned Visionary')
        definition=parse_card(raw)
        self.assertTrue(definition.supported,definition.reason)
        self.assertEqual(len(definition.static_effects),1)
        self.assertEqual(len(definition.triggers),1)
        self.assertEqual(definition.triggers[0].effect.payment_cost,'{G}')
        g=Game()
        g.enter(Permanent('source',definition,0))
        ally=parse_card(dict(name='Unseen Ally',types=['Creature'],subTypes=['Elf'],
                             power='2',toughness='2',oracleText='Reach'))
        enemy=Permanent('enemy',ally,1)
        g.enter(Permanent('ally',ally,0));g.enter(enemy)
        self.assertEqual(g.stats(g.battlefield['ally']),(3,3))
        self.assertEqual(g.stats(g.battlefield['enemy']),(2,2))
        g.leave('source')
        self.assertEqual(g.stats(g.battlefield['ally']),(2,2))

        sim,cards=self.fixture(['Leaf-Crowned Visionary','Lys Alana Huntmaster'])
        source=self.put(sim,cards['Leaf-Crowned Visionary'])
        elf=cards['Lys Alana Huntmaster']
        event=sim.event_game('main').cast_triggers(elf,0)
        self.assertEqual(len(event),1)
        self.assertEqual(event[0]['paymentCost'],'{G}')
        self.assertFalse(sim.event_game('main').cast_triggers(elf,1))
        hand_before=len(sim.players[0].hand)
        for p in sim.players[0].battlefield:
            if p.card.kind=='land':p.tapped=True
        land=next(p for p in sim.players[0].battlefield if p.card.kind=='land')
        land.tapped=False
        sim.resolve_entry_triggers(event,elf)
        self.assertEqual(len(sim.players[0].hand),hand_before)
        self.drain(sim)
        self.assertEqual(len(sim.players[0].hand),hand_before+1)
        self.assertTrue(land.tapped)
        self.assertTrue(any(e['kind']=='trigger_payment' for e in sim.events))
        # No mana: the trigger resolves without granting a free draw.
        before=len(sim.players[0].hand)
        sim.resolve_entry_triggers(sim.event_game('main').cast_triggers(elf,0),elf)
        self.drain(sim)
        self.assertEqual(len(sim.players[0].hand),before)
        self.assertTrue(any(e['kind']=='trigger_payment_unavailable' for e in sim.events))
        # An explicit decline must never tap mana or resolve the gated effect.
        land.tapped=False
        with patch.object(sim,'choose_optional_trigger_payment',return_value=False):
            sim.resolve_entry_triggers(sim.event_game('main').cast_triggers(elf,0),elf)
            self.drain(sim)
        self.assertEqual(len(sim.players[0].hand),before)
        self.assertFalse(land.tapped)
        self.assertTrue(any(e['kind']=='trigger_payment_declined' for e in sim.events))
        self.assertIn(source,sim.players[0].battlefield)
        sim.invariant()

    def test_cycle_one_renamed_effect_and_unknown_remainder(self):
        raw=self.real('Leaf-Crowned Visionary')
        raw['name']='Unseen Foliage Mentor'
        raw['oracleText']=raw['oracleText'].replace('Elves','Goblins').replace('Elf spell','Goblin spell').replace('{G}','{2}').replace('draw a card','gain 3 life')
        parsed=parse_card(raw)
        self.assertTrue(parsed.supported,parsed.reason)
        self.assertEqual(parsed.triggers[0].effect.payment_cost,'{2}')
        self.assertEqual(parsed.triggers[0].effect.operation,'gain_life')
        self.assertEqual(parsed.triggers[0].subject.subtype,'Goblin')
        for extra in ('Win the game.','If you do, draw seven cards.'):
            self.assertFalse(parse_card(dict(raw,oracleText=raw['oracleText']+'\n'+extra)).supported)
        malformed=dict(raw,oracleText=raw['oracleText'].replace('If you do,','If you might,'))
        self.assertFalse(parse_card(malformed).supported)

    def test_cycle_two_equipped_attack_counters_stack_and_source_independence(self):
        raw=self.real('Bone Sabres')
        parsed=parse_card(raw)
        self.assertTrue(parsed.supported,parsed.reason)
        self.assertEqual(parsed.equipped_attack_counters,4)
        sim,cards=self.fixture(['Bone Sabres'])
        attacker=self.token(sim,'unseen-attacker',power=2,toughness=2)
        sabres=self.put(sim,cards['Bone Sabres'])
        sim.activate_equip(0,sabres.card.id,attacker.card.id);self.drain(sim)
        self.ready(sim)
        sim.declare_attackers([attacker.card.id])
        self.assertEqual(attacker.counters,0)
        self.assertTrue(any(frame.payload[0].get('operation')=='equipped_attack_counter'
                            for frame in sim.stack.items))
        # A triggered ability exists independently once it has triggered.
        sim.send_to_destination(sim.players[0],sabres)
        self.drain(sim)
        self.assertEqual(attacker.counters,4)
        self.assertEqual(sim.effective_card(attacker).power,6)
        sim.invariant()

    def test_cycle_two_composes_equipment_static_grants_and_rejects_extra(self):
        raw=self.real('Bone Sabres')
        raw['name']='Unseen Training Tool'
        raw['oracleText']=raw['oracleText'].replace('four','two').replace('Equip {3}',
            'Equipped creature gets +1/+2 and has vigilance.\nEquip {4}')
        parsed=parse_card(raw)
        self.assertTrue(parsed.supported,parsed.reason)
        self.assertEqual(parsed.equipped_attack_counters,2)
        self.assertEqual(parsed.attachment,('equipment','{4}',frozenset({'vigilance'}),1,2))
        for added in ('Whenever equipped creature blocks, you win the game.',
                      'Whenever equipped creature attacks, put a +1/+1 counter on it.'):
            self.assertFalse(parse_card(dict(raw,oracleText=raw['oracleText']+'\n'+added)).supported)

    def test_cycle_two_counter_replacement_and_zone_changed_attacker(self):
        sim,cards=self.fixture(['Bone Sabres','Hardened Scales'])
        attacker=self.token(sim,'enchanted-attacker')
        sabres=self.put(sim,cards['Bone Sabres'])
        self.put(sim,cards['Hardened Scales'])
        sim.activate_equip(0,sabres.card.id,attacker.card.id);self.drain(sim)
        self.ready(sim);sim.declare_attackers([attacker.card.id]);self.drain(sim)
        self.assertEqual(attacker.counters,5)  # Four plus one replacement.
        sim.invariant()

        sim,cards=self.fixture(['Bone Sabres','Lys Alana Huntmaster'])
        host=self.put(sim,cards['Lys Alana Huntmaster'])
        sabres=self.put(sim,cards['Bone Sabres'])
        sim.activate_equip(0,sabres.card.id,host.card.id);self.drain(sim)
        self.ready(sim);sim.declare_attackers([host.card.id])
        sim.send_to_destination(sim.players[0],host)
        # Same Card ID re-enters as a new permanent and must not receive the
        # old attacker's pending counters.
        sim.players[0].graveyard.remove(host.card)
        sim.enter_creature(host.card,sim.players[0])
        self.drain(sim)
        returned=next(p for p in sim.players[0].battlefield if p.card.id==host.card.id)
        self.assertEqual(returned.counters,0)
        sim.invariant()

    def test_cycle_three_token_equip_payment_target_and_grants(self):
        raw=self.real('Team Pennant')
        parsed=parse_card(raw)
        self.assertTrue(parsed.supported,parsed.reason)
        self.assertEqual((parsed.equipment_token_cost,parsed.attachment[1]),('{1}','{3}'))
        sim,cards=self.fixture(['Team Pennant','Lys Alana Huntmaster'])
        pennant=self.put(sim,cards['Team Pennant'])
        elf=self.put(sim,cards['Lys Alana Huntmaster'])
        token=self.token(sim,'unknown-token',power=2,toughness=2)
        for p in sim.players[0].battlefield:
            if p.card.kind=='land':p.tapped=True
        lands=[p for p in sim.players[0].battlefield if p.card.kind=='land']
        lands[0].tapped=False
        sim.stack.priority=0
        self.assertIn(token.card.id,[c.target_permanent for c in sim.equip_choices(0)])
        self.assertNotIn(elf.card.id,[c.target_permanent for c in sim.equip_choices(0)])
        with self.assertRaises(ValueError):sim.activate_equip(0,pennant.card.id,elf.card.id)
        sim.activate_equip(0,pennant.card.id,token.card.id);self.drain(sim)
        self.assertEqual(pennant.attached_to,token.card.id)
        self.assertTrue(lands[0].tapped)
        self.assertEqual(sim.effective_card(token).power,3)
        self.assertIn('vigilance',sim.effective_card(token).traits)
        self.assertIn('trample',sim.effective_card(token).traits)
        # Ordinary equip still works for nontoken creatures, at its own cost.
        for land in lands[:3]:land.tapped=False
        sim.activate_equip(0,pennant.card.id,elf.card.id);self.drain(sim)
        self.assertEqual(pennant.attached_to,elf.card.id)
        self.assertEqual(sum(p.tapped for p in lands),len(lands))
        self.assertEqual(sim.effective_card(token).power,2)
        sim.invariant()

    def test_cycle_three_renamed_grammar_fail_closed(self):
        raw=self.real('Team Pennant')
        raw['name']='Unseen Token Standard'
        raw['oracleText']=raw['oracleText'].replace('+1/+1','+2/+3').replace('vigilance and trample','first strike and reach').replace('token {1}','token {2}')
        parsed=parse_card(raw)
        self.assertTrue(parsed.supported,parsed.reason)
        self.assertEqual(parsed.attachment,('equipment','{3}',frozenset({'first strike','reach'}),2,3))
        self.assertEqual(parsed.equipment_token_cost,'{2}')
        self.assertFalse(parse_card(dict(raw,oracleText=raw['oracleText']+'\nEquip creature token {1}')).supported)
        self.assertFalse(parse_card(dict(raw,oracleText=raw['oracleText']+'\nEquip {5}')).supported)
        self.assertFalse(parse_card(dict(raw,oracleText=raw['oracleText']+'\nCreate a Dragon token.')).supported)
        self.assertFalse(parse_card(dict(raw,subTypes=[])).supported)


if __name__=='__main__':
    unittest.main()
