"""Typed removal plus independent token-creation clause on the same spell."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
import test_enchantment_abilities as fixtures

class DestroyAndCreateChecks(unittest.TestCase):
    setUpClass=classmethod(fixtures.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.EnchantmentChecks.tearDownClass.__func__)
    fixture=fixtures.EnchantmentChecks.fixture
    put=fixtures.EnchantmentChecks.put
    token=fixtures.EnchantmentChecks.token
    drain=fixtures.EnchantmentChecks.drain

    def artifact(self,sim,identifier='artifact',seat=1,abilities=()):
        d=s.EventDefinition(identifier,frozenset({'Artifact'}),frozenset(),
                            False,0,0,frozenset(abilities))
        card=s.Card(identifier,identifier,'artifact',event_definition=d,
                    printed_types=('Artifact',),is_token=True)
        sim.enter_creature(card,sim.players[seat])
        return next(p for p in sim.players[seat].battlefield if p.card.id==identifier)

    def oxen(self,sim,seat):
        return [p for p in sim.players[seat].battlefield
                if p.card.is_token and p.card.name=='Ox']

    def test_unknown_card_name_compiles_and_extra_text_rejects(self):
        raw=dict(self.lookup['Bovine Intervention'],name='Unknown cow ritual')
        card=s.import_diagnostic_card(self.rules,raw,0,'cow',{'White'})
        self.assertEqual((card.kind,card.removal),('removal_spell','destroy_target_token'))
        self.assertEqual(set(card.removal_target_types),{'Artifact','Creature'})
        self.assertEqual((card.token_definition.name,card.token_count),('Ox',1))
        raw['oracleText']+='\nDraw three mysterious cards.'
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'bad',{'White'}).kind,'unsupported')

    def test_enemy_creature_destroyed_and_its_controller_gets_ox(self):
        sim,cards=self.fixture(['Bovine Intervention'])
        creature=self.token(sim,'enemy',seat=1,power=6,toughness=6)
        sim.cast_spell(0,cards['Bovine Intervention'],target=creature.card.id)
        self.assertFalse(self.oxen(sim,1))
        self.drain(sim)
        self.assertNotIn(creature,sim.players[1].battlefield)
        self.assertEqual(len(self.oxen(sim,1)),1)
        self.assertEqual((self.oxen(sim,1)[0].card.power,self.oxen(sim,1)[0].card.toughness),(2,2))
        self.assertFalse(self.oxen(sim,0))
        sim.invariant()

    def test_nontoken_artifact_is_legal_removal_target(self):
        sim,cards=self.fixture(['Bovine Intervention'])
        artifact=self.artifact(sim)
        sim.cast_spell(0,cards['Bovine Intervention'],target=artifact.card.id)
        self.drain(sim)
        self.assertNotIn(artifact,sim.players[1].battlefield)
        self.assertEqual(len(self.oxen(sim,1)),1)
        sim.invariant()

    def test_indestructible_still_gets_token_for_controller(self):
        sim,cards=self.fixture(['Bovine Intervention'])
        target=self.token(sim,'safe',seat=1,keywords=('indestructible',))
        sim.cast_spell(0,cards['Bovine Intervention'],target=target.card.id)
        self.drain(sim)
        self.assertIn(target,sim.players[1].battlefield)
        self.assertEqual(len(self.oxen(sim,1)),1)
        sim.invariant()

    def test_target_missing_on_resolution_creates_no_token(self):
        sim,cards=self.fixture(['Bovine Intervention'])
        target=self.token(sim,'missing',seat=1)
        sim.cast_spell(0,cards['Bovine Intervention'],target=target.card.id)
        sim.send_to_destination(sim.players[1],target)
        self.drain(sim)
        self.assertFalse(self.oxen(sim,1))
        sim.invariant()

    def test_opposing_hexproof_blocks_casting_but_not_indestructible(self):
        sim,cards=self.fixture(['Bovine Intervention'])
        target=self.token(sim,'warded',seat=1,keywords=('hexproof',))
        with self.assertRaisesRegex(ValueError,'legal permanent'):
            sim.cast_spell(0,cards['Bovine Intervention'],target=target.card.id)
        self.assertIn(cards['Bovine Intervention'],sim.players[0].hand)
        sim.invariant()

    def test_doublers_apply_under_controller_receiving_token(self):
        sim,cards=self.fixture(['Bovine Intervention','Doubling Season'])
        self.put(sim,cards['Doubling Season'])
        owned=self.token(sim,'own')
        sim.cast_spell(0,cards['Bovine Intervention'],target=owned.card.id)
        self.drain(sim)
        self.assertEqual(len(self.oxen(sim,0)),2)
        sim.invariant()

    def test_token_watchers_observe_created_oxen(self):
        sim,cards=self.fixture(['Bovine Intervention','Mirkwood Bats'])
        self.put(sim,cards['Mirkwood Bats'])
        owned=self.token(sim,'own')
        sim.cast_spell(0,cards['Bovine Intervention'],target=owned.card.id)
        self.drain(sim)
        self.assertEqual(len(self.oxen(sim,0)),1)
        self.assertEqual(sim.players[1].life,39)
        sim.invariant()

    def test_beast_within_and_unseen_permanent_wording_compile_whole_text(self):
        for name in ('Beast Within','Unseen wilderness removal'):
            raw=dict(self.lookup['Beast Within'],name=name)
            card=s.import_diagnostic_card(self.rules,raw,0,'beast',{'Green'})
            self.assertEqual((card.kind,card.removal),('removal_spell','destroy_target_token'))
            self.assertEqual(card.removal_target_types,('Permanent',))
            self.assertEqual((card.token_definition.name,card.token_count),('Beast',1))
            raw['oracleText']+=' Draw a card.'
            self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'bad',{'Green'}).kind,'unsupported')

    def test_permanent_target_can_be_land_or_enchantment(self):
        for types in (('Land',),('Enchantment',),('Planeswalker',)):
            sim,cards=self.fixture(['Beast Within'])
            identifier='target-'+types[0]
            definition=s.EventDefinition(identifier,frozenset(types),frozenset(),False,0,0,frozenset())
            target=s.Card(identifier,identifier,types[0].lower(),event_definition=definition,
                          printed_types=types,is_token=True)
            sim.players[1].battlefield.append(s.Permanent(target))
            sim.cast_spell(0,cards['Beast Within'],target=identifier)
            self.assertTrue(any(p.card.id==identifier for p in sim.players[1].battlefield))
            self.drain(sim)
            self.assertFalse(any(p.card.id==identifier for p in sim.players[1].battlefield))
            beasts=[p for p in sim.players[1].battlefield if p.card.name=='Beast']
            self.assertEqual(len(beasts),1)
            self.assertEqual((beasts[0].card.power,beasts[0].card.toughness),(3,3))
            sim.invariant()

    def test_target_controller_gets_token_even_if_permanent_indestructible(self):
        sim,cards=self.fixture(['Beast Within'])
        target=self.artifact(sim,abilities=('indestructible',))
        sim.cast_spell(0,cards['Beast Within'],target=target.card.id)
        self.drain(sim)
        self.assertIn(target,sim.players[1].battlefield)
        self.assertEqual(len([p for p in sim.players[1].battlefield if p.card.name=='Beast']),1)
        sim.invariant()

    def test_unseen_target_filter_and_token_characteristics(self):
        raw=dict(self.lookup['Beast Within'],name='Mysterious target and token',
                 oracleText='Destroy target enchantment. Its controller creates two 1/1 blue Bird creature tokens.')
        card=s.import_diagnostic_card(self.rules,raw,0,'birds',{'Green'})
        self.assertEqual(card.removal_target_types,('Enchantment',))
        self.assertEqual(card.token_count,2)
        self.assertEqual((card.token_definition.power,card.token_definition.toughness),(1,1))
        sim,cards=self.fixture(['Beast Within'])
        sim.players[0].hand.remove(cards['Beast Within'])
        sim.players[0].hand.append(card)
        artifact=self.artifact(sim)
        with self.assertRaisesRegex(ValueError,'legal permanent'):
            sim.cast_spell(0,card,target=artifact.card.id)
        sim.invariant()

    def test_phased_out_permanent_cannot_be_targeted_or_create_token(self):
        sim,cards=self.fixture(['Beast Within'])
        target=self.artifact(sim)
        target.phased_out=True
        with self.assertRaisesRegex(ValueError,'legal permanent'):
            sim.cast_spell(0,cards['Beast Within'],target=target.card.id)
        self.assertIn(cards['Beast Within'],sim.players[0].hand)
        self.assertFalse(any(p.card.name=='Beast' for p in sim.players[1].battlefield))
        sim.invariant()
