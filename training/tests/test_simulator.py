import dataclasses
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import simulator as s


class SimulatorChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rules = s.RulesBridge()
    @classmethod
    def tearDownClass(cls):
        cls.rules.close()

    def test_shared_java_mana_and_combat(self):
        self.assertFalse(self.rules.query("pay", "{G}", "one:8")["paid"])
        self.assertTrue(self.rules.query("pay", "{G}", "one:16")["paid"])
        d = self.rules.query("combat", "3;3;double strike,trample,lifelink", "2;2;", 40, 40)
        self.assertEqual((d["damage"], d["gainA"]), (4, 6))

    def test_hidden_opponent_hand_and_library_never_enter_observation(self):
        sim = s.Simulator(self.rules, 42)
        before = sim.observe(0)
        p = sim.players[1]
        p.hand = [dataclasses.replace(c, name="SECRET ENEMY HAND", id="hidden-"+str(i))
                  for i, c in enumerate(p.hand)]
        p.library = list(reversed(p.library))
        after = sim.observe(0)
        self.assertEqual(before, after)
        self.assertNotIn("SECRET ENEMY HAND", before.public_state)

    def test_own_hand_is_visible_and_frozen(self):
        sim = s.Simulator(self.rules, 7)
        self.assertEqual(tuple(sim.players[0].hand), sim.observe(0).own_hand)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            sim.policies[0].version = 9

    def test_both_agents_decide_and_match_reproduces(self):
        a = s.Simulator(self.rules, 42)
        ra = a.run()
        rb = s.Simulator(self.rules, 42).run()
        self.assertEqual(ra, rb)
        self.assertEqual({d["seat"] for d in a.decisions}, {0, 1})
        self.assertEqual(ra["result"], "win")
        self.assertTrue(ra["learningEligible"])
        self.assertFalse(ra["productionEligible"])
        a.invariant()
        count = len(a.events)
        self.assertFalse(a.step())
        self.assertEqual(count, len(a.events))

    def test_attacker_chooses_lethal_and_defender_tries_to_survive(self):
        sim = s.Simulator(self.rules,42)
        p = sim.players[0]
        a = next(c for c in p.hand+p.library if c.kind=="creature")
        # Build a deterministic public decision without changing the card inventory.
        source = p.hand if a in p.hand else p.library
        source.remove(a);p.battlefield.append(s.Permanent(a,False,False))
        sim.players[1].life=1
        sim.phase="attack"
        self.assertEqual(sim.decide(0).kind,"attack")
        sim.pending=a.id
        defender=sim.players[1]
        b=next(c for c in defender.hand+defender.library if c.kind=="creature")
        source=defender.hand if b in defender.hand else defender.library
        source.remove(b);defender.battlefield.append(s.Permanent(b,False,False))
        sim.phase="block"
        choice=sim.decide(1)
        self.assertEqual(choice.kind,"block")
        self.assertNotEqual(choice.card_id,"")

    def test_draw_logs_keep_card_names_private(self):
        replay = s.Simulator(self.rules, 42).run()
        for event in replay["events"]:
            if event["kind"] == "draw":
                self.assertNotIn("card", event["details"])
                self.assertNotIn("Training creature", event["message"])
                for p in event["state"]["players"]:
                    self.assertNotIn("hand", p)
                    self.assertNotIn("library", p)

    def test_starting_seats_and_fresh_shuffles(self):
        a = s.Simulator(self.rules, 42, starter=0)
        b = s.Simulator(self.rules, 42, starter=1)
        a.step();b.step()
        self.assertEqual((a.active,b.active), (0,1))
        c = s.Simulator(self.rules, 43)
        self.assertNotEqual(a.players[0].hand, c.players[0].hand)

    def test_timeout_not_training_or_win(self):
        report = s.Simulator(self.rules, 42, max_turns=1).run()
        self.assertEqual(report["result"], "timeout")
        self.assertFalse(report["learningEligible"])
        self.assertEqual(s.match_score(report, 0), (0,0))

    def test_unknown_stage_asks_instead_of_guessing(self):
        sim = s.Simulator(self.rules, 42)
        sim.phase = "unsupported priority choice"
        replay = sim.run()
        self.assertEqual(replay["result"], "blocked")
        self.assertTrue(replay["questions"][0]["blocking"])
        self.assertFalse(replay["learningEligible"])

    def test_unknown_card_blocks_before_any_draw(self):
        a = s.demo_deck(0)
        a[0] = s.Card("unsupported", "Unknown ability card", "planeswalker")
        sim = s.Simulator(self.rules, 42, decks=(a,s.demo_deck(1)))
        report = sim.run()
        self.assertEqual(report["result"], "blocked")
        self.assertEqual(report["questions"][0]["card"], "Unknown ability card")
        self.assertFalse(any(e["kind"] == "draw" for e in report["events"]))

    def test_missing_creature_rule_blocks(self):
        a = s.demo_deck(0)
        a[14] = dataclasses.replace(a[14], traits="2;2;menace")
        report = s.Simulator(self.rules, 42, decks=(a,s.demo_deck(1))).run()
        self.assertEqual(report["result"], "blocked")

    def test_empty_library_does_not_lose_until_required_draw(self):
        sim = s.Simulator(self.rules, 42)
        p = sim.players[0]
        p.graveyard.extend(p.library);p.library.clear()
        sim.outcome()
        self.assertFalse(sim.finished)
        sim.draw(0);sim.outcome()
        self.assertEqual(sim.winner, 1)

    def test_speed_is_secondary_to_wins_and_losses_get_no_speed_reward(self):
        report = {"learningEligible":True, "winner":0, "turns":2}
        self.assertEqual(s.match_score(report,1),(0,0))
        slow = dict(report,turns=90)
        self.assertGreater(s.match_score(slow,0),s.match_score(report,1))
        self.assertGreater(s.match_score(report,0),s.match_score(slow,0))

    def test_actual_decks_flag_rules_and_cannot_train(self):
        decks = [json.loads(p.read_text()) for p in sorted((HERE/"decks").glob("*.json"))]
        report = s.audit_decks(self.rules,decks)
        self.assertEqual(report["status"], "blocked")
        self.assertFalse(report["learningEligible"])
        self.assertEqual([d["mainCount"] for d in report["decks"]],[99,99])
        names = {q["card"] for q in report["questions"]}
        self.assertIn("Kolodin, Triumph Caster",names)
        self.assertIn("Zurgo Helmsmasher",names)
        self.assertTrue(all(q["blocking"] and q["status"]=="open" for q in report["questions"]))
        self.assertEqual(len({q["id"] for q in report["questions"]}),len(report["questions"]))

    def test_dual_faces_and_extra_clauses_never_ignored(self):
        c = {"name":"Test","types":["Creature"],"superTypes":[],"subTypes":[],
             "manaCost":"{G}","power":"1","toughness":"1","oracleText":"Haste\nWhen this enters, draw a card."}
        self.assertEqual(s.audit_card(self.rules,c)["kind"],"unsupported")
        c["oracleText"]="Haste";c["layout"]="transform"
        self.assertEqual(s.audit_card(self.rules,c)["kind"],"unsupported")

    def test_answer_notes_do_not_enable_rules(self):
        decks = [json.loads(next((HERE/"decks").glob("*.json")).read_text())]
        report = s.audit_decks(self.rules,decks)
        for q in report["questions"]: q["answer"]="Ignore the ability."
        again = s.audit_decks(self.rules,decks)
        self.assertEqual(again["status"],"blocked")
        self.assertEqual(len(report["questions"]),len(again["questions"]))

    def test_policy_checkpoint_roundtrip_and_invalid_weights(self):
        p = s.Policy(5)
        self.assertEqual(s.Policy.from_json(p.to_json()),p)
        raw = p.to_json();raw["weights"]["power"]=float("nan")
        with self.assertRaises(ValueError):s.Policy.from_json(raw)

    def test_resume_keeps_progress_and_candidate_cannot_replace_better_champion(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            with patch.object(s,"evaluate",return_value={"candidate":[0,0],"champion":[2,-10],
                              "completed":4,"expected":4,"promote":False}):
                r = s.train(self.rules,out,1,42,2)
                self.assertEqual(r["championVersion"],0)
                self.assertEqual(json.loads((out/"champion.json").read_text())["version"],0)
                r = s.train(self.rules,out,1,42,2)
                self.assertEqual([row["generation"] for row in r["history"]],[0,1])
                self.assertNotEqual(r["history"][0]["evaluationSeeds"],r["history"][1]["evaluationSeeds"])
                self.assertTrue(all(n>0 for n in r["history"][0]["pooledDecisions"]))

    def test_authoritative_checkpoint_recovers_interrupted_exports(self):
        with tempfile.TemporaryDirectory() as directory:
            out=Path(directory)
            with patch.object(s,"evaluate",return_value={"candidate":[2,-20],"champion":[0,0],
                              "completed":4,"expected":4,"promote":True}):
                r=s.train(self.rules,out,1,42,2)
            self.assertEqual(r["championVersion"],1)
            s.write_json(out/"champion.json",s.Policy().to_json())
            s.write_json(out/"history.json",[])
            with patch.object(s,"evaluate",return_value={"candidate":[0,0],"champion":[2,-20],
                              "completed":4,"expected":4,"promote":False}):
                r=s.train(self.rules,out,1,42,2)
            self.assertEqual(r["championVersion"],1)
            self.assertEqual(len(r["history"]),2)
            with self.assertRaises(ValueError):s.train(self.rules,out,1,999,2)

    def test_viewer_payload_cannot_close_script(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"test.json"
            s.export_review(path,{"schemaVersion":1,"kind":"rules-review","questions":[],
                                  "test":"</script><script>alert(1)</script>"})
            self.assertNotIn("</script><script>alert",path.with_suffix(".html").read_text())


if __name__ == "__main__":unittest.main()
