"""Whole Oracle replacement effects: token creation and all-counter doubling."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
from oracle_abilities import compile_abilities
import test_enchantment_abilities as fixtures

class TokenReplacementsChecks(unittest.TestCase):
    setUpClass=classmethod(fixtures.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.EnchantmentChecks.tearDownClass.__func__)
    fixture=fixtures.EnchantmentChecks.fixture
    put=fixtures.EnchantmentChecks.put
    token=fixtures.EnchantmentChecks.token
    drain=fixtures.EnchantmentChecks.drain

    def create(self,sim,controller=0,amount=2):
        event=dict(operation='create_tokens',effect='create tokens',source='external',
                   name='Unfamiliar token effect',controller=controller,
                   tokenSpec=dict(amount=amount,power=1,toughness=1,subtypes=['Squirrel'],
                                  colors=['Green'],keywords=[],tapped=False))
        sim._resolve_entry_effects([event],s.Card('unknown','Unknown','spell'))

    def token_count(self,sim,seat):
        return sum(p.card.is_token for p in sim.players[seat].battlefield)

    def test_three_oracle_cards_are_name_independent_and_fail_closed(self):
        for name in ('Doubling Season','Primal Vigor','Parallel Lives'):
            raw=dict(self.lookup[name],name='Unknown replacement')
            parsed=s.import_diagnostic_card(self.rules,raw,0,'unknown',{'Green'})
            self.assertNotEqual(parsed.kind,'unsupported',name)
            self.assertEqual(len(parsed.event_definition.token_replacements),1)
            if name!='Parallel Lives':
                self.assertEqual(len(parsed.event_definition.counter_replacements),1)
            else:self.assertEqual(len(parsed.event_definition.counter_replacements),0)
            raw['oracleText']+='\nWhen you fly, create a mystery thing.'
            self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'invalid',set()).kind,'unsupported')
        self.assertIsNone(compile_abilities(
            'If an effect would create one or more tokens under your control, '
            'it creates three random objects instead.'))

    def test_doubling_season_only_doubles_its_own_controllers_tokens(self):
        sim,cards=self.fixture(['Doubling Season'])
        self.put(sim,cards['Doubling Season'])
        self.create(sim,controller=0,amount=2)
        self.create(sim,controller=1,amount=2)
        self.assertEqual((self.token_count(sim,0),self.token_count(sim,1)),(4,2))
        sim.invariant()

    def test_primal_vigor_doubles_both_players_tokens(self):
        sim,cards=self.fixture(['Primal Vigor'])
        self.put(sim,cards['Primal Vigor'])
        self.create(sim,controller=0)
        self.create(sim,controller=1)
        self.assertEqual((self.token_count(sim,0),self.token_count(sim,1)),(4,4))
        sim.invariant()

    def test_independent_replacements_stack_and_leave_independently(self):
        sim,cards=self.fixture(['Doubling Season','Parallel Lives','Primal Vigor'])
        double=self.put(sim,cards['Doubling Season'])
        parallel=self.put(sim,cards['Parallel Lives'])
        vigor=self.put(sim,cards['Primal Vigor'])
        self.assertEqual(sim.event_game('main').token_amount(0,1),8)
        self.assertEqual(sim.event_game('main').token_amount(1,1),2)
        self.create(sim,controller=0,amount=1)
        self.assertEqual(self.token_count(sim,0),8)
        sim.send_to_destination(sim.players[0],double)
        self.assertEqual(sim.event_game('main').token_amount(0,1),4)
        sim.send_to_destination(sim.players[0],parallel)
        self.assertEqual(sim.event_game('main').token_amount(0,1),2)
        sim.send_to_destination(sim.players[0],vigor)
        self.assertEqual(sim.event_game('main').token_amount(0,1),1)
        sim.invariant()

    def test_zero_creation_stays_zero_and_new_token_effects_are_one_event(self):
        sim,cards=self.fixture(['Doubling Season','Primal Vigor'])
        for item in cards.values():self.put(sim,item)
        self.assertEqual(sim.event_game('main').token_amount(0,0),0)
        self.create(sim,amount=0)
        self.assertEqual(self.token_count(sim,0),0)
        self.create(sim,amount=3)
        self.assertEqual(self.token_count(sim,0),12)
        sim.invariant()

    def test_controller_scoped_effect_does_not_apply_outside_effect(self):
        sim,cards=self.fixture(['Doubling Season','Primal Vigor'])
        for item in cards.values():self.put(sim,item)
        self.assertEqual(sim.event_game('main').token_amount(0,2,by_effect=False),4)
        self.assertEqual(sim.event_game('main').token_amount(0,2,by_effect=True),8)
        sim.invariant()

    def test_primal_vigor_counter_replacement_applies_to_both_players(self):
        sim,cards=self.fixture(['Primal Vigor'])
        self.put(sim,cards['Primal Vigor'])
        own=self.token(sim,'own')
        enemy=self.token(sim,'enemy',seat=1)
        game=sim.event_game('main')
        self.assertEqual(game.counter_amount(own.card.id,2),4)
        self.assertEqual(game.counter_amount(enemy.card.id,2),4)
        self.assertEqual(game.counter_amount(own.card.id,2,counter_type='charge'),2)
        sim.invariant()

    def test_doubling_season_doubles_any_effect_counters_on_controlled_permanent(self):
        sim,cards=self.fixture(['Doubling Season'])
        source=self.put(sim,cards['Doubling Season'])
        own=self.token(sim,'own')
        enemy=self.token(sim,'enemy',seat=1)
        game=sim.event_game('main')
        self.assertEqual(game.counter_amount(own.card.id,3),6)
        self.assertEqual(game.counter_amount(enemy.card.id,3),3)
        self.assertEqual(game.counter_amount(source.card.id,2,counter_type='charge'),4)
        self.assertEqual(game.counter_amount(own.card.id,2,by_effect=False),2)
        sim.invariant()

    def test_primal_vigor_and_scales_combine_with_doubling_season(self):
        sim,cards=self.fixture(['Doubling Season','Primal Vigor','Hardened Scales'])
        for item in cards.values():self.put(sim,item)
        own=self.token(sim,'own')
        enemy=self.token(sim,'enemy',seat=1)
        game=sim.event_game('main')
        self.assertEqual(game.counter_amount(own.card.id,1),8)
        self.assertEqual(game.counter_amount(enemy.card.id,1),2)
        sim.invariant()

    def test_token_event_creates_correct_number_of_enter_triggers(self):
        sim,cards=self.fixture(['Parallel Lives',"Ajani's Welcome"])
        for item in cards.values():self.put(sim,item)
        self.create(sim,controller=0,amount=2)
        self.drain(sim)
        self.assertEqual(self.token_count(sim,0),4)
        self.assertEqual(sim.players[0].life,44)
        sim.invariant()
