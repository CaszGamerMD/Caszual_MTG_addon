"""Opening hand evaluator and pregame setup regressions."""
import sys,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HERE))
import simulator as s
import opening_hand as h

def land(n,mask=16,**kw):return s.Card(n,n,"land",mask=mask,**kw)
def creature(n,cost):return s.Card(n,n,"creature",cost,"2;2;",2,2)

class OpeningHandTests(unittest.TestCase):
    def test_good_curve_and_bad_three_drop_pair(self):
        lands=[land("L1"),land("L2"),land("L3")]
        self.assertTrue(h.assess(lands+[creature("A","{G}"),creature("B","{1}{G}"),
                creature("C","{7}"),creature("D","{8}")])["keep"])
        poor=lands+[creature("A","{2}{G}"),creature("B","{2}{G}"),
                    creature("C","{7}"),creature("D","{8}")]
        self.assertFalse(h.assess(poor)["keep"])
        self.assertEqual(h.assess(poor)["castable"],2)

    def test_color_tapped_and_target_dependent_limits(self):
        red=[land("R1",8),land("R2",8),land("R3",8)]
        self.assertFalse(h.assess(red+[creature("A","{G}"),creature("B","{U}"),
                creature("C","{7}"),creature("D","{8}")])["keep"])
        tapped=[land("T1",16,enters_tapped=True),land("T2",16,enters_tapped=True),
                land("T3",16,enters_tapped=True)]
        self.assertFalse(h.assess(tapped+[creature("A","{2}{G}"),
                creature("B","{1}{G}"),creature("C","{7}"),creature("D","{8}")])["keep"])
        self.assertFalse(h.assess([land("L1"),land("L2"),land("L3"),
                s.Card("a","Aura","aura","{G}"),
                s.Card("r","Removal","removal_spell","{G}"),
                creature("One","{G}"),creature("Huge","{8}")])["keep"])

    def test_soft_keep_requires_a_workable_not_perfect_hand(self):
        good=[land("L1"),land("L2"),creature("Cheap","{G}"),
              creature("Huge","{7}"),creature("Tall","{8}"),
              creature("More","{9}"),creature("Another","{7}")]
        self.assertFalse(h.assess(good)["keep"])
        self.assertTrue(h.fallback(good))
        self.assertFalse(h.fallback([land("L1")]+good[2:]))

    def test_modal_land_back_counts_as_land_without_spending_its_front(self):
        modal=s.Card('m','Blessing','aura','{G}',
                     modal_land_face=land('m',mask=16,enters_tapped=True))
        hand=[land('L1'),land('L2'),modal,creature('A','{G}'),
              creature('B','{1}{G}'),creature('C','{8}'),creature('D','{9}')]
        report=h.assess(hand)
        self.assertTrue(report['keep'])
        self.assertEqual(report['lands'],3)
        self.assertEqual(report['early'],2)
        self.assertTrue(h.fallback(hand))

    def test_modal_front_and_back_cannot_both_count_for_one_opening(self):
        modal=s.Card('m','Adaptable','creature','{G}','2;2;',2,2,
                     modal_land_face=land('m',mask=16))
        # Exactly one other early spell: using modal as the third land leaves
        # only one castable spell; using modal as a spell leaves two lands.
        hand=[land('L1'),land('L2'),modal,creature('A','{G}'),
              creature('C','{8}'),creature('D','{9}'),creature('E','{7}')]
        self.assertFalse(h.assess(hand)['keep'])
        self.assertTrue(h.fallback(hand))

    def test_batch_seven_and_reproducible_free_mulligans(self):
        class Rules:
            def query(self,*args):return {"kind":"creature"}
        a=s.Simulator(Rules(),42);b=s.Simulator(Rules(),42)
        self.assertEqual(a.events,b.events)
        for player in a.players:
            self.assertEqual(len(player.hand),7)
            self.assertEqual(len(player.library),21)
        self.assertTrue(all(e["details"]["count"]==7 for e in a.events if e["kind"]=="opening_hand"))
        self.assertFalse(any(e["kind"]=="draw" for e in a.events))
        self.assertTrue(all(n<=h.FRIENDLY_MULLIGAN_LIMIT for n in a.opening_mulligans))
        self.assertEqual(a.report()["openingMulligans"],a.opening_mulligans)
        a.invariant()

    def test_main_phase_policy_prefers_doing_something(self):
        passing=s.Candidate("pass","pass",features=s.features(**{"pass":1}))
        casting=s.Candidate("cast","cast",features=s.features(cost=3))
        self.assertEqual(s.Policy().choose(s.Observation(0,1,"main",(),"{}",
            (passing,casting))).kind,"cast")
        self.assertEqual(s.Policy().choose(s.Observation(0,1,"main",(),"{}",
            (passing,))).kind,"pass")

if __name__=="__main__":unittest.main()
