"""Global tribal lords and five basic-landwalk blocking restrictions.

Cards are parsed from full Oracle rules, not selected by their name.
"""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
from oracle_abilities import compile_abilities
import test_enchantment_abilities as fixtures

class LandwalkLordChecks(unittest.TestCase):
    setUpClass=classmethod(fixtures.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.EnchantmentChecks.tearDownClass.__func__)
    fixture=fixtures.EnchantmentChecks.fixture
    put=fixtures.EnchantmentChecks.put
    token=fixtures.EnchantmentChecks.token
    drain=fixtures.EnchantmentChecks.drain

    def land(self,sim,identifier,subtypes,seat):
        # The game kernel sees Land + its basic land subtypes, even on nonbasic
        # duals and land tokens. This should not be implemented as a name test.
        definition=s.EventDefinition(identifier,frozenset({'Land'}),frozenset(subtypes),
                                     False,0,0,frozenset())
        card=s.Card(identifier,identifier,'land',mask=31,land_subtypes=tuple(subtypes),
                    event_definition=definition,is_token=True,printed_types=('Land',))
        sim.enter_creature(card,sim.players[seat])
        return next(p for p in sim.players[seat].battlefield if p.card.id==identifier)

    def prepare(self):
        sim,cards=self.fixture(['Goblin King'])
        lord=self.put(sim,cards['Goblin King'])
        friend=self.token(sim,'friendly',subtypes=('Goblin',),power=2,toughness=2)
        opponent=self.token(sim,'enemy',seat=1,subtypes=('Goblin',),power=2,toughness=2)
        blocker=self.token(sim,'blocker',seat=1,power=2,toughness=2)
        return sim,lord,friend,opponent,blocker

    def test_real_lord_and_unseen_tribes_numbers_and_landwalk(self):
        saved=dict(self.lookup['Goblin King'])
        card=s.import_diagnostic_card(self.rules,saved,0,'king',{'Red'})
        self.assertEqual(card.kind,'creature')
        self.assertEqual(len(card.event_definition.static_effects),2)
        self.assertEqual(card.event_definition.static_effects[1].grant,'mountainwalk')
        for tribe,land_type in (('Goblins','mountain'),('Faeries','island'),
                                ('Elves','forest'),('Wolves','plains'),('Merfolk','swamp')):
            unknown=dict(saved,name='Unknown lord',oracleText=
                         f'Other {tribe} get +2/+3 and have {land_type}walk.')
            parsed=s.import_diagnostic_card(self.rules,unknown,0,'unknown',set())
            self.assertEqual(parsed.kind,'creature',(tribe,land_type))
            self.assertEqual(parsed.event_definition.static_effects[0].power,2)
            self.assertEqual(parsed.event_definition.static_effects[1].grant,land_type+'walk')
            unknown['oracleText']+='\nDraw an extra card.'
            self.assertEqual(s.import_diagnostic_card(self.rules,unknown,0,'bad',set()).kind,'unsupported')
        self.assertIsNone(compile_abilities('Other Imaginaries get +2/+3 and have mountainwalk.'))
        self.assertIsNone(compile_abilities('Other Goblins get +2/+3 and have moonwalk.'))

    def test_global_lord_buffs_both_controllers_other_than_itself(self):
        sim,lord,friend,opponent,_=self.prepare()
        self.assertEqual((sim.effective_card(lord).power,sim.effective_card(lord).toughness),(2,2))
        self.assertEqual((sim.effective_card(friend).power,sim.effective_card(friend).toughness),(3,3))
        self.assertEqual((sim.effective_card(opponent).power,sim.effective_card(opponent).toughness),(3,3))
        for item in (friend,opponent):
            self.assertIn('mountainwalk',sim.effective_card(item).traits)
        self.assertNotIn('mountainwalk',sim.effective_card(lord).traits)
        sim.send_to_destination(sim.players[0],lord)
        self.assertEqual(sim.effective_card(friend).power,2)
        self.assertNotIn('mountainwalk',sim.effective_card(opponent).traits)
        sim.invariant()

    def test_defending_mountain_blocks_every_legal_blocker_and_is_rechecked(self):
        sim,lord,friend,_,blocker=self.prepare()
        self.land(sim,'dual',('Mountain','Forest'),seat=1)
        game=sim.event_game('combat')
        self.assertTrue(sim.landwalk_unblockable(friend,game))
        self.assertFalse(sim.can_block(friend,blocker))
        sim.phase='attack';sim.stack.priority=sim.active
        for p in sim.players[0].battlefield:p.fresh=False
        sim.declare_attackers([friend.card.id])
        self.assertFalse(any(choice.blocks for choice in sim.group_block_choices(1)))
        with self.assertRaisesRegex(ValueError,'Illegal or duplicate blocker'):
            sim.declare_blockers({friend.card.id:[blocker.card.id]})
        sim.declare_blockers({})
        while sim.group_combat is not None:
            sim.group_damage_step()
            self.drain(sim)
        self.assertEqual(sim.players[1].life,37) # Lord gives friend +1 power
        sim.invariant()

    def test_attacker_controls_mountain_does_not_grant_unblockable(self):
        sim,_,friend,_,blocker=self.prepare()
        self.land(sim,'own-mountain',('Mountain',),seat=0)
        self.assertFalse(sim.landwalk_unblockable(friend))
        self.assertTrue(sim.can_block(friend,blocker))
        sim.invariant()

    def test_untyped_land_does_not_count_but_basic_land_does(self):
        sim,lord,friend,_,blocker=self.prepare()
        self.land(sim,'wastes',(),seat=1)
        self.assertTrue(sim.can_block(friend,blocker))
        forest=self.land(sim,'forest',('Forest',),seat=1)
        self.assertTrue(sim.can_block(friend,blocker))
        sim.send_to_destination(sim.players[1],forest)
        mountain=self.land(sim,'mountain',('Mountain',),seat=1)
        self.assertFalse(sim.can_block(friend,blocker))
        sim.send_to_destination(sim.players[0],lord)
        self.assertTrue(sim.can_block(friend,blocker))
        sim.invariant()

    def test_intrinsic_keyword_obeys_same_check_without_lord(self):
        sim,_=self.fixture([])
        elf=self.token(sim,'traveler',subtypes=('Elf',),keywords=('islandwalk',))
        blocker=self.token(sim,'defender',seat=1)
        self.assertTrue(sim.can_block(elf,blocker))
        self.land(sim,'dual-island',('Island','Swamp'),seat=1)
        self.assertFalse(sim.can_block(elf,blocker))
        sim.invariant()
