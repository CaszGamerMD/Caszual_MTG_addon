"""Pilot crew/saddle contributions and non-stacking OR-subtype anthems."""
import sys
import unittest
from dataclasses import replace
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
import test_enchantment_abilities as fixtures

class TransportPilotChecks(unittest.TestCase):
    setUpClass=classmethod(fixtures.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.EnchantmentChecks.tearDownClass.__func__)
    fixture=fixtures.EnchantmentChecks.fixture
    put=fixtures.EnchantmentChecks.put
    token=fixtures.EnchantmentChecks.token
    drain=fixtures.EnchantmentChecks.drain

    def test_real_renamed_parameters_and_reject_unknown_clauses(self):
        for name in ('Cloudspire Captain','Dynamite Diver'):
            raw=dict(self.lookup[name]);real=s.import_diagnostic_card(self.rules,raw,0,'real',{'White','Red'})
            self.assertEqual(real.kind,'creature')
            self.assertEqual(real.event_definition.pilot_bonus,2)
            raw['name']='Unseen transport helper'
            raw['oracleText']=raw['oracleText'].replace('power were 2 greater','power were 4 greater')
            new=s.import_diagnostic_card(self.rules,raw,0,'new',{'White','Red'})
            self.assertEqual(new.event_definition.pilot_bonus,4)
            raw['oracleText']+='\nCreatures gain an unrecognized power.'
            self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'bad',{'White','Red'}).kind,'unsupported')

    def test_or_anthem_counts_dual_type_once_and_ceases_on_source_leave(self):
        sim,cards=self.fixture(['Cloudspire Captain'])
        mount=self.token(sim,'mount',subtypes=('Mount',))
        vehicle=self.token(sim,'vehicle',subtypes=('Vehicle',))
        both=self.token(sim,'both',subtypes=('Mount','Vehicle'))
        outsider=self.token(sim,'outsider',subtypes=('Human',))
        enemy=self.token(sim,'enemy',seat=1,subtypes=('Mount',))
        source=self.put(sim,cards['Cloudspire Captain'])
        self.assertEqual([sim.effective_card(x).power for x in (mount,vehicle,both,outsider,enemy)],[3,3,3,2,2])
        self.assertEqual(sim.effective_card(source).power,2)
        sim.send_to_destination(sim.players[0],source)
        self.assertEqual(sim.effective_card(both).power,2)
        sim.invariant()

    def test_pilot_counts_only_for_crew_and_mandatory_death_damage_targets(self):
        sim,cards=self.fixture(['Dynamite Diver'])
        diver=self.put(sim,cards['Dynamite Diver'])
        self.assertEqual(sim.effective_card(diver).power,1)
        raw=dict(name='Unseen Vehicle',types=['Artifact'],subTypes=['Vehicle'],superTypes=[],
                 manaCost='{2}',power='3',toughness='3',oracleText='Crew 3',colors=[],colorIdentity=[])
        vehicle=s.import_diagnostic_card(self.rules,raw,0,'v',set())
        sim.enter_creature(replace(vehicle,is_token=True),sim.players[0])
        game=sim.event_game('main');game.crew(vehicle.id,[diver.card.id],0);sim.sync_events(game)
        self.assertTrue(next(p for p in sim.players[0].battlefield if p.card.id==vehicle.id).animated)
        self.assertEqual(sim.effective_card(diver).power,1)
        life=sim.players[1].life
        sim.destroy_batch([(0,diver)],diver.card)
        self.assertTrue(any(frame.payload[0]['operation']=='damage_any_target' for frame in sim.stack.items))
        self.drain(sim)
        self.assertEqual(sim.players[1].life,life-1)
        sim.invariant()
