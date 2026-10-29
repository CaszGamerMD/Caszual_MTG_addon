"""Living weapon creates real Germ tokens before attaching Equipment."""
import unittest
import test_enchantment_abilities as fixtures
import simulator as s

class LivingWeaponChecks(unittest.TestCase):
    setUpClass=classmethod(fixtures.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.EnchantmentChecks.tearDownClass.__func__)
    fixture=fixtures.EnchantmentChecks.fixture
    put=fixtures.EnchantmentChecks.put
    drain=fixtures.EnchantmentChecks.drain

    def test_actual_and_unseen_equipment_reject_unknown_clauses(self):
        for name in ('Batterbone','Nettlecyst'):
            raw=dict(self.lookup[name],name='Unseen Germ gear')
            card=s.import_diagnostic_card(self.rules,raw,0,'unseen',set())
            self.assertEqual(card.kind,'equipment')
            self.assertTrue(card.event_definition.living_weapon)
            raw['oracleText']+='\nDo something mysterious.'
            self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'bad',set()).kind,'unsupported')
        self.assertEqual(s.import_diagnostic_card(self.rules,self.lookup["Bitterthorn, Nissa's Animus"],
                         0,'bitter',set()).kind,'unsupported')

    def test_cast_creates_germ_after_trigger_and_equips_before_state_actions(self):
        sim,cards=self.fixture(['Batterbone'])
        gear=cards['Batterbone']
        sim.cast_spell(0,gear)
        self.assertEqual(len(sim.stack.items),1)
        self.drain(sim)
        equipped=next(p for p in sim.players[0].battlefield if p.card.id==gear.id)
        germs=[p for p in sim.players[0].battlefield if p.card.is_token and 'Germ' in p.card.event_definition.subtypes]
        self.assertEqual(len(germs),1)
        self.assertEqual(equipped.attached_to,germs[0].card.id)
        self.assertEqual((sim.effective_card(germs[0]).power,sim.effective_card(germs[0]).toughness),(1,1))
        for keyword in ('vigilance','lifelink'):self.assertIn(keyword,sim.effective_card(germs[0]).traits)
        sim.invariant()

    def test_equipment_removed_before_trigger_creates_doomed_zero_zero(self):
        sim,cards=self.fixture(['Batterbone'])
        gear=self.put(sim,cards['Batterbone'])
        self.assertEqual(len(sim.stack.items),1)
        sim.send_to_destination(sim.players[0],gear)
        self.drain(sim)
        self.assertFalse(any(p.card.is_token and 'Germ' in p.card.event_definition.subtypes
                             for p in sim.players[0].battlefield))
        self.assertEqual(sim.token_sequence,1)
        sim.invariant()

    def test_doubling_creates_two_germs_but_only_equipped_one_survives(self):
        sim,cards=self.fixture(['Batterbone','Parallel Lives'])
        self.put(sim,cards['Parallel Lives'])
        gear=self.put(sim,cards['Batterbone'])
        self.drain(sim)
        germs=[p for p in sim.players[0].battlefield if p.card.is_token and 'Germ' in p.card.event_definition.subtypes]
        self.assertEqual(len(germs),1)
        self.assertEqual(sim.token_sequence,2)
        self.assertEqual(gear.attached_to,germs[0].card.id)
        sim.invariant()

    def test_nettlecyst_scales_from_artifacts_and_enchantments(self):
        sim,cards=self.fixture(['Nettlecyst','Parallel Lives'])
        self.put(sim,cards['Parallel Lives'])
        gear=self.put(sim,cards['Nettlecyst'])
        self.drain(sim)
        germ=next(p for p in sim.players[0].battlefield if p.card.is_token and 'Germ' in p.card.event_definition.subtypes)
        self.assertEqual(gear.attached_to,germ.card.id)
        self.assertEqual(sim.effective_card(germ).power,2)
        self.assertEqual(sim.effective_card(germ).toughness,2)
        sim.invariant()
