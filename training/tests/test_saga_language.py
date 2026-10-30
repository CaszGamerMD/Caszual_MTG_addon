"""Saga front and transformed back, lore/chapter timing and physical identity."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
import test_enchantment_abilities as fixture


class SagaLanguageChecks(unittest.TestCase):
    setUpClass=classmethod(fixture.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(fixture.EnchantmentChecks.tearDownClass.__func__)
    token=fixture.EnchantmentChecks.token
    drain=fixture.EnchantmentChecks.drain

    def prepare(self):
        raw=self.lookup["Michiko's Reign of Truth // Portrait of Michiko"]
        card=s.import_diagnostic_card(self.rules,raw,0,'saga',{'White'})
        self.assertEqual(card.kind,'enchantment')
        self.assertIsNotNone(card.transform_back_face)
        self.assertEqual(card.event_definition.saga_chapter_scale,(1,1))
        self.assertEqual(card.transform_back_face.event_definition.self_artifact_enchantment_scale,(1,1))
        sim=s.Simulator(self.rules,42,decks=(s.demo_deck(0)+[card],s.demo_deck(1)),diagnostic=True)
        sim.manual_priority=True;sim.phase='main';sim.active=0;sim.stack.priority=0
        p=sim.players[0]
        (p.hand if card in p.hand else p.library).remove(card)
        creature=next(c for c in p.hand+p.library if c.kind=='creature')
        (p.hand if creature in p.hand else p.library).remove(creature)
        sim.enter_creature(creature,p)
        host=next(x for x in p.battlefield if x.card.id==creature.id)
        return sim,card,host

    def test_named_and_new_name_faces_fail_closed_on_extra_instructions(self):
        raw=dict(self.lookup["Michiko's Reign of Truth // Portrait of Michiko"])
        raw['name']='Unseen History // Unseen Portrait'
        raw['faces']=[dict(x) for x in raw['faces']]
        raw['faces'][0]['name']='Unseen History'
        raw['faces'][1]['name']='Unseen Portrait'
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'new',{'White'}).kind,
                         'enchantment')
        raw['faces'][1]['text']+='\nDraw an extra unknown card.'
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'invalid',{'White'}).kind,
                         'unsupported')

    def test_chapters_one_and_two_look_at_dynamic_artifact_enchantment_count(self):
        sim,front,host=self.prepare();p=sim.players[0]
        base=sim.effective_card(host).power
        pending=sim.enter_creature(front,p)
        self.assertEqual(sum(e['operation']=='saga_chapter_bonus' for e in pending),1)
        saga=next(x for x in p.battlefield if x.card.id==front.id)
        self.assertEqual(saga.lore_counters,1)
        self.assertEqual(sim.effective_card(host).power,base)
        sim.resolve_entry_triggers(pending,front);self.drain(sim)
        self.assertEqual(sim.effective_card(host).power,base+1)
        sim.advance_sagas_after_draw(0);self.drain(sim)
        self.assertEqual(saga.lore_counters,2)
        self.assertEqual(sim.effective_card(host).power,base+2)
        sim.invariant()

    def test_chapter_three_exiles_and_reenters_transformed_same_physical_card(self):
        sim,front,host=self.prepare();p=sim.players[0]
        pending=sim.enter_creature(front,p)
        sim.resolve_entry_triggers(pending,front);self.drain(sim)
        sim.advance_sagas_after_draw(0);self.drain(sim)
        saga=next(x for x in p.battlefield if x.card.id==front.id)
        self.assertEqual(saga.lore_counters,2)
        sim.advance_sagas_after_draw(0)
        self.assertEqual(saga.lore_counters,3)
        self.assertTrue(any(frame.payload[0].get('operation')=='saga_transform'
                            for frame in sim.stack.items))
        self.drain(sim)
        portrait=next(x for x in p.battlefield if x.card.id==front.id)
        self.assertEqual(portrait.card.name,'Portrait of Michiko')
        self.assertEqual(sim.effective_card(portrait).power,1)
        self.assertNotIn(front,p.exile)
        sim.send_to_destination(p,portrait,to_hand=True)
        returned=next(card for card in p.hand if card.id==front.id)
        self.assertEqual(returned.name,'Michiko\'s Reign of Truth')
        self.assertIsNotNone(returned.transform_back_face)
        sim.invariant()
