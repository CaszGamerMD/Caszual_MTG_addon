"""Whole-program static-language learning cycles; real cards plus unseen names."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
from oracle_abilities import compile_abilities
import test_enchantment_abilities as fixtures


class ArchetypeSuppressionChecks(unittest.TestCase):
    setUpClass=classmethod(fixtures.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.EnchantmentChecks.tearDownClass.__func__)
    fixture=fixtures.EnchantmentChecks.fixture
    put=fixtures.EnchantmentChecks.put
    token=fixtures.EnchantmentChecks.token

    def test_real_and_unseen_oracle_and_unknown_clause_rejection(self):
        raw=dict(self.lookup['Archetype of Courage'],name='Unseen first strike law')
        parsed=s.import_diagnostic_card(self.rules,raw,0,'unseen',{'White'})
        self.assertEqual(parsed.kind,'creature')
        self.assertEqual(len(parsed.event_definition.static_effects),2)
        self.assertEqual(parsed.event_definition.static_effects[1].suppress,'first strike')
        raw['oracleText']+='\nCreatures get mysterious powers.'
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'bad',{'White'}).kind,'unsupported')
        self.assertIsNone(compile_abilities(
            "Creatures your opponents control lose flying and can't have or gain first strike."))
        self.assertIsNotNone(compile_abilities(
            "Creatures your opponents control lose flying and can't have or gain flying."))

    def test_denial_beats_printed_temporary_and_anthem_grants(self):
        sim,cards=self.fixture(['Archetype of Courage'])
        own=self.token(sim,'ally')
        enemy=self.token(sim,'enemy',seat=1,keywords=('first strike',))
        source=self.put(sim,cards['Archetype of Courage'])
        game=sim.event_game('combat')
        self.assertTrue(game.has(game.battlefield['ally'],'first strike'))
        self.assertFalse(game.has(game.battlefield['enemy'],'first strike'))
        enemy.temporary_abilities=frozenset({'first strike'})
        game=sim.event_game('combat')
        self.assertFalse(game.has(game.battlefield['enemy'],'first strike'))
        self.assertNotIn('first strike',sim.effective_card(enemy).traits)
        sim.send_to_destination(sim.players[0],source)
        self.assertTrue(sim.event_game('combat').has(sim.event_game('combat').battlefield['enemy'],'first strike'))
        sim.invariant()

    def test_suppression_is_scoped_to_opponents_and_disappears_with_source(self):
        sim,cards=self.fixture(['Archetype of Courage'])
        source=self.put(sim,cards['Archetype of Courage'])
        ally=self.token(sim,'ally',keywords=('first strike',))
        foe=self.token(sim,'foe',seat=1,keywords=('first strike',))
        self.assertIn('first strike',sim.effective_card(ally).traits)
        self.assertNotIn('first strike',sim.effective_card(foe).traits)
        sim.send_to_destination(sim.players[0],source)
        self.assertIn('first strike',sim.effective_card(foe).traits)
        sim.invariant()


class SharedCreatureTypesChecks(unittest.TestCase):
    setUpClass=classmethod(fixtures.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.EnchantmentChecks.tearDownClass.__func__)
    fixture=fixtures.EnchantmentChecks.fixture
    put=fixtures.EnchantmentChecks.put
    token=fixtures.EnchantmentChecks.token

    def test_full_real_oracle_and_unseen_names(self):
        raw=dict(self.lookup['Coat of Arms'],name='Unfamiliar shared-type artifact')
        parsed=s.import_diagnostic_card(self.rules,raw,0,'shared',set())
        self.assertEqual(parsed.kind,'artifact')
        self.assertTrue(parsed.event_definition.static_effects[0].share_types)
        raw['oracleText']+='\nWhenever a mystery happens, change reality.'
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'bad',set()).kind,'unsupported')
        self.assertIsNone(compile_abilities(
            'Each creature gets +1/+1 for each other permanent on the battlefield that shares at least one creature type with it.'))

    def test_opponents_and_dual_types_count_once_and_update_dynamically(self):
        sim,cards=self.fixture(['Coat of Arms'])
        first=self.token(sim,'goblin',subtypes=('Goblin',))
        second=self.token(sim,'warrior',seat=1,subtypes=('Goblin','Warrior'))
        third=self.token(sim,'shaman',subtypes=('Goblin','Shaman'))
        elf=self.token(sim,'elf',subtypes=('Elf',))
        source=self.put(sim,cards['Coat of Arms'])
        self.assertEqual([sim.effective_card(p).power for p in (first,second,third,elf)],
                         [4,4,4,2])
        fourth=self.token(sim,'dual',seat=1,subtypes=('Goblin','Warrior'))
        self.assertEqual([sim.effective_card(p).power for p in (first,second,third,fourth)],
                         [5,5,5,5])
        sim.send_to_destination(sim.players[0],third)
        self.assertEqual(sim.effective_card(first).power,4)
        sim.send_to_destination(sim.players[0],source)
        self.assertEqual([sim.effective_card(p).power for p in (first,second,fourth,elf)],
                         [2,2,2,2])
        sim.invariant()

    def test_noncreatures_with_matching_subtypes_do_not_count(self):
        sim,cards=self.fixture(['Coat of Arms'])
        goblin=self.token(sim,'goblin',subtypes=('Goblin',))
        self.put(sim,cards['Coat of Arms'])
        from dataclasses import replace
        fake=s.EventDefinition('Goblin relic',frozenset({'Artifact'}),frozenset({'Goblin'}),
                               False,0,0,frozenset())
        sim.enter_creature(s.Card('relic','Goblin relic','artifact',event_definition=fake,is_token=True),
                           sim.players[1])
        self.assertEqual(sim.effective_card(goblin).power,2)
        sim.invariant()


class GreatestPowerAttackChecks(unittest.TestCase):
    setUpClass=classmethod(fixtures.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.EnchantmentChecks.tearDownClass.__func__)
    fixture=fixtures.EnchantmentChecks.fixture
    put=fixtures.EnchantmentChecks.put
    token=fixtures.EnchantmentChecks.token
    ready=fixtures.EnchantmentChecks.ready
    drain=fixtures.EnchantmentChecks.drain

    def test_full_oracle_program_unseen_name_and_fail_closed(self):
        raw=dict(self.lookup['Orcish Siegemaster'],name='Unknown Orc captain')
        parsed=s.import_diagnostic_card(self.rules,raw,0,'unknown',{'Red'})
        self.assertEqual(parsed.kind,'creature')
        self.assertEqual(parsed.event_definition.attack_effects[0][0],'greatest_power_boost')
        self.assertEqual(len(parsed.event_definition.static_effects),2)
        raw['oracleText']+='\nWhenever you roll a mystery die, draw a card.'
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'bad',{'Red'}).kind,'unsupported')
        from attack_abilities import compile as compile_attacks
        for boost,expected in (('+X/+0',(1,0)),('+0/+X',(0,1)),('+X/+X',(1,1))):
            result=compile_attacks('Whenever this creature attacks, it gets '+boost+
                ' until end of turn, where X is the greatest power among creatures you control.')
            self.assertEqual(result[3][0][1:3],expected)
        self.assertIsNone(compile_attacks(
            'Whenever this creature attacks, it gets +X/+0 until end of turn, where X is the greatest toughness among creatures you control.'))

    def test_other_orcs_and_goblins_gain_trample_but_not_enemies(self):
        sim,cards=self.fixture(['Orcish Siegemaster'])
        self.put(sim,cards['Orcish Siegemaster'])
        orc=self.token(sim,'orc',subtypes=('Orc',))
        goblin=self.token(sim,'goblin',subtypes=('Goblin',))
        dual=self.token(sim,'dual',subtypes=('Orc','Goblin'))
        human=self.token(sim,'human',subtypes=('Human',))
        enemy=self.token(sim,'enemy',seat=1,subtypes=('Goblin',))
        for member in (orc,goblin,dual):
            self.assertIn('trample',sim.effective_card(member).traits)
        for member in (human,enemy):
            self.assertNotIn('trample',sim.effective_card(member).traits)
        sim.invariant()

    def test_attack_bonus_uses_greatest_controlled_power_at_resolution(self):
        sim,cards=self.fixture(['Orcish Siegemaster'])
        source=self.put(sim,cards['Orcish Siegemaster'])
        big=self.token(sim,'big',power=6,toughness=6)
        small=self.token(sim,'small',power=3,toughness=3)
        self.token(sim,'opposing-giant',seat=1,power=15,toughness=15)
        self.ready(sim)
        sim.declare_attackers([source.card.id])
        self.assertEqual(sim.effective_card(source).power,0)
        sim.send_to_destination(sim.players[0],big)
        self.drain(sim)
        self.assertEqual(sim.effective_card(source).power,3)
        self.assertEqual(sim.effective_card(source).toughness,5)
        self.assertIn('trample',sim.effective_card(source).traits)
        sim.invariant()

    def test_attack_trigger_no_longer_buffs_source_after_it_leaves(self):
        sim,cards=self.fixture(['Orcish Siegemaster'])
        source=self.put(sim,cards['Orcish Siegemaster'])
        self.token(sim,'ally',power=4,toughness=4)
        self.ready(sim)
        sim.declare_attackers([source.card.id])
        sim.send_to_destination(sim.players[0],source)
        self.drain(sim)
        self.assertNotIn(source,sim.players[0].battlefield)
        sim.invariant()
