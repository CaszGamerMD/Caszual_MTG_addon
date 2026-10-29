"""Source keywords and Oxford-comma grants compose without name dispatch."""
import unittest
import test_enchantment_abilities as fixtures
import simulator as s
from attachments import parse

class AttachmentLanguageChecks(unittest.TestCase):
    setUpClass=classmethod(fixtures.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.EnchantmentChecks.tearDownClass.__func__)
    fixture=fixtures.EnchantmentChecks.fixture
    put=fixtures.EnchantmentChecks.put
    token=fixtures.EnchantmentChecks.token
    drain=fixtures.EnchantmentChecks.drain

    def test_renamed_equipment_consumes_all_rules(self):
        for name in ('Darksteel Plate','Sword of Vengeance'):
            raw=dict(self.lookup[name],name='Unseen equipment')
            self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'item',set()).kind,'equipment')
            raw['oracleText']+='\nDraw a mystery card.'
            self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'item',set()).kind,'unsupported')
        for words in ('first strike, vigilance, trample, and haste','first strike, vigilance, trample and haste'):
            parsed=parse('Equipped creature has '+words+'.\nEquip {2}',{'Artifact'},{'Equipment'})
            self.assertEqual(parsed[2],frozenset({'first strike','vigilance','trample','haste'}))
        self.assertIsNone(parse('Equipped creature has flying, vigilance, and mystery.\nEquip {2}',{'Artifact'},{'Equipment'}))

    def test_plate_source_and_host_indestructibility_are_independent(self):
        sim,cards=self.fixture(['Darksteel Plate'])
        host=self.token(sim,'host');other=self.token(sim,'other')
        plate=self.put(sim,cards['Darksteel Plate'])
        game=sim.event_game('main')
        self.assertTrue(game.has(game.battlefield[plate.card.id],'indestructible'))
        self.assertFalse(game.has(game.battlefield[host.card.id],'indestructible'))
        sim.activate_equip(0,plate.card.id,host.card.id);self.drain(sim)
        self.assertIn('indestructible',sim.effective_card(host).traits)
        sim.activate_equip(0,plate.card.id,other.card.id);self.drain(sim)
        self.assertNotIn('indestructible',sim.effective_card(host).traits)
        self.assertIn('indestructible',sim.effective_card(other).traits)
        sim.invariant()

    def test_sword_grants_stats_and_all_keywords_only_when_equipped(self):
        sim,cards=self.fixture(['Sword of Vengeance'])
        host=self.token(sim,'host');sword=self.put(sim,cards['Sword of Vengeance'])
        sim.activate_equip(0,sword.card.id,host.card.id);self.drain(sim)
        card=sim.effective_card(host)
        self.assertEqual((card.power,card.toughness),(4,2))
        for keyword in ('first strike','vigilance','trample','haste'):self.assertIn(keyword,card.traits)
        self.assertFalse(sword.card.event_definition.abilities)
        sim.send_to_destination(sim.players[0],sword,to_exile=True)
        self.assertEqual(sim.effective_card(host).power,2)
        self.assertNotIn('haste',sim.effective_card(host).traits)
        sim.invariant()
