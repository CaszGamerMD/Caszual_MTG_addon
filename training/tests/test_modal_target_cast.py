"""End-to-end modal target legality, choices, resolution and deck intake."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

import simulator as s

ABRADE = ('Choose one —\n• Abrade deals 3 damage to target creature.\n'
          '• Destroy target artifact.')
RETURN = ('Choose one —\n• Destroy target artifact.\n'
          '• Destroy target enchantment.\n• Exile target card from a graveyard.')

class ModalCastTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.rules=s.RulesBridge()
    @classmethod
    def tearDownClass(cls):cls.rules.close()

    def spell(self,text,name="Unknown modal",cost="{1}{R}"):
        raw=dict(name=name,layout="normal",types=["Instant"],superTypes=[],
                 subTypes=[],manaCost=cost,oracleText=text,colors=["Red"])
        return s.import_diagnostic_card(self.rules,raw,0,"modal-spell",
                                        {"White","Blue","Black","Red","Green"})

    def fixture(self,spell):
        mana=[s.Card("modal-land-"+str(i),"Modal mana","land",mask=63)
              for i in range(5)]
        creature=s.Card("modal-creature","Opponent creature","creature",
                 power=2,toughness=2,traits="2;2;",colors=("Green",),
                 event_definition=s.EventDefinition("Opponent creature",
                     frozenset({"Creature"}),frozenset(),False,2,2,
                     frozenset(),colors=frozenset({"Green"})))
        artifact=s.Card("modal-artifact","Opponent artifact","mana_artifact",
                 event_definition=s.EventDefinition("Opponent artifact",
                     frozenset({"Artifact"}),frozenset(),False,0,0,
                     frozenset()))
        enchantment=s.Card("modal-enchant","Opponent enchantment","enchantment",
                 event_definition=s.EventDefinition("Opponent enchantment",
                     frozenset({"Enchantment"}),frozenset(),False,0,0,
                     frozenset()))
        yard=s.Card("modal-graveyard","Discarded card","spell")
        sim=s.Simulator(self.rules,42,
             decks=(s.demo_deck(0)+[spell]+mana,
                    s.demo_deck(1)+[creature,artifact,enchantment,yard]),diagnostic=True)
        sim.manual_priority=True;sim.phase="main"
        owner=sim.players[0];opp=sim.players[1]
        for card in [spell]+mana:(owner.hand if card in owner.hand else owner.library).remove(card)
        for card in (creature,artifact,enchantment,yard):
            (opp.hand if card in opp.hand else opp.library).remove(card)
        owner.hand.append(spell)
        owner.battlefield.extend(s.Permanent(card) for card in mana)
        opp.battlefield.extend(s.Permanent(card) for card in (creature,artifact,enchantment))
        opp.graveyard.append(yard)
        return sim,creature,artifact,enchantment,yard

    @staticmethod
    def resolve(sim):
        while sim.stack.items:sim.pass_priority(sim.stack.priority)

    def test_real_saved_deck_spell_text_parses(self):
        self.assertEqual(self.spell(ABRADE,"Abrade").kind,"modal_target_spell")
        self.assertEqual(self.spell(RETURN,"Return to Nature").kind,"modal_target_spell")
        self.assertEqual(self.spell(ABRADE,"Unknown damage spell").kind,"unsupported")
        self.assertEqual(self.spell(ABRADE.replace("Abrade deals","Unknown damage spell deals"),
                                    "Unknown damage spell").kind,"modal_target_spell")

    def test_abrade_damage_mode_checks_sba(self):
        spell=self.spell(ABRADE,"Abrade")
        sim,creature,artifact,_,_=self.fixture(spell)
        sim.cast_spell(0,spell,target=creature.id,modal_modes=(0,))
        self.resolve(sim)
        self.assertNotIn(creature.id,[p.card.id for p in sim.players[1].battlefield])
        self.assertIn(creature,sim.players[1].graveyard)
        self.assertIn(artifact.id,[p.card.id for p in sim.players[1].battlefield])
        sim.invariant()

    def test_abrade_destroy_mode(self):
        spell=self.spell(ABRADE,"Abrade")
        sim,creature,artifact,_,_=self.fixture(spell)
        sim.cast_spell(0,spell,target=artifact.id,modal_modes=(1,))
        self.resolve(sim)
        self.assertIn(artifact,sim.players[1].graveyard)
        self.assertIn(creature.id,[p.card.id for p in sim.players[1].battlefield])
        sim.invariant()

    def test_return_to_nature_graveyard_exile(self):
        spell=self.spell(RETURN,"Return to Nature",cost="{1}{G}")
        sim,_,artifact,enchantment,yard=self.fixture(spell)
        sim.cast_spell(0,spell,target=yard.id,modal_modes=(2,))
        self.resolve(sim)
        self.assertNotIn(yard,sim.players[1].graveyard)
        self.assertIn(yard,sim.players[1].exile)
        self.assertIn(artifact.id,[p.card.id for p in sim.players[1].battlefield])
        self.assertIn(enchantment.id,[p.card.id for p in sim.players[1].battlefield])
        sim.invariant()

    def test_return_to_nature_enchantment_and_artifact(self):
        for mode_index in (0,1):
            with self.subTest(mode=mode_index):
                spell=self.spell(RETURN,"Return to Nature",cost="{1}{G}")
                sim,_,artifact,enchantment,_=self.fixture(spell)
                victim=(artifact,enchantment)[mode_index]
                sim.cast_spell(0,spell,target=victim.id,modal_modes=(mode_index,))
                self.resolve(sim)
                self.assertIn(victim,sim.players[1].graveyard)
                sim.invariant()

    def test_mode_targets_cannot_be_swapped_before_payment(self):
        spell=self.spell(ABRADE,"Abrade")
        sim,creature,artifact,_,_=self.fixture(spell)
        for target,modes in ((artifact.id,(0,)),(creature.id,(1,)),
                             (creature.id,()),(creature.id,(0,0)),
                             (creature.id,(3,)),(creature.id,(True,))):
            with self.subTest(target=target,modes=modes):
                with self.assertRaises(ValueError):
                    sim.cast_spell(0,spell,target=target,modal_modes=modes)
                self.assertIn(spell,sim.players[0].hand)
                self.assertFalse(sim.stack.items)
                self.assertFalse(any(p.tapped for p in sim.players[0].battlefield))
        sim.invariant()

    def test_target_removed_between_cast_and_resolution_fizzles(self):
        spell=self.spell(ABRADE,"Abrade")
        sim,creature,artifact,_,_=self.fixture(spell)
        sim.cast_spell(0,spell,target=artifact.id,modal_modes=(1,))
        victim=next(p for p in sim.players[1].battlefield if p.card==artifact)
        sim.players[1].battlefield.remove(victim)
        sim.players[1].graveyard.append(artifact)
        self.resolve(sim)
        self.assertTrue(any(e["kind"]=="modal_target_fizzle" for e in sim.events))
        self.assertIn(creature.id,[p.card.id for p in sim.players[1].battlefield])
        sim.invariant()

    def test_ai_choices_bind_mode_and_target_together(self):
        spell=self.spell(ABRADE,"Abrade")
        sim,creature,artifact,_,_=self.fixture(spell)
        choices=sim.modal_target_choices(0,spell,"cast")
        pairs={(c.modal_modes,c.target_permanent) for c in choices}
        self.assertIn(((0,),creature.id),pairs)
        self.assertIn(((1,),artifact.id),pairs)
        self.assertNotIn(((0,),artifact.id),pairs)
        self.assertNotIn(((1,),creature.id),pairs)

if __name__=="__main__":
    unittest.main()
