"""Global subtype lords combine numeric bonuses with actual landwalk restrictions."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
import test_enchantment_abilities as fixtures

class GlobalLordLandwalkCycle(unittest.TestCase):
    setUpClass=classmethod(fixtures.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.EnchantmentChecks.tearDownClass.__func__)
    fixture=fixtures.EnchantmentChecks.fixture
    put=fixtures.EnchantmentChecks.put
    token=fixtures.EnchantmentChecks.token

    def test_real_unseen_variant_and_fail_closed(self):
        raw=self.lookup['Elvish Champion']
        card=s.import_diagnostic_card(self.rules,raw,0,'champion',{'Green'})
        self.assertEqual(card.kind,'creature')
        self.assertEqual(len(card.event_definition.static_effects),2)
        self.assertEqual(card.event_definition.static_effects[0].subject.subtype,'Elf')
        variant=dict(raw,name='Unseen Mountain Chief',subTypes=['Goblin'],
            oracleText='Other Goblin creatures get +2/+3 and have mountainwalk.')
        parsed=s.import_diagnostic_card(self.rules,variant,0,'unseen',{'Green'})
        self.assertEqual(parsed.kind,'creature')
        self.assertEqual(parsed.event_definition.static_effects[0].power,2)
        self.assertEqual(parsed.event_definition.static_effects[0].toughness,3)
        self.assertEqual(parsed.event_definition.static_effects[1].grant,'mountainwalk')
        for text in ('Other Goblin creatures get +2/+3 and have banana-walk.',
                     'Other Goblin creatures get +2/+3 and have mountainwalk.\nWin the game.'):
            variant['oracleText']=text
            self.assertEqual(s.import_diagnostic_card(self.rules,variant,0,'bad',{'Green'}).kind,'unsupported')

    def test_both_players_benefit_other_only_and_removal_reverses(self):
        sim,cards=self.fixture(['Elvish Champion'])
        champion=self.put(sim,cards['Elvish Champion'])
        own=self.token(sim,'own',seat=0,subtypes=('Elf',))
        enemy=self.token(sim,'enemy',seat=1,subtypes=('Elf',))
        goblin=self.token(sim,'goblin',seat=0,subtypes=('Goblin',))
        game=sim.event_game('main')
        self.assertEqual(sim.effective_card(champion).power,2)
        for elf in (own,enemy):
            self.assertEqual(sim.effective_card(elf).power,3)
            self.assertTrue(game.has(game.battlefield[elf.card.id],'forestwalk'))
        self.assertEqual(sim.effective_card(goblin).power,2)
        self.assertFalse(game.has(game.battlefield[goblin.card.id],'forestwalk'))
        sim.send_to_destination(sim.players[0],champion)
        game=sim.event_game('main')
        for elf in (own,enemy):
            self.assertEqual(sim.effective_card(elf).power,2)
            self.assertFalse(game.has(game.battlefield[elf.card.id],'forestwalk'))
        sim.invariant()

if __name__=='__main__':unittest.main()
