"""Whole-text combat-prevention spells resolve on stack and expire at cleanup."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import simulator as s
import test_enchantment_abilities as helpers


class CombatFogSpellChecks(unittest.TestCase):
    setUpClass=classmethod(helpers.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(helpers.EnchantmentChecks.tearDownClass.__func__)
    fixture=helpers.EnchantmentChecks.fixture
    token=helpers.EnchantmentChecks.token
    ready=helpers.EnchantmentChecks.ready
    damage=helpers.EnchantmentChecks.damage
    drain=helpers.EnchantmentChecks.drain

    def test_real_unseen_card_and_full_oracle_rejection(self):
        raw=dict(self.lookup['Fog'],name='Unknown battlefield mist')
        card=s.import_diagnostic_card(self.rules,raw,0,'fog',{'Green'})
        self.assertEqual(card.kind,'prevention_spell')
        self.assertTrue(card.instant)
        self.assertTrue(card.prevent_all_combat_damage)
        raw['manaCost']='{1}{G}'
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'variant',{'Green'}).kind,
                         'prevention_spell')
        raw['oracleText']+='\nDraw a card.'
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'unsafe',{'Green'}).kind,
                         'unsupported')
        raw['oracleText']='Prevent all combat damage that would be dealt to you this turn.'
        limited=s.import_diagnostic_card(self.rules,raw,0,'limited',{'Green'})
        self.assertEqual(limited.kind,'prevention_spell')
        self.assertTrue(limited.prevent_player_combat_damage)
        self.assertFalse(limited.prevent_all_combat_damage)

    def test_stack_resolution_prevents_both_sides_lifelink_and_trample(self):
        sim,cards=self.fixture(['Fog'])
        fog=cards['Fog']
        self.assertIn(fog,sim.players[0].hand)
        sim.cast_spell(0,fog)
        self.assertFalse(sim.combat_damage_prevented)  # No effect before resolution.
        self.assertIn(fog,[frame.payload[1] for frame in sim.stack.items])
        self.drain(sim)
        self.assertTrue(sim.combat_damage_prevented)
        attacker=self.token(sim,'trampling attacker',power=5,toughness=2,keywords=('trample','lifelink'))
        blocker=self.token(sim,'deathtouch blocker',seat=1,power=4,toughness=3,
                           keywords=('deathtouch','lifelink'))
        self.ready(sim)
        sim.declare_attackers([attacker.card.id])
        sim.declare_blockers({attacker.card.id:[blocker.card.id]})
        self.damage(sim)
        self.assertEqual((sim.players[0].life,sim.players[1].life),(40,40))
        self.assertIn(attacker,sim.players[0].battlefield)
        self.assertIn(blocker,sim.players[1].battlefield)
        self.assertEqual((attacker.marked_damage,blocker.marked_damage),(0,0))
        self.assertFalse(sim.damage_to_players[1])
        self.assertIn(fog,sim.players[0].graveyard)
        sim.invariant()

    def test_first_strike_and_noncombat_damage_are_distinct(self):
        sim,cards=self.fixture(['Fog'])
        sim.cast_spell(0,cards['Fog']);self.drain(sim)
        attacker=self.token(sim,'first striker',power=5,toughness=2,keywords=('first strike',))
        blocker=self.token(sim,'opposing lifelinker',seat=1,power=5,toughness=3,
                           keywords=('first strike','lifelink'))
        sim.active=0;sim.phase='first_damage'
        sim.combat_context=dict(attacker=attacker.card.id,blocker=blocker.card.id,
                                blocked=True,early={attacker.card.id,blocker.card.id})
        sim.strike_damage_step(True)
        self.assertEqual((attacker.marked_damage,blocker.marked_damage),(0,0))
        self.assertEqual(sim.players[1].life,40)
        sim._resolve_entry_effects([dict(operation='damage',controller=0,source='unseen',
                                         name='Unseen bolt',amount=3)],cards['Fog'])
        self.assertEqual(sim.players[1].life,37)
        sim.invariant()

    def test_cleanup_expires_prevention_before_next_combat(self):
        sim,cards=self.fixture(['Fog'])
        sim.cast_spell(0,cards['Fog']);self.drain(sim)
        sim.phase='cleanup'
        sim.step()
        self.assertFalse(sim.combat_damage_prevented)
        attacker=self.token(sim,'unblocked attacker',power=3,toughness=3)
        self.ready(sim)
        sim.declare_attackers([attacker.card.id])
        sim.declare_blockers({})
        self.damage(sim)
        self.assertEqual(sim.players[1].life,37)
        sim.invariant()


if __name__=='__main__':unittest.main()
