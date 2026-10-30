"""Modal spell-front / land-back cards share one physical identity and legal zone behavior."""
import sys
import unittest
from unittest.mock import patch
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
import test_enchantment_abilities as fixtures


class ModalFaceChecks(unittest.TestCase):
    setUpClass=classmethod(fixtures.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.EnchantmentChecks.tearDownClass.__func__)
    token=fixtures.EnchantmentChecks.token
    drain=fixtures.EnchantmentChecks.drain

    def actual(self):
        return dict(self.lookup['Strength of the Harvest // Haven of the Harvest'])

    def test_actual_and_unseen_aura_land_faces_compile_strictly(self):
        raw=self.actual()
        card=s.import_diagnostic_card(self.rules,raw,0,'modal',{'White','Green'})
        self.assertEqual(card.kind,'aura')
        self.assertEqual(card.name,'Strength of the Harvest')
        self.assertIsNotNone(card.modal_land_face)
        self.assertEqual(card.modal_land_face.name,'Haven of the Harvest')
        self.assertEqual(card.event_definition.attachment_scale,(1,1,('Creature','Enchantment')))
        self.assertTrue(card.modal_land_face.enters_tapped)
        self.assertEqual(card.modal_land_face.mask,17)
        other=dict(raw,name='Unseen Forest Blessing // Secret Refuge',
                   faces=[dict(x) for x in raw['faces']])
        other['faces'][0]['name']='Unseen Forest Blessing'
        other['faces'][1]['name']='Secret Refuge'
        other['faces'][1]['text']='This land enters tapped.\n{T}: Add {W} or {U}.'
        parsed=s.import_diagnostic_card(self.rules,other,0,'new',{'White','Blue','Green'})
        self.assertEqual(parsed.kind,'aura')
        self.assertEqual(parsed.modal_land_face.mask,3)
        other['faces'][1]['text']+='\nWhen this land leaves, win the game.'
        self.assertEqual(s.import_diagnostic_card(self.rules,other,0,'bad',{'White'}).kind,'unsupported')
        other['faces'][1]['text']='This land enters tapped.\n{T}: Add {W} or {U}.'
        other['faces'][0]['text']+='\nCreate an unknown mystery.'
        self.assertEqual(s.import_diagnostic_card(self.rules,other,0,'bad2',{'White'}).kind,'unsupported')
        # Other multi-face mechanisms cannot be silently treated as a normal front card.
        # Fully compiled transforming Sagas now preserve both face programs.
        transform=s.import_diagnostic_card(self.rules,self.lookup["Michiko's Reign of Truth // Portrait of Michiko"],0,'transform',{'White'})
        self.assertEqual(transform.kind,'enchantment')
        self.assertEqual(transform.transform_back_face.kind,'creature')
        # A castable spell back is now supported; the physical front and back
        # must be distinct programs rather than a silently ignored second face.
        dual=dict(self.lookup["Halvar, God of Battle // Sword of the Realms"])
        halvar=s.import_diagnostic_card(self.rules,dual,0,'spellback',{'White'})
        self.assertEqual(halvar.kind,'creature')
        self.assertIsNotNone(halvar.modal_spell_face)
        self.assertEqual(halvar.modal_spell_face.name,'Sword of the Realms')
        unseen=dict(dual,name='Unseen Battle God // Unseen Blade',
                    faces=[dict(face) for face in dual['faces']])
        unseen['faces'][0]['name']='Unseen Battle God'
        unseen['faces'][1]['name']='Unseen Blade'
        self.assertEqual(s.import_diagnostic_card(self.rules,unseen,0,'unseen-spellback',{'White'}).kind,'creature')
        unseen['faces'][1]['text']+='\\nWhen this enters, win the game.'
        self.assertEqual(s.import_diagnostic_card(self.rules,unseen,0,'invalid-spellback',{'White'}).kind,'unsupported')

    def test_spell_back_casts_as_equipment_then_returns_to_front_face(self):
        raw=self.lookup["Halvar, God of Battle // Sword of the Realms"]
        front=s.import_diagnostic_card(self.rules,raw,0,'dual-spell',{'White'})
        self.assertEqual(front.kind,'creature')
        self.assertIsNotNone(front.modal_spell_face)
        sim=s.Simulator(self.rules,42,decks=(s.demo_deck(0)+[front],s.demo_deck(1)),
                        diagnostic=True)
        sim.manual_priority=True
        player=sim.players[0]
        (player.hand if front in player.hand else player.library).remove(front)
        player.hand.append(front)
        sim.phase='main';sim.active=0;sim.stack.priority=0
        player.mana_pool[0]=5
        choices=[action for action in sim.legal(0)
                 if action.kind=='cast_modal_back' and action.card_id==front.id]
        self.assertEqual(len(choices),1)
        with patch.object(sim,'decide',return_value=choices[0]):
            sim.step()
        self.drain(sim)
        equipment=next(permanent for permanent in player.battlefield
                       if permanent.card.id==front.id)
        self.assertEqual(equipment.card.name,'Sword of the Realms')
        self.assertEqual(equipment.card.kind,'equipment')
        self.assertFalse(any(card.id==front.id for card in player.hand))
        sim.send_to_destination(player,equipment,to_hand=True)
        returned=next(card for card in player.hand if card.id==front.id)
        self.assertEqual(returned.name,'Halvar, God of Battle')
        self.assertIsNotNone(returned.modal_spell_face)
        sim.invariant()

    def test_real_wilds_vs_garbo_diagnostic_accepts_physical_front_face_identity(self):
        import json
        decks=[json.loads((s.HERE/'decks'/name).read_text(encoding='utf-8'))
               for name in ('5189995-enchantments.json','5254666-garbo-gobbos.json')]
        report=s.diagnose(self.rules,decks,seed=71,turns_per_player=1)
        self.assertEqual(report['deckIds'],[5189995,5254666])
        self.assertFalse(report['learningEligible'])
        self.assertTrue(report['events'])
        self.assertEqual(report['rulesProgress']['cardsPlayableInDiagnostic'],[100,100])

    def pathway(self, name='Needleverge Pathway // Pillarverge Pathway'):
        return dict(self.lookup[name],faces=[dict(face) for face in self.lookup[name]['faces']])

    def test_three_saved_pathways_and_unseen_two_land_faces_are_whole_oracle(self):
        examples=(('Needleverge Pathway // Pillarverge Pathway',8,1),
                  ('Clearwater Pathway // Murkwater Pathway',2,4),
                  ('Darkbore Pathway // Slitherbore Pathway',4,16))
        for name,front_mask,back_mask in examples:
            with self.subTest(name=name):
                raw=self.pathway(name)
                card=s.import_diagnostic_card(self.rules,raw,0,'pathway',set())
                self.assertEqual(card.kind,'land')
                self.assertEqual(card.mask,front_mask)
                self.assertEqual(card.modal_land_face.kind,'land')
                self.assertEqual(card.modal_land_face.mask,back_mask)
                self.assertEqual(card.modal_land_face.name,raw['faces'][1]['name'])
                self.assertFalse(card.enters_tapped)
                self.assertFalse(card.modal_land_face.enters_tapped)
        raw=self.pathway()
        raw['name']='Unseen Mountain Trail // Unseen Ocean Trail'
        raw['faces'][0]['name']='Unseen Mountain Trail'
        raw['faces'][1]['name']='Unseen Ocean Trail'
        raw['faces'][0]['text']='{T}: Add {G}.'
        raw['faces'][1]['text']='{T}: Add {U}.'
        unseen=s.import_diagnostic_card(self.rules,raw,0,'unseen-pathway',{'Green','Blue'})
        self.assertEqual((unseen.mask,unseen.modal_land_face.mask),(16,2))
        raw['faces'][1]['text']+='\\nWhenever this land taps, win the game.'
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'bad-back',set()).kind,'unsupported')
        raw['faces'][1]['text']='{T}: Add {U}.'
        raw['faces'][0]['text']+='\\nCreate a mysterious counter.'
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'bad-front',set()).kind,'unsupported')

    def test_pathway_front_or_back_uses_one_land_play_and_reverts_in_zones(self):
        raw=self.pathway()
        for chosen,expected,mask in (('land','Needleverge Pathway',8),
                                     ('land_back','Pillarverge Pathway',1)):
            with self.subTest(chosen=chosen):
                front=s.import_diagnostic_card(self.rules,raw,0,'pathway',{'White','Red'})
                sim=s.Simulator(self.rules,42,
                    decks=(s.demo_deck(0)+[front],s.demo_deck(1)),diagnostic=True)
                sim.manual_priority=True
                player=sim.players[0]
                (player.hand if front in player.hand else player.library).remove(front)
                player.hand.append(front)
                sim.phase='land';sim.active=0;sim.stack.priority=0
                actions=[action for action in sim.legal(0)
                         if action.card_id==front.id and action.kind in ('land','land_back')]
                self.assertEqual({a.kind for a in actions},{'land','land_back'})
                with patch.object(sim,'decide',return_value=next(a for a in actions if a.kind==chosen)):
                    sim.step()
                permanent=next(p for p in player.battlefield if p.card.id==front.id)
                self.assertEqual(permanent.card.name,expected)
                self.assertEqual(permanent.card.mask,mask)
                self.assertFalse(permanent.tapped)
                self.assertEqual(sim.land_plays_this_turn,1)
                self.assertEqual([a for a in sim.legal(0) if a.kind in ('land','land_back')],[])
                self.assertIn(front.id,[source for source,_ in sim.mana_sources(0)])
                self.assertEqual(next(options for source,options in sim.mana_sources(0)
                                      if source==front.id),
                                 (tuple(int(i==('WUBRGC'.index('R' if mask==8 else 'W')))
                                        for i in range(6)),))
                self.assertFalse(any(e['kind']=='cast' and e['details'].get('card')==expected
                                     for e in sim.events))
                sim.send_to_destination(player,permanent,to_hand=True)
                returned=next(c for c in player.hand if c.id==front.id)
                self.assertEqual(returned.name,'Needleverge Pathway')
                self.assertIsNotNone(returned.modal_land_face)
                sim.invariant()

    def prepare(self):
        card=s.import_diagnostic_card(self.rules,self.actual(),0,'modal',{'White','Green'})
        sim=s.Simulator(self.rules,42,decks=(s.demo_deck(0)+[card],s.demo_deck(1)),diagnostic=True)
        sim.manual_priority=True
        p=sim.players[0]
        (p.hand if card in p.hand else p.library).remove(card)
        p.hand.append(card)
        mana=[c for c in p.hand+p.library if c.kind=='land'][:5]
        for land in mana:
            (p.hand if land in p.hand else p.library).remove(land)
            p.battlefield.append(s.Permanent(land,tapped=False,fresh=False))
        sim.phase='land';sim.active=0;sim.stack.priority=0
        return sim,card

    def test_land_back_plays_tapped_without_cast_then_returns_front_to_hand(self):
        sim,front=self.prepare()
        candidates=[c for c in sim.legal(0) if c.kind=='land_back' and c.card_id==front.id]
        self.assertEqual(len(candidates),1)
        with patch.object(sim,'decide',return_value=candidates[0]):
            sim.step()
        back=next(p for p in sim.players[0].battlefield if p.card.id==front.id)
        self.assertEqual(back.card.name,'Haven of the Harvest')
        self.assertTrue(back.tapped)
        self.assertEqual(sim.land_plays_this_turn,1)
        self.assertFalse(any(e['kind']=='cast' and e['details'].get('card')==back.card.name for e in sim.events))
        sim.send_to_destination(sim.players[0],back,to_hand=True)
        returned=next(c for c in sim.players[0].hand if c.id==front.id)
        self.assertEqual(returned.name,front.name)
        self.assertIsNotNone(returned.modal_land_face)
        self.assertEqual(returned.kind,'aura')
        sim.invariant()

    def test_land_back_can_be_cast_as_front_after_return_and_counts_dynamically(self):
        sim,front=self.prepare()
        with patch.object(sim,'decide',return_value=next(
                c for c in sim.legal(0) if c.kind=='land_back' and c.card_id==front.id)):
            sim.step()
        back=next(p for p in sim.players[0].battlefield if p.card.id==front.id)
        sim.send_to_destination(sim.players[0],back,to_hand=True)
        host=self.token(sim,'host')
        sim.phase='main';sim.stack.priority=0
        sim.cast_spell(0,front,target=host.card.id)
        self.drain(sim)
        aura=next(p for p in sim.players[0].battlefield if p.card.id==front.id)
        self.assertEqual(aura.card.name,front.name)
        self.assertEqual(aura.attached_to,host.card.id)
        self.assertEqual(sim.effective_card(host).power,4)
        sim.send_to_destination(sim.players[0],aura)
        self.assertIn(front,sim.players[0].graveyard)
        sim.invariant()
