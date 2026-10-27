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

    def test_real_decks_complete_requested_window_without_training(self):
        decks = [json.loads(p.read_text()) for p in sorted((HERE/"decks").glob("*.json"))]
        report = s.diagnose(self.rules, decks, 42, 10)
        self.assertEqual(report["turnsCompleted"], [10,10])
        self.assertEqual(report["result"], "diagnostic_window_complete")
        self.assertEqual(report["commanders"], ["Kolodin, Triumph Caster","Zurgo Helmsmasher"])
        self.assertFalse(report["learningEligible"])
        self.assertFalse(report["productionEligible"])
        self.assertEqual(len(report["questions"]),133)
        self.assertTrue(next(q for q in report["questions"] if q.get("card")=="Kolodin, Triumph Caster")["diagnosticSupport"])
        self.assertEqual([p["life"] for p in report["events"][-1]["state"]["players"]],[24,40])
        self.assertEqual(report["events"][-1]["state"]["players"][0]["commanderDamage"],{"1-commander":14})
        self.assertEqual(len([e for e in report["events"] if e["kind"]=="token"]),2)
        self.assertTrue(any(e["kind"]=="cast" and e["details"]["card"]=="Dragon Fodder" for e in report["events"]))
        commander_casts=[e for e in report["events"] if e["kind"]=="cast" and e["details"].get("commander")]
        self.assertEqual([len(e["details"]["manaSources"]) for e in commander_casts if e["actor"]==0],[2,4,6,8])
        self.assertEqual(len([e for e in report["events"] if e["kind"]=="attack" and e["details"].get("attacker")=="1-commander"]),6)
        zurgo=next(c for c in report["events"][-1]["state"]["players"][1]["battlefield"] if c["name"]=="Zurgo Helmsmasher")
        self.assertEqual((zurgo["power"],zurgo["toughness"],zurgo["counters"]),(11,6,4))
        self.assertEqual([p["libraryCount"] for p in report["events"][-1]["state"]["players"]],[83,82])
        self.assertTrue(any(e["kind"]=="draw_skipped" and e["actor"]==0 for e in report["events"]))
        played = [e["details"].get("card") for e in report["events"] if e["kind"] in ("land","cast")]
        self.assertIn("Command Tower", played)
        self.assertIn("Smoldering Marsh", played)

    def test_extended_real_deck_diagnostic_stops_on_commander_damage(self):
        decks=[json.loads(p.read_text()) for p in sorted((HERE/"decks").glob("*.json"))]
        report=s.diagnose(self.rules,decks,42,12)
        self.assertEqual(report["winner"],1)
        self.assertEqual(report["turnsStarted"],[11,11])
        self.assertEqual(report["events"][-1]["state"]["players"][0]["life"],13)
        self.assertEqual(report["events"][-1]["state"]["players"][0]["commanderDamage"],{"1-commander":25})
        self.assertIn("21 commander damage",report["events"][-1]["details"]["lossReasons"][0])
        self.assertFalse(report["learningEligible"])

    def test_zurgo_must_attack_and_indestructibility_depends_on_turn(self):
        deck=json.loads((HERE/"decks/5254666-garbo-gobbos.json").read_text())
        c=s.import_diagnostic_card(self.rules,deck["commanders"][0],0,"zurgo",{"White","Red","Black"})
        sim=s.Simulator(self.rules,42,decks=(s.demo_deck(0)+[c],s.demo_deck(1)),diagnostic=True)
        player=sim.players[0]
        (player.hand if c in player.hand else player.library).remove(c)
        player.battlefield.append(s.Permanent(c,fresh=False))
        sim.phase="attack"
        actions=sim.legal(0)
        self.assertEqual([(a.kind,a.card_id) for a in actions],[("attack","zurgo")])
        self.assertIn("indestructible",sim.effective_card(player.battlefield[-1]).traits)
        sim.active=1
        self.assertNotIn("indestructible",sim.effective_card(player.battlefield[-1]).traits)
        sim.invariant()

    def test_crew_activation_is_offered_and_taps_legal_helper(self):
        deck=json.loads((HERE/"decks/14850373-budget-deck.json").read_text())
        definition=next(c for c in deck["mainboard"] if c["name"]=="Thundering Chariot")
        vehicle=s.import_diagnostic_card(self.rules,definition,0,"vehicle",{"White","Red"})
        sim=s.Simulator(self.rules,42,decks=(s.demo_deck(0)+[vehicle],s.demo_deck(1)),diagnostic=True)
        player=sim.players[0]
        (player.hand if vehicle in player.hand else player.library).remove(vehicle)
        player.battlefield.append(s.Permanent(vehicle))
        helper=next(c for c in player.hand+player.library if c.kind=="creature")
        (player.hand if helper in player.hand else player.library).remove(helper)
        player.battlefield.append(s.Permanent(helper,fresh=True))
        sim.phase="main"
        action=next(a for a in sim.legal(0) if a.kind=="crew")
        game=sim.event_game("main");game.crew(action.card_id,list(action.tap_ids),0);sim.sync_events(game)
        self.assertTrue(next(x for x in player.battlefield if x.card.id==helper.id).tapped)
        self.assertTrue(next(x for x in player.battlefield if x.card.id=="vehicle").animated)
        sim.invariant()

    def test_commander_damage_can_lose_above_zero_life(self):
        sim=s.Simulator(self.rules,42)
        sim.players[0].life=40
        sim.players[0].commander_damage={"source-a":20,"source-b":20}
        sim.outcome()
        self.assertFalse(sim.finished)
        sim.players[0].commander_damage["source-a"]=21
        sim.outcome()
        self.assertEqual(sim.winner,1)
        self.assertIn("21 commander damage",sim.events[-1]["details"]["lossReasons"][0])

    def test_real_kolodin_mount_and_vehicle_events_feed_simulator(self):
        deck=json.loads((HERE/"decks/14850373-budget-deck.json").read_text())
        by_name={x["name"]:x for x in deck["commanders"]+deck["mainboard"]}
        identity=set(deck["commanders"][0]["colorIdentity"])
        extra=[s.import_diagnostic_card(self.rules,by_name[name],0,f"extra-{i}",identity)
               for i,name in enumerate(("Kolodin, Triumph Caster","Brightfield Mustang","Thundering Chariot"))]
        sim=s.Simulator(self.rules,42,decks=(s.demo_deck(0)+extra,s.demo_deck(1)),diagnostic=True)
        player=sim.players[0]
        for card in extra:
            source=player.hand if card in player.hand else player.library
            source.remove(card)
            sim.enter_creature(card,player)
        mount=next(x for x in player.battlefield if x.card.name=="Brightfield Mustang")
        vehicle=next(x for x in player.battlefield if x.card.name=="Thundering Chariot")
        self.assertTrue(mount.saddled)
        self.assertTrue(vehicle.animated)
        self.assertIn("haste",sim.effective_card(mount).traits)
        self.assertEqual(sim.effective_card(vehicle).kind,"creature")
        sim.phase="attack"
        self.assertTrue(any(x.card_id==mount.card.id for x in sim.legal(0)))
        game=sim.event_game("combat");game.attack(mount.card.id,1);sim.sync_events(game)
        self.assertEqual(mount.counters,1)
        self.assertFalse(mount.tapped)
        sim.phase="cleanup";sim.step()
        self.assertFalse(mount.saddled)
        self.assertFalse(vehicle.animated)
        self.assertEqual(mount.counters,1)
        sim.invariant()

    def test_instigator_entry_creates_real_goblin_and_tokens_cease_on_death(self):
        deck=json.loads((HERE/"decks/14850373-budget-deck.json").read_text())
        definition=next(c for c in deck["mainboard"] if c["name"]=="Goblin Instigator")
        card=s.import_diagnostic_card(self.rules,definition,0,"instigator",{"White","Red"})
        self.assertEqual(card.kind,"creature")
        sim=s.Simulator(self.rules,42,decks=(s.demo_deck(0)+[card],s.demo_deck(1)),diagnostic=True)
        player=sim.players[0]
        (player.hand if card in player.hand else player.library).remove(card)
        triggers=sim.enter_creature(card,player)
        tokens=[x for x in player.battlefield if x.card.is_token]
        self.assertEqual(len(tokens),1)
        self.assertEqual(tokens[0].card.name,"Goblin")
        self.assertEqual(tokens[0].card.event_definition.subtypes,frozenset({"Goblin"}))
        self.assertTrue(any("Goblin" in e["effect"] for e in triggers))
        sim.send_to_destination(player,tokens[0])
        self.assertFalse(any(c.is_token for c in player.graveyard))
        sim.invariant()

    def test_token_spell_with_extra_text_remains_unsupported(self):
        deck=json.loads((HERE/"decks/5254666-garbo-gobbos.json").read_text())
        definition=next(c for c in deck["mainboard"] if c["name"]=="Dragon Fodder")
        card=s.import_diagnostic_card(self.rules,definition,1,"a",{"Black","Red","White"})
        self.assertEqual((card.kind,card.token_count),("token_spell",2))
        changed=dict(definition,oracleText=definition["oracleText"]+" You lose 1 life.")
        self.assertEqual(s.import_diagnostic_card(self.rules,changed,1,"b",{"Red"}).kind,"unsupported")

    def test_diagnostic_lands_respect_color_identity_and_entry_conditions(self):
        tower={"oracleText":"{T}: Add one mana of any color in your commander's color identity."}
        self.assertEqual(s.diagnostic_land(tower,{"White","Red"})["mask"],9)
        self.assertEqual(s.diagnostic_land(tower,{"White","Red","Black"})["mask"],13)
        self.assertIsNone(s.diagnostic_land(tower,set()))
        p=s.Card("p","Plains","land",mask=1,land_subtypes=("Plains",),basic_land=True)
        m=s.Card("m","Mountain","land",mask=8,land_subtypes=("Mountain",),basic_land=True)
        dual=s.Card("dual","Dual","land",mask=9,land_rule="has_type:Plains,Swamp")
        self.assertTrue(s.land_enters_tapped(dual,[]))
        self.assertTrue(s.land_enters_tapped(dual,[m]))
        self.assertFalse(s.land_enters_tapped(dual,[p]))
        slow=s.Card("s","Slow","land",mask=9,land_rule="two_other_lands")
        self.assertTrue(s.land_enters_tapped(slow,[p]))
        self.assertFalse(s.land_enters_tapped(slow,[p,m]))
        basics=s.Card("b","Basic check","land",mask=12,land_rule="two_basics")
        self.assertTrue(s.land_enters_tapped(basics,[p,dual]))
        self.assertFalse(s.land_enters_tapped(basics,[p,m]))
        self.assertIsNone(s.diagnostic_land({"oracleText":tower["oracleText"]+" Draw a card."},{"White"}))

    def test_viewer_payload_cannot_close_script(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"test.json"
            s.export_review(path,{"schemaVersion":1,"kind":"rules-review","questions":[],
                                  "test":"</script><script>alert(1)</script>"})
            self.assertNotIn("</script><script>alert",path.with_suffix(".html").read_text())


if __name__ == "__main__":unittest.main()
