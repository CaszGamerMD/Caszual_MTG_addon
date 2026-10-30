"""Gylwain modal Roles: strict Oracle import, choice, attachment and granted skills."""
import unittest
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
import test_enchantment_abilities as fixtures

NAME='Gylwain, Casting Director'

class SessionLearningModalRoles(unittest.TestCase):
    setUpClass=classmethod(fixtures.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.EnchantmentChecks.tearDownClass.__func__)
    fixture=fixtures.EnchantmentChecks.fixture
    put=fixtures.EnchantmentChecks.put
    token=fixtures.EnchantmentChecks.token
    ready=fixtures.EnchantmentChecks.ready
    drain=fixtures.EnchantmentChecks.drain

    def test_real_unseen_and_strict_unknown_oracle(self):
        raw=dict(self.lookup[NAME])
        card=s.import_diagnostic_card(self.rules,raw,0,'real',{'White','Green'})
        self.assertNotEqual(card.kind,'unsupported')
        self.assertEqual(card.event_definition.modal_role_choices,('Royal','Sorcerer','Monster'))
        raw['name']='Unseen Theater Director'
        raw['oracleText']=raw['oracleText'].replace(NAME,'Unseen Theater Director')
        other=s.import_diagnostic_card(self.rules,raw,0,'renamed',{'White','Green'})
        self.assertNotEqual(other.kind,'unsupported')
        raw['oracleText']+='\nCast a mysterious spell.'
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'unknown',{'White','Green'}).kind,'unsupported')

    def build(self,kind):
        sim,cards=self.fixture([NAME])
        sim.choose_role_kind=lambda event,options: kind
        source=self.put(sim,cards[NAME])
        self.assertEqual(len(sim.stack.items),1)
        return sim,source

    def roles(self,sim):
        return [p for player in sim.players for p in player.battlefield
                if p.card.event_definition and p.card.event_definition.role]

    def test_royal_role_gives_ward_and_base_stats(self):
        sim,source=self.build('Royal')
        self.assertEqual(self.roles(sim),[])
        self.drain(sim)
        role=self.roles(sim)[0]
        self.assertEqual(role.attached_to,source.card.id)
        self.assertEqual(sim.effective_card(source).power,3)
        g=sim.event_game('main')
        self.assertEqual(g.ward_costs(g.battlefield[source.card.id]),('{1}',))
        sim.invariant()

    def test_monster_trample_and_source_leave_after_trigger(self):
        sim,source=self.build('Monster')
        sim.send_to_destination(sim.players[0],source)
        self.drain(sim)
        self.assertEqual(self.roles(sim),[])
        sim.invariant()
        sim,source=self.build('Monster')
        self.drain(sim)
        g=sim.event_game('main')
        self.assertTrue(g.has(g.battlefield[source.card.id],'trample'))
        self.assertEqual(sim.effective_card(source).power,3)
        sim.invariant()

    def test_sorcerer_attack_scries_without_public_card_reveal(self):
        sim,source=self.build('Sorcerer')
        self.drain(sim)
        self.ready(sim)
        before=list(sim.players[0].library)
        sim.choose_scry_bottom=lambda seat,card: True
        sim.declare_attackers([source.card.id])
        self.assertTrue(any(frame.payload[0].get('operation')=='scry' for frame in sim.stack.items))
        self.drain(sim)
        self.assertEqual(sim.players[0].library[0],before[-1])
        self.assertTrue(any(e['kind']=='scry' for e in sim.events))
        self.assertFalse(any(e['kind']=='scry' and
                         before[-1].name in e['message'] for e in sim.events))
        sim.invariant()

    def test_only_nontoken_creature_entries_make_roles(self):
        sim,source=self.build('Royal')
        self.drain(sim)
        before=len(self.roles(sim))
        self.token(sim,'new-token')
        self.drain(sim)
        self.assertEqual(len(self.roles(sim)),before)
        other=next(c for c in sim.players[0].library if c.kind=='creature' and not c.is_token)
        sim.players[0].library.remove(other)
        pending=sim.enter_creature(other,sim.players[0])
        self.assertTrue(any(e.get('operation')=='create_chosen_role' for e in pending))
        sim.resolve_entry_triggers(pending,other)
        self.drain(sim)
        self.assertTrue(any(p.attached_to==other.id for p in self.roles(sim)))
        sim.invariant()
