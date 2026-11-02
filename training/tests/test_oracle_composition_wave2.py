"""Reusable complete-Oracle compositions, real deck cards and novel names."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
from card_events import parse_card,Game,Permanent
import test_enchantment_abilities as fixtures


class OracleCompositionWaveTwo(unittest.TestCase):
    setUpClass=classmethod(fixtures.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.EnchantmentChecks.tearDownClass.__func__)
    fixture=fixtures.EnchantmentChecks.fixture
    put=fixtures.EnchantmentChecks.put
    token=fixtures.EnchantmentChecks.token
    drain=fixtures.EnchantmentChecks.drain
    ready=fixtures.EnchantmentChecks.ready

    def raw(self,name):return dict(self.lookup[name])

    def test_cycle_one_quietus_half_life_resolves_at_stack_time(self):
        parsed=parse_card(self.raw('Quietus Spike'))
        self.assertTrue(parsed.supported,parsed.reason)
        self.assertEqual(parsed.equipped_player_hit_life,('half',0))
        self.assertEqual(parsed.attachment[2],frozenset({'deathtouch'}))
        sim,cards=self.fixture(['Quietus Spike'])
        attacker=self.token(sim,'unknown-attacker',power=2,toughness=2)
        spike=self.put(sim,cards['Quietus Spike'])
        sim.activate_equip(0,spike.card.id,attacker.card.id);self.drain(sim)
        self.ready(sim);sim.declare_attackers([attacker.card.id]);sim.declare_blockers({})
        sim.group_damage_step()
        self.assertEqual(sim.players[1].life,38)
        self.assertTrue(any(frame.payload[0].get('operation')=='equipment_hit_life'
                            for frame in sim.stack.items))
        sim.gain_life(1,2)  # 38 -> 40; half is evaluated at resolution.
        # The trigger exists even if its source is destroyed after damage.
        sim.send_to_destination(sim.players[0],spike)
        self.drain(sim)
        self.assertEqual(sim.players[1].life,20)
        sim.invariant()

    def test_cycle_one_life_uses_current_total_and_rejects_extra_text(self):
        raw=self.raw('Quietus Spike')
        raw['name']='Unseen Mindspike'
        raw['oracleText']=raw['oracleText'].replace('half their life, rounded up','3 life')
        parsed=parse_card(raw)
        self.assertTrue(parsed.supported,parsed.reason)
        self.assertEqual(parsed.equipped_player_hit_life,('fixed',3))
        self.assertFalse(parse_card(dict(raw,oracleText=raw['oracleText']+'\nDraw seven cards.')).supported)
        raw['oracleText']+='\nWhenever equipped creature deals combat damage to a player, that player loses 2 life.'
        self.assertFalse(parse_card(raw).supported)

    def test_cycle_one_prevented_damage_does_not_trigger(self):
        sim,cards=self.fixture(['Quietus Spike'])
        attacker=self.token(sim,'unknown-attacker')
        spike=self.put(sim,cards['Quietus Spike'])
        sim.activate_equip(0,spike.card.id,attacker.card.id);self.drain(sim)
        self.ready(sim);sim.declare_attackers([attacker.card.id]);sim.declare_blockers({})
        sim.combat_damage_prevented=True
        sim.group_damage_step();self.drain(sim)
        self.assertEqual(sim.players[1].life,40)
        sim.invariant()

    def test_cycle_one_double_strike_triggers_on_each_positive_hit(self):
        sim,cards=self.fixture(['Quietus Spike'])
        attacker=self.token(sim,'unknown-double',keywords=('double strike',))
        spike=self.put(sim,cards['Quietus Spike'])
        sim.activate_equip(0,spike.card.id,attacker.card.id);self.drain(sim)
        self.ready(sim);sim.declare_attackers([attacker.card.id]);sim.declare_blockers({})
        sim.group_damage_step()
        self.assertEqual(sim.players[1].life,38)
        self.drain(sim)
        self.assertEqual(sim.players[1].life,19)
        sim.group_damage_step()
        self.assertEqual(sim.players[1].life,17)
        self.drain(sim)
        self.assertEqual(sim.players[1].life,8)
        sim.invariant()

    def test_cycle_two_equipment_spell_and_targeted_ability_costs_separate(self):
        raw=self.raw('Bladegraft Aspirant')
        parsed=parse_card(raw)
        self.assertTrue(parsed.supported,parsed.reason)
        self.assertIn('menace',parsed.abilities)
        self.assertEqual(parsed.equipment_target_ability_discount,1)
        self.assertEqual(parsed.cost_reductions,((('equipment',),1),))
        sim,cards=self.fixture(['Bladegraft Aspirant','Quietus Spike'])
        aspirant=self.put(sim,cards['Bladegraft Aspirant'])
        other=self.token(sim,'unseen-host')
        spike=cards['Quietus Spike']
        # Spell-only discount: three-generic Equipment is castable for two.
        lands=[p for p in sim.players[0].battlefield if p.card.kind=='land']
        for p in lands:p.tapped=True
        for p in lands[:2]:p.tapped=False
        self.assertTrue(sim.payment(spike,seat=0,spell_cost=True)['paid'])
        sim.players[0].hand.remove(spike)
        sim.enter_creature(spike,sim.players[0]);self.drain(sim)
        # Targeted-ability discount: equip the Aspirant for two, but not the
        # unrelated 2/2 token. The Equipment's own printed cost stays {3}.
        sim.stack.priority=0
        self.assertIn(aspirant.card.id,[c.target_permanent for c in sim.equip_choices(0)])
        self.assertNotIn(other.card.id,[c.target_permanent for c in sim.equip_choices(0)])
        with self.assertRaises(ValueError):sim.activate_equip(0,spike.id,other.card.id)
        sim.activate_equip(0,spike.id,aspirant.card.id);self.drain(sim)
        self.assertEqual(next(x for x in sim.players[0].battlefield if x.card.id==spike.id).attached_to,
                         aspirant.card.id)
        self.assertTrue(all(p.tapped for p in lands))
        sim.invariant()

    def test_cycle_two_renamed_discount_amount_and_fail_closed(self):
        raw=self.raw('Bladegraft Aspirant')
        raw['name']='Unseen Artificer'
        raw['oracleText']=raw['oracleText'].replace('cost {1} less','cost {2} less')
        parsed=parse_card(raw)
        self.assertTrue(parsed.supported,parsed.reason)
        self.assertEqual(parsed.equipment_target_ability_discount,2)
        self.assertEqual(parsed.cost_reductions,((('equipment',),2),))
        self.assertFalse(parse_card(dict(raw,oracleText=raw['oracleText']+'\nWin the game.')).supported)
        self.assertFalse(parse_card(dict(raw,oracleText=raw['oracleText']+'\nActivated abilities of Equipment you control that target this creature cost {1} less to activate.')).supported)
        self.assertFalse(parse_card(dict(raw,oracleText=raw['oracleText'].replace('Equipment you control that target this creature','Auras you control that target this creature'))).supported)

    def test_cycle_three_nonhuman_entry_and_reflexive_x_stack(self):
        real=self.raw('Wildborn Preserver')
        parsed=parse_card(real)
        self.assertTrue(parsed.supported,parsed.reason)
        self.assertEqual(parsed.abilities,frozenset({'flash','reach'}))
        self.assertEqual(parsed.triggers[0].subject.excluded_subtype,'Human')
        self.assertEqual(parsed.triggers[0].effect.payment_cost,'{X}')
        g=Game()
        g.enter(Permanent('preserver',parsed,0))
        def creature(kind):
            return parse_card(dict(name='Unseen '+kind,types=['Creature'],subTypes=[kind],
                                   power='1',toughness='1',oracleText='Reach'))
        g.enter(Permanent('human',creature('Human'),0))
        g.enter(Permanent('enemy-elf',creature('Elf'),1))
        self.assertFalse(any(e.get('operation')=='reflexive_paid_self_counters'
                             for e in g.events))
        g.enter(Permanent('elf',creature('Elf'),0))
        self.assertEqual(sum(e.get('operation')=='reflexive_paid_self_counters'
                             for e in g.events),1)

        sim,cards=self.fixture(['Wildborn Preserver','Lys Alana Huntmaster'])
        source=self.put(sim,cards['Wildborn Preserver'])
        with patch.object(sim,'choose_optional_trigger_x',return_value=2):
            self.put(sim,cards['Lys Alana Huntmaster'])
            self.assertEqual(source.counters,0)
            self.assertEqual(sim.stack.items[-1].payload[0]['operation'],
                             'reflexive_paid_self_counters')
            sim.pass_priority(sim.stack.priority);sim.pass_priority(sim.stack.priority)
        self.assertEqual(source.counters,0)
        self.assertEqual(sim.stack.items[-1].payload[0]['operation'],'reflexive_self_counter')
        self.assertTrue(any(e['kind']=='trigger_payment' for e in sim.events))
        self.drain(sim)
        self.assertEqual(source.counters,2)
        self.assertEqual(sim.effective_card(source).power,4)
        sim.invariant()

    def test_cycle_three_renamed_excluded_subtype_and_source_zone_change(self):
        raw=self.raw('Wildborn Preserver')
        raw['name']='Unseen Canopy Guardian'
        raw['oracleText']=raw['oracleText'].replace('non-Human','non-Elf')
        parsed=parse_card(raw)
        self.assertTrue(parsed.supported,parsed.reason)
        self.assertEqual(parsed.triggers[0].subject.excluded_subtype,'Elf')
        self.assertFalse(parse_card(dict(raw,oracleText=raw['oracleText']+'\nWin the game.')).supported)
        self.assertFalse(parse_card(dict(raw,oracleText=raw['oracleText'].replace('When you do','If you do'))).supported)
        self.assertFalse(parse_card(dict(raw,types=['Artifact'])).supported)

        sim,cards=self.fixture(['Wildborn Preserver','Lys Alana Huntmaster'])
        source=self.put(sim,cards['Wildborn Preserver'])
        with patch.object(sim,'choose_optional_trigger_x',return_value=3):
            self.put(sim,cards['Lys Alana Huntmaster'])
            sim.pass_priority(sim.stack.priority);sim.pass_priority(sim.stack.priority)
        self.assertEqual(sim.stack.items[-1].payload[0]['operation'],'reflexive_self_counter')
        sim.send_to_destination(sim.players[0],source)
        self.drain(sim)
        self.assertEqual(source.counters,0)
        self.assertNotIn(source,sim.players[0].battlefield)
        sim.invariant()

    def test_cycle_three_declined_payment_does_not_create_reflexive_trigger(self):
        sim,cards=self.fixture(['Wildborn Preserver','Lys Alana Huntmaster'])
        source=self.put(sim,cards['Wildborn Preserver'])
        with patch.object(sim,'choose_optional_trigger_payment',return_value=False):
            self.put(sim,cards['Lys Alana Huntmaster']);self.drain(sim)
        self.assertEqual(source.counters,0)
        self.assertFalse(any(e['kind']=='reflexive_trigger_queued' for e in sim.events))
        sim.invariant()


if __name__=='__main__':unittest.main()
