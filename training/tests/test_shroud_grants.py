"""Shroud is a universal targeting prohibition, not just opponent hexproof."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
import test_enchantment_abilities as fixtures

class ShroudGrantsChecks(unittest.TestCase):
    setUpClass=classmethod(fixtures.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.EnchantmentChecks.tearDownClass.__func__)
    fixture=fixtures.EnchantmentChecks.fixture
    put=fixtures.EnchantmentChecks.put
    token=fixtures.EnchantmentChecks.token
    drain=fixtures.EnchantmentChecks.drain

    def test_real_scion_and_unseen_tribal_card_compile_without_ignored_text(self):
        raw=dict(self.lookup['Scion of Oona'],name='Unseen Faerie source')
        card=s.import_diagnostic_card(self.rules,raw,0,'scion',{'Blue'})
        self.assertEqual(card.kind,'creature')
        self.assertEqual({e.grant for e in card.event_definition.static_effects if e.grant},{'shroud'})
        self.assertTrue(all(e.subject.other for e in card.event_definition.static_effects))
        changed=dict(raw,oracleText='Flash\nFlying\nOther Goblin creatures you control get +2/+1.\nOther Goblins you control have shroud.')
        goblins=s.import_diagnostic_card(self.rules,changed,0,'unknown',{'Red'})
        self.assertEqual(goblins.kind,'creature')
        self.assertEqual(goblins.event_definition.static_effects[0].subject.subtype,'Goblin')
        changed['oracleText']+='\nWhenever a star falls, draw a bonus card.'
        self.assertEqual(s.import_diagnostic_card(self.rules,changed,0,'bad',set()).kind,'unsupported')

    def test_scion_grants_other_faeries_shroud_and_an_anthem_only_to_own(self):
        sim,cards=self.fixture(['Scion of Oona'])
        source=self.put(sim,cards['Scion of Oona'])
        friend=self.token(sim,'friendly',subtypes=('Faerie',))
        enemy=self.token(sim,'enemy',seat=1,subtypes=('Faerie',))
        elf=self.token(sim,'elf',subtypes=('Elf',))
        self.assertEqual(sim.effective_card(friend).power,3)
        self.assertTrue(sim.event_game('main').has(sim.event_game('main').battlefield[friend.card.id],'shroud'))
        self.assertEqual(sim.effective_card(source).power,1)
        self.assertNotIn('shroud',sim.effective_card(source).traits)
        self.assertEqual(sim.effective_card(enemy).power,2)
        self.assertNotIn('shroud',sim.effective_card(enemy).traits)
        self.assertEqual(sim.effective_card(elf).power,2)
        sim.send_to_destination(sim.players[0],source)
        self.assertEqual(sim.effective_card(friend).power,2)
        self.assertFalse(sim.event_game('main').has(sim.event_game('main').battlefield[friend.card.id],'shroud'))
        sim.invariant()

    def test_shroud_blocks_own_and_opposing_removal_and_auras(self):
        sim,cards=self.fixture(['Scion of Oona','Swords to Plowshares','Lifelink'])
        source=self.put(sim,cards['Scion of Oona'])
        own=self.token(sim,'own',subtypes=('Faerie',))
        other=self.token(sim,'other',seat=1,subtypes=('Faerie',))
        for seat in (0,1):
            self.assertNotIn(own.card.id,{p.card.id for _,p in sim.creature_targets(seat)})
        self.assertIn(other.card.id,{p.card.id for _,p in sim.creature_targets(0)})
        with self.assertRaises(ValueError):sim.cast_spell(0,cards['Swords to Plowshares'],target=own.card.id)
        with self.assertRaises(ValueError):sim.cast_spell(0,cards['Lifelink'],target=own.card.id)
        sim.send_to_destination(sim.players[0],source)
        self.assertIn(own.card.id,{p.card.id for _,p in sim.creature_targets(0)})
        sim.invariant()

    def test_equipment_cannot_target_shrouded_own_creature_and_roles_cannot_either(self):
        sim,cards=self.fixture(['Scion of Oona','Basilisk Collar'])
        self.put(sim,cards['Scion of Oona'])
        target=self.token(sim,'own',subtypes=('Faerie',))
        collar=self.put(sim,cards['Basilisk Collar'])
        with self.assertRaisesRegex(ValueError,'Illegal equip target'):
            sim.activate_equip(0,collar.card.id,target.card.id)
        self.assertFalse(any(p.card.id==target.card.id for p in sim.role_targets(
            {'source':collar.card.id,'controller':0,'sourceColors':[]})))
        sim.invariant()

    def test_shroud_does_not_cancel_existing_equipment_or_prevent_combat(self):
        sim,cards=self.fixture(['Scion of Oona','Basilisk Collar'])
        target=self.token(sim,'own',subtypes=('Faerie',))
        collar=self.put(sim,cards['Basilisk Collar'])
        sim.activate_equip(0,collar.card.id,target.card.id)
        self.drain(sim)
        self.assertIn('lifelink',sim.effective_card(target).traits)
        self.put(sim,cards['Scion of Oona'])
        self.assertEqual(next(p for p in sim.players[0].battlefield if p.card.id==collar.card.id).attached_to,target.card.id)
        self.assertIn('shroud',sim.effective_card(target).traits)
        target.fresh=False
        self.assertIn(target,sim.attackable(0)) # Shroud does not prevent attacking.
        sim.invariant()
