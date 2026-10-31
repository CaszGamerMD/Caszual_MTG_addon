"""Real saved-deck library search patterns, adversarial grammar and full stack casts."""
import json
import sys
import unittest
from pathlib import Path

HERE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HERE))
import simulator as s
from library_search_spells import compile_card

def saved(deck,name):
    raw=json.loads((HERE/'decks'/deck).read_text(encoding='utf-8'))
    return next(c for c in raw['mainboard'] if c['name']==name)

TUTOR=saved('14435337-lupitas-elves.json','Worldly Tutor')
GAMBLE=saved('14509839-mono-red-gobs.json','Gamble')

class LibrarySearchCastTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.rules=s.RulesBridge()
    @classmethod
    def tearDownClass(cls):cls.rules.close()

    def spell(self,definition,name=None):
        definition=dict(definition)
        if name:definition['name']=name
        return s.import_diagnostic_card(self.rules,definition,0,'search-spell',
               {'White','Blue','Black','Red','Green'})

    def fixture(self,spell,seed=419):
        mana=[s.Card('search-mana-'+str(i),'Mana','land',mask=63) for i in range(5)]
        sim=s.Simulator(self.rules,seed,
           decks=(s.demo_deck(0)+[spell]+mana,s.demo_deck(1)),
           diagnostic=True)
        self.assertFalse(sim.finished,sim.questions)
        sim.manual_priority=True;sim.phase='main'
        player=sim.players[0]
        for item in [spell]+mana:
            (player.hand if item in player.hand else player.library).remove(item)
        player.hand.append(spell)
        player.battlefield.extend(s.Permanent(x) for x in mana)
        return sim,player

    @staticmethod
    def drain(sim):
        while sim.stack.items:sim.pass_priority(sim.stack.priority)

    def test_real_tutor_and_gamble_recognized_as_generic_whole_oracle(self):
        tutor=self.spell(TUTOR)
        gamble=self.spell(GAMBLE)
        self.assertEqual(tutor.kind,'library_search_spell')
        self.assertEqual(gamble.kind,'library_search_spell')
        self.assertEqual(tutor.library_search_program.steps,(
            'search','reveal','shuffle','put_top'))
        self.assertEqual(gamble.library_search_program.steps,(
            'search','put_hand','discard_random','shuffle'))
        self.assertEqual(self.spell(TUTOR,'Unseen Creature Finder').kind,'library_search_spell')
        self.assertEqual(self.spell(GAMBLE,'Unseen Gamble Spell').kind,'library_search_spell')

    def test_negative_samples_do_not_claim_partial_support(self):
        tests=(TUTOR['oracleText']+' Draw a card.',
               TUTOR['oracleText'].replace('creature card','any card'),
               TUTOR['oracleText'].replace('then shuffle','then draw a card, shuffle'),
               GAMBLE['oracleText'].replace('at random','of your choice'),
               GAMBLE['oracleText'].replace('then shuffle','then exile all lands'),
               'Search your library for a card, put it into your hand, then shuffle.',
               'Search your library for a creature card and put it onto the battlefield.',
               'Search your library for an artifact card, reveal it, then shuffle and put the card on top. Draw a card.')
        for oracle in tests:
            with self.subTest(oracle=oracle):
                self.assertIsNone(compile_card(oracle,['Sorcery']))
        self.assertIsNone(compile_card(TUTOR['oracleText'],['Creature']))
        self.assertIsNone(compile_card(TUTOR['oracleText'],['Artifact','Creature']))

    def test_tutor_shuffles_then_puts_exact_revealed_creature_on_top(self):
        spell=self.spell(TUTOR)
        sim,p=self.fixture(spell)
        eligible=[c for c in p.library if c.kind=='creature'
                  or 'Creature' in c.printed_types]
        chosen=min(eligible,key=lambda c:c.id)
        before=len(p.library)
        sim.cast_spell(0,spell)
        self.drain(sim)
        self.assertIs(p.library[-1],chosen)
        self.assertEqual(len(p.library),before)
        self.assertNotIn(chosen,p.hand)
        self.assertIn(spell,p.graveyard)
        self.assertTrue(any(x['kind']=='search_reveal' and
                            x['details']['card']==chosen.name for x in sim.events))
        drawn=sim.players[0].library.pop()
        sim.players[0].hand.append(drawn)
        self.assertIs(drawn,chosen)
        sim.invariant()

    def test_tutor_can_fail_to_find_matching_type_without_inventing_card(self):
        spell=self.spell(TUTOR)
        sim,p=self.fixture(spell)
        for c in list(p.library):
            if c.kind=='creature' or 'Creature' in c.printed_types:
                p.library.remove(c);p.graveyard.append(c)
        before=len(p.library)
        sim.cast_spell(0,spell);self.drain(sim)
        self.assertEqual(len(p.library),before)
        self.assertEqual(sum(x['kind']=='search_reveal' for x in sim.events),0)
        self.assertTrue(any(x['kind']=='library_shuffle' for x in sim.events))
        sim.invariant()

    def test_gamble_searches_to_hand_then_randomly_discards_and_shuffles(self):
        spell=self.spell(GAMBLE)
        sim,p=self.fixture(spell)
        candidate=min(p.library,key=lambda c:c.id)
        hand_before=len(p.hand)
        library_before=len(p.library)
        sim.cast_spell(0,spell)
        self.drain(sim)
        # The cast spell itself left the hand before the search (+1)
        # and the random discard (-1), so the net hand change is -1.
        self.assertEqual(len(p.hand),hand_before-1)
        self.assertEqual(len(p.library),library_before-1)
        discarded=[x for x in sim.events if x['kind']=='random_discard']
        self.assertEqual(len(discarded),1)
        self.assertEqual(discarded[0]['details']['card'],p.graveyard[-1].name)
        self.assertEqual(sum(x['kind']=='library_shuffle' for x in sim.events),1)
        self.assertEqual(sum(candidate in collection
                            for collection in (p.hand,p.graveyard)),1)
        sim.invariant()

    def test_gamble_seeded_random_discard_is_replay_deterministic(self):
        def result(seed):
            sim,p=self.fixture(self.spell(GAMBLE),seed=seed)
            sim.cast_spell(0,next(c for c in p.hand if c.kind=='library_search_spell'))
            self.drain(sim)
            return next(x['details']['card'] for x in sim.events
                        if x['kind']=='random_discard')
        self.assertEqual(result(419),result(419))

    def test_tutor_can_be_cast_during_priority_window_as_instant(self):
        spell=self.spell(TUTOR)
        sim,p=self.fixture(spell)
        self.assertTrue(spell.instant)
        sim.stack.priority=0
        choices=sim.response_choices(0)
        self.assertIn(spell,choices)
        sim.invariant()

if __name__=='__main__':unittest.main()
