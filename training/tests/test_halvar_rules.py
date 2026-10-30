"""Modal two-spell faces: beginning combat attachment transfers and physical death returns."""
import sys
import unittest
from unittest.mock import patch
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
import test_enchantment_abilities as fixture


class HalvarRuleTests(unittest.TestCase):
    setUpClass=classmethod(fixture.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(fixture.EnchantmentChecks.tearDownClass.__func__)
    token=fixture.EnchantmentChecks.token
    drain=fixture.EnchantmentChecks.drain

    def setup_game(self):
        original=self.lookup['Halvar, God of Battle // Sword of the Realms']
        front=s.import_diagnostic_card(self.rules,original,0,'halvar',{'White'})
        self.assertEqual(front.kind,'creature')
        self.assertEqual(front.modal_spell_face.kind,'equipment')
        self.assertTrue(front.event_definition.combat_reattach)
        self.assertTrue(front.modal_spell_face.event_definition.equipment_return_dying)
        self.assertEqual(front.modal_spell_face.event_definition.attachment[1],'{1}{W}')
        sim=s.Simulator(self.rules,42,decks=(s.demo_deck(0)+[front],s.demo_deck(1)),diagnostic=True)
        sim.manual_priority=True;sim.phase='main';sim.active=0;sim.stack.priority=0
        p=sim.players[0]
        (p.hand if front in p.hand else p.library).remove(front)
        p.hand.append(front);p.mana_pool[0]=9
        return sim,front

    def test_back_face_cast_normalizes_to_front_in_graveyard(self):
        sim,front=self.setup_game();p=sim.players[0]
        choice=next(c for c in sim.legal(0) if c.kind=='cast_modal_back')
        with patch.object(sim,'decide',return_value=choice):sim.step()
        self.drain(sim)
        equip=next(item for item in p.battlefield if item.card.id==front.id)
        self.assertEqual(equip.card.name,'Sword of the Realms')
        sim.send_to_destination(p,equip)
        self.assertEqual(next(card for card in p.graveyard if card.id==front.id).name,
                         'Halvar, God of Battle')
        sim.invariant()

    def test_double_strike_requires_own_creature_enchanted_or_equipped(self):
        sim,front=self.setup_game();p=sim.players[0];p.hand.remove(front)
        host=self.token(sim,'host');other=self.token(sim,'other');enemy=self.token(sim,'enemy',1)
        sim.enter_creature(front,p)
        aura_def=s.EventDefinition('Aura',frozenset({'Enchantment'}),frozenset({'Aura'}),
                                   False,0,0,frozenset(),
                                   attachment=('aura',None,frozenset(),1,1))
        aura=s.Card('testaura','Aura','aura',event_definition=aura_def,
                    is_token=True,printed_types=('Enchantment',))
        sim.enter_creature(aura,p,attached_to=host.card.id)
        self.assertIn('double strike',sim.effective_card(host).traits)
        self.assertNotIn('double strike',sim.effective_card(other).traits)
        self.assertNotIn('double strike',sim.effective_card(enemy).traits)
        sim.invariant()

    def test_beginning_combat_moves_targeted_aura_between_creatures(self):
        sim,front=self.setup_game();p=sim.players[0];p.hand.remove(front)
        sim.enter_creature(front,p)
        host=self.token(sim,'first');second=self.token(sim,'second')
        aura_def=s.EventDefinition('Aura',frozenset({'Enchantment'}),frozenset({'Aura'}),
                                   False,0,0,frozenset(),
                                   attachment=('aura',None,frozenset(),1,1))
        aura=s.Card('testaura','Aura','aura',event_definition=aura_def,
                    is_token=True,printed_types=('Enchantment',))
        sim.enter_creature(aura,p,attached_to=host.card.id)
        triggers=sim.combat_reattach_triggers()
        self.assertEqual(len(triggers),1)
        target=triggers[0][0]['target']
        sim.resolve_entry_triggers([triggers[0][0]],front)
        self.drain(sim)
        self.assertEqual(next(item for item in p.battlefield if item.card.id==aura.id).attached_to,
                         target)
        self.assertNotEqual(target,host.card.id)
        sim.invariant()

    def test_sword_death_trigger_returns_only_card_still_in_graveyard(self):
        sim,front=self.setup_game();p=sim.players[0];p.hand.remove(front)
        from dataclasses import replace
        back=replace(front.modal_spell_face,physical_id=front.id,modal_front_face=front)
        sim.enter_creature(back,p)
        equip=next(item for item in p.battlefield if item.card.id==front.id)
        # A token ceases to exist after leaving the battlefield, so it cannot
        # test a graveyard-to-hand death trigger. Use a physical creature card.
        victim_card=s.Card('victim','victim','creature','{1}{W}',
                           event_definition=s.EventDefinition('victim',
                               frozenset({'Creature'}),frozenset(),False,2,2,frozenset()))
        sim.enter_creature(victim_card,p)
        victim=next(item for item in p.battlefield if item.card.id==victim_card.id)
        equip.attached_to=victim.card.id
        sim.send_to_destination(p,victim)
        self.assertIn(victim.card,p.graveyard)
        sim.resolve_entry_triggers([],back);self.drain(sim)
        self.assertNotIn(victim.card,p.graveyard)
        self.assertIn(victim.card,p.hand)
        sim.invariant()
