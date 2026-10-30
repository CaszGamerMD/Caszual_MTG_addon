"""Equipment attack land-search triggers use stack timing and source controller."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
import test_enchantment_abilities as f

class EquipmentLandSearchCycle(unittest.TestCase):
    setUpClass=classmethod(f.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(f.EnchantmentChecks.tearDownClass.__func__)
    fixture=f.EnchantmentChecks.fixture
    put=f.EnchantmentChecks.put
    token=f.EnchantmentChecks.token
    drain=f.EnchantmentChecks.drain
    ready=f.EnchantmentChecks.ready

    def add_basic(self,sim,seat=0):
        basic=s.Card('searched-basic-'+str(seat),'Plains','land',mask=1,
                     basic_land=True,land_subtypes=('Plains',))
        sim.players[seat].library.append(basic)
        sim.card_owners[basic.id]=seat
        counts=list(sim.total_cards);counts[seat]+=1;sim.total_cards=tuple(counts)
        return basic

    def test_unseen_equipment_name_and_strict_unknown_clause(self):
        for name in ('Sword of the Animist',"Bitterthorn, Nissa's Animus"):
            raw=dict(self.lookup[name],name='Unseen adventurer gear')
            card=s.import_diagnostic_card(self.rules,raw,0,'unknown',{'Green'})
            self.assertEqual(card.kind,'equipment')
            self.assertTrue(card.event_definition.equipment_basic_search)
            raw['oracleText']+='\nWhenever equipped creature blocks, gain unknown points.'
            self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'bad',{'Green'}).kind,'unsupported')
        raw=dict(self.lookup['Sword of the Animist'],name='Unseen scout tool')
        raw['oracleText']=raw['oracleText'].replace('Equip {2}','Equip {4}')
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'other',set()).event_definition.attachment[1],'{4}')

    def test_attacker_search_uses_stack_and_enters_tapped(self):
        sim,cards=self.fixture(['Sword of the Animist'])
        attacker=self.token(sim,'attacker')
        basic=self.add_basic(sim)
        equipment=self.put(sim,cards['Sword of the Animist'])
        sim.activate_equip(0,equipment.card.id,attacker.card.id);self.drain(sim)
        self.assertEqual(sim.effective_card(attacker).power,3)
        self.ready(sim);sim.declare_attackers([attacker.card.id])
        self.assertTrue(any(frame.payload[0].get('operation')=='equipment_basic_search' for frame in sim.stack.items))
        self.assertIn(basic,sim.players[0].library)
        self.drain(sim)
        land=next(p for p in sim.players[0].battlefield if p.card.id==basic.id)
        self.assertTrue(land.tapped)
        self.assertNotIn(basic,sim.players[0].library)
        sim.invariant()

    def test_trigger_survives_equipment_leaving(self):
        sim,cards=self.fixture(['Sword of the Animist'])
        attacker=self.token(sim,'attacker');basic=self.add_basic(sim)
        equipment=self.put(sim,cards['Sword of the Animist'])
        sim.activate_equip(0,equipment.card.id,attacker.card.id);self.drain(sim)
        self.ready(sim);sim.declare_attackers([attacker.card.id])
        sim.send_to_destination(sim.players[0],equipment)
        self.drain(sim)
        self.assertTrue(any(p.card.id==basic.id for p in sim.players[0].battlefield))
        sim.invariant()

    def test_living_weapon_composes_with_equipped_attack(self):
        sim,cards=self.fixture(["Bitterthorn, Nissa's Animus"])
        basic=self.add_basic(sim)
        equipment=self.put(sim,cards["Bitterthorn, Nissa's Animus"])
        self.drain(sim)
        germ=next(p for p in sim.players[0].battlefield if p.card.is_token and 'Germ' in p.card.event_definition.subtypes)
        self.assertEqual(equipment.attached_to,germ.card.id)
        self.assertEqual(sim.effective_card(germ).power,1)
        self.ready(sim);sim.declare_attackers([germ.card.id]);self.drain(sim)
        self.assertTrue(any(p.card.id==basic.id for p in sim.players[0].battlefield))
        sim.invariant()

    def test_optional_search_can_decline_without_basic(self):
        sim,cards=self.fixture(['Sword of the Animist'])
        attacker=self.token(sim,'attacker')
        equipment=self.put(sim,cards['Sword of the Animist'])
        sim.activate_equip(0,equipment.card.id,attacker.card.id);self.drain(sim)
        self.ready(sim);sim.declare_attackers([attacker.card.id]);self.drain(sim)
        self.assertTrue(any(e['kind']=='search_declined' for e in sim.events))
        sim.invariant()
