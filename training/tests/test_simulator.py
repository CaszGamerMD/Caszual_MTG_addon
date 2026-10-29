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
    def test_token_spell_finishes_before_lethal_impact_tremors_trigger(self):
        deck=json.loads((HERE/"decks/5254666-garbo-gobbos.json").read_text())
        lookup={c["name"]:c for c in deck["mainboard"]}
        tremors,spell=[s.import_diagnostic_card(self.rules,lookup[name],0,"actual-"+str(i),{"Red"})
                       for i,name in enumerate(("Impact Tremors","Dragon Fodder"))]
        lands=[s.Card("red-land-"+str(i),"Mountain","land",mask=8) for i in range(2)]
        sim=s.Simulator(self.rules,42,decks=(s.demo_deck(0)+[tremors,spell]+lands,s.demo_deck(1)),diagnostic=True)
        player=sim.players[0]
        for card in [tremors,spell]+lands:
            (player.hand if card in player.hand else player.library).remove(card)
            if card==spell: player.hand.append(card)
            elif card==tremors: sim.enter_creature(card,player)
            else: player.battlefield.append(s.Permanent(card))
        sim.phase="main"; sim.players[1].life=1
        with patch.object(sim,"decide",return_value=s.Candidate("cast","cast",card_id=spell.id)):
            sim.step()
        self.assertEqual(sum(p.card.is_token for p in player.battlefield),2)
        self.assertEqual(sim.result,"win")
        token_events=[e["index"] for e in sim.events if e["kind"]=="token"]
        damage_events=[e["index"] for e in sim.events if "Impact Tremors deals" in e["message"]]
        self.assertEqual(len(damage_events),1)  # Opponent loses before the next trigger can resolve.
        self.assertLess(max(token_events),min(damage_events))
        self.assertEqual(sim.players[1].commander_damage,{})
        sim.invariant()

    def death_fixture(self, attack_traits="1;1;", defenders=("Nested Shambler",), allies=()):
        deck=json.loads((HERE/"decks/8321184-squirrels.json").read_text())
        lookup={c["name"]:c for c in deck["mainboard"]}
        power,toughness,_=attack_traits.split(";")
        attacker=s.Card("scenario-attacker","Scenario attacker","creature",mana_cost="{G}",traits=attack_traits,
                        power=int(power),toughness=int(toughness))
        actual=[[s.import_diagnostic_card(self.rules,lookup[name],seat,f"scenario-{seat}-{i}",{"Green","Black"})
                 for i,name in enumerate(names)] for seat,names in enumerate((allies,defenders))]
        actual[0].insert(0,attacker)
        sim=s.Simulator(self.rules,42,decks=tuple(s.demo_deck(i)+actual[i] for i in (0,1)),diagnostic=True)
        for player,cards in zip(sim.players,actual):
            for card in cards:
                (player.hand if card in player.hand else player.library).remove(card)
                sim.enter_creature(card,player)
                next(p for p in player.battlefield if p.card.id==card.id).fresh=False
        sim.phase="block"; sim.pending=attacker.id
        return sim,actual

    def resolve_fixture_combat(self,sim,actual):
        with patch.object(sim,"decide",return_value=s.Candidate("block","block",card_id=actual[1][0].id)):
            sim.step()
        sim.invariant()

    def test_simultaneous_combat_deaths_trigger_artist_and_cutthroat(self):
        sim,actual=self.death_fixture(defenders=("Zulaport Cutthroat",),allies=("Blood Artist",))
        self.resolve_fixture_combat(sim,actual)
        triggers=[e for e in sim.events if e["kind"]=="trigger" and e["details"].get("dead")]
        self.assertEqual([e["details"]["name"] for e in triggers],["Zulaport Cutthroat","Blood Artist","Blood Artist"])
        self.assertEqual([p.life for p in sim.players],[41,39])
        self.assertFalse(sim.report()["learningEligible"])

    def generic_death_fixture(self, text):
        sim,actual=self.death_fixture()
        raw=dict(name="Unfamiliar death source",types=["Creature"],power="1",toughness="1",
                 manaCost="{G}",oracleText=text)
        card=s.import_diagnostic_card(self.rules,raw,1,actual[1][0].id,{"Green"})
        self.assertEqual(card.kind,"creature")
        sim.players[1].battlefield[0].card=card
        actual[1][0]=card
        return sim,actual

    def test_generic_death_tokens_resolve_after_source_leaves(self):
        sim,actual=self.generic_death_fixture(
            "When this creature dies, create two tapped 2/3 blue Drake creature tokens with flying.")
        self.resolve_fixture_combat(sim,actual)
        tokens=[p for p in sim.players[1].battlefield if p.card.is_token]
        self.assertEqual(len(tokens),2)
        self.assertTrue(all(p.tapped and p.fresh and p.card.traits=="2;3;flying" for p in tokens))
        self.assertIn(actual[1][0],sim.players[1].graveyard)
        self.assertFalse(sim.players[0].battlefield)
        combat=next(e["index"] for e in sim.events if e["kind"]=="combat")
        created=[e["index"] for e in sim.events if e["kind"]=="trigger" and e["details"].get("operation")=="create_tokens"]
        self.assertEqual(len(created),1)
        self.assertGreater(created[0],combat)

    def test_death_token_batch_finishes_before_lethal_entry_trigger(self):
        sim,actual=self.generic_death_fixture(
            "When this creature dies, create two 1/1 red Goblin creature tokens.")
        raw=dict(name="Unfamiliar entry watcher",types=["Enchantment"],manaCost="{R}",
                 oracleText="Whenever a creature you control enters, this enchantment deals 1 damage to each opponent.")
        watcher=s.import_diagnostic_card(self.rules,raw,1,"death-watcher",{"Red"})
        # Replace an existing library card to preserve the fixture's card count.
        sim.players[1].library.pop()
        sim.enter_creature(watcher,sim.players[1])
        sim.players[0].life=1
        self.resolve_fixture_combat(sim,actual)
        self.assertEqual(sim.winner,1)
        self.assertEqual(sum(p.card.is_token for p in sim.players[1].battlefield),2)
        effects=[e for e in sim.events if e["kind"]=="trigger" and e["details"].get("operation")=="damage"]
        self.assertEqual(len(effects),1)
        batch=next(e for e in sim.events if e["kind"]=="trigger" and e["details"].get("operation")=="create_tokens")
        self.assertLess(batch["index"],effects[0]["index"])

    def test_generic_death_scry_keeps_controller_library_private(self):
        sim,actual=self.generic_death_fixture("When this creature dies, scry 3.")
        before=[list(p.library) for p in sim.players]
        self.resolve_fixture_combat(sim,actual)
        self.assertEqual([p.library for p in sim.players],before)
        events=[e for e in sim.events if e["details"].get("operation")=="scry"]
        self.assertEqual(len(events),1)
        self.assertIn("Player 2 scries 3",events[0]["message"])
        self.assertFalse(any(c.id in json.dumps(events) for c in before[1]))

    def test_generic_death_counters_only_affect_surviving_controller_creatures(self):
        sim,actual=self.generic_death_fixture("When this creature dies, put 2 +1/+1 counters on each creature you control.")
        for seat in (0,1):
            card=next(c for c in sim.players[seat].library+sim.players[seat].hand if c.kind=="creature")
            p=sim.players[seat]
            (p.hand if card in p.hand else p.library).remove(card)
            sim.enter_creature(card,p)
        self.resolve_fixture_combat(sim,actual)
        self.assertEqual([p.counters for p in sim.players[0].battlefield],[0])
        self.assertEqual([p.counters for p in sim.players[1].battlefield],[2])

    def test_nested_shambler_uses_last_power_and_defender_controls_tapped_tokens(self):
        sim,actual=self.death_fixture("3;3;")
        sim.players[1].battlefield[0].counters=2
        self.resolve_fixture_combat(sim,actual)
        tokens=[p for p in sim.players[1].battlefield if p.card.is_token]
        self.assertEqual(len(tokens),3)
        self.assertTrue(all(p.tapped and p.fresh for p in tokens))
        self.assertTrue(all(p.definition.subtypes==frozenset({"Squirrel"}) and p.controller==1
                            for p in sim.event_game("combat").battlefield.values()))
        self.assertEqual(sim.players[0].battlefield,[])
        self.assertEqual(sim.players[1].graveyard[-1].name,"Nested Shambler")

    def test_combat_loss_is_checked_before_death_lifegain(self):
        sim,actual=self.death_fixture("2;2;trample",defenders=("Zulaport Cutthroat",))
        sim.players[1].life=1
        self.resolve_fixture_combat(sim,actual)
        self.assertEqual(sim.result,"win")
        self.assertEqual(sim.winner,0)
        self.assertEqual(sim.players[1].life,0)
        self.assertFalse(any(e["kind"]=="trigger" and e["details"].get("dead") for e in sim.events))

    def test_first_strike_death_timing_uses_separate_steps(self):
        sim,actual=self.death_fixture('1;1;first strike')
        self.resolve_fixture_combat(sim,actual)
        self.assertEqual(sim.phase,'first_damage')
        sim.step()
        self.assertEqual(sim.phase,'regular_damage')
        self.assertIn(actual[1][0],sim.players[1].graveyard)
        self.assertTrue(any(p.card.is_token for p in sim.players[1].battlefield))
        sim.step()
        self.assertEqual(sim.phase,'second_main')
        self.assertFalse(sim.questions)
        sim.invariant()

    def test_real_deck_report_keeps_runtime_questions(self):
        decks=[json.loads((HERE/"decks"/name).read_text()) for name in
               ("27521806-faeries.json","8321184-squirrels.json")]
        def blocked_run(sim):
            sim.pause("Scenario requires a response window")
            return sim.report()
        with patch.object(s.Simulator,"run",blocked_run):
            report=s.diagnose(self.rules,decks,42,10)
        self.assertEqual(report["result"],"blocked")
        self.assertTrue(any(q["reason"]=="Scenario requires a response window" for q in report["questions"]))
        self.assertTrue(any(q.get("card")=="Chatterfang, Squirrel General" for q in report["questions"]))
        self.assertEqual(report["rulesProgress"]["runtimeQuestions"],["Scenario requires a response window"])
        self.assertIn("Chatterfang, Squirrel General",report["rulesProgress"]["unsupportedCommanders"])
        artist=next(q for q in report["questions"] if q.get("card")=="Blood Artist")
        self.assertTrue(artist["diagnosticSupport"])
        self.assertIn("Simultaneous deaths",artist["ruleAnswer"])
        self.assertTrue(artist["blocking"])

    def test_real_squirrel_continuous_effects_reach_combat_stats(self):
        deck=json.loads((HERE/"decks/8321184-squirrels.json").read_text())
        lookup={c["name"]:c for c in deck["mainboard"]}
        cards=[s.import_diagnostic_card(self.rules,lookup[name],0,"squirrel-"+str(i),{"Green","Black"})
               for i,name in enumerate(("Squirrel Mob","Squirrel Sovereign"))]
        self.assertTrue(all(card.kind == "creature" for card in cards))
        sim=s.Simulator(self.rules,42,decks=(s.demo_deck(0)+cards,s.demo_deck(1)),diagnostic=True)
        player=sim.players[0]
        for card in cards:
            (player.hand if card in player.hand else player.library).remove(card)
            sim.enter_creature(card,player)
        mob=next(x for x in player.battlefield if x.card.name=="Squirrel Mob")
        self.assertEqual((sim.effective_card(mob).power,sim.effective_card(mob).toughness),(4,4))
        sim.send_to_destination(player,next(x for x in player.battlefield if x.card.name=="Squirrel Sovereign"))
        self.assertEqual((sim.effective_card(mob).power,sim.effective_card(mob).toughness),(2,2))
        self.assertFalse(sim.report()["learningEligible"])
        sim.invariant()

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
                self.assertNotIn("Training A", event["message"])
                self.assertNotIn("Training B", event["message"])
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
        self.assertEqual([d["mainCount"] for d in report["decks"]],[99,99,99,99])
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

    def test_random_decks_are_distinct_reproducible_and_cover_all_pairs(self):
        decks=[json.loads(p.read_text()) for p in sorted((HERE/"decks").glob("*.json"))]
        pairs=set()
        for seed in range(300):
            selected=s.select_decks(decks,seed)
            self.assertNotEqual(s.deck_fingerprint(selected[0]),s.deck_fingerprint(selected[1]))
            self.assertNotEqual(selected[0]["sourceDeckId"],selected[1]["sourceDeckId"])
            self.assertEqual([d["sourceDeckId"] for d in selected],
                             [d["sourceDeckId"] for d in s.select_decks(decks,seed)])
            pairs.add(tuple(sorted(d["sourceDeckId"] for d in selected)))
        self.assertEqual(len(pairs),6)
        schedule=s.schedule_decks(decks,42,6)
        self.assertEqual(len({tuple(sorted(d["sourceDeckId"] for d in pair)) for pair in schedule}),6)
        self.assertEqual([[d["sourceDeckId"] for d in pair] for pair in schedule],
                         [[d["sourceDeckId"] for d in pair] for pair in s.schedule_decks(decks,42,6)])
        with self.assertRaises(ValueError):s.schedule_decks(decks,42,7)
        with self.assertRaises(ValueError):s.select_decks([decks[0],dict(decks[0],sourceDeckId=999)],42)
        with self.assertRaises(ValueError):s.diagnose(self.rules,[decks[0],decks[0]],42,10)

    def test_synthetic_demo_decks_are_not_mirrors(self):
        a,b=s.demo_deck(0),s.demo_deck(1)
        self.assertNotEqual([(c.name,c.power,c.toughness) for c in a],
                            [(c.name,c.power,c.toughness) for c in b])
        copy=[dataclasses.replace(c,id="copy-"+c.id) for c in a]
        with self.assertRaises(ValueError):s.Simulator(self.rules,42,decks=(a,copy))

    def test_real_decks_complete_requested_window_without_training(self):
        decks = [json.loads((HERE/"decks"/name).read_text()) for name in ("14850373-budget-deck.json","5254666-garbo-gobbos.json")]
        report = s.diagnose(self.rules, decks, 42, 10)
        self.assertEqual(report["turnsCompleted"], [10,10])
        self.assertEqual(report["result"], "diagnostic_window_complete")
        self.assertEqual(report["commanders"], ["Kolodin, Triumph Caster","Zurgo Helmsmasher"])
        self.assertFalse(report["learningEligible"])
        self.assertFalse(report["productionEligible"])
        self.assertEqual(len(report["questions"]),133)
        self.assertTrue(next(q for q in report["questions"] if q.get("card")=="Kolodin, Triumph Caster")["diagnosticSupport"])
        self.assertEqual([p["life"] for p in report["events"][-1]["state"]["players"]],[28,40])
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
        decks=[json.loads((HERE/"decks"/name).read_text()) for name in ("14850373-budget-deck.json","5254666-garbo-gobbos.json")]
        report=s.diagnose(self.rules,decks,42,12)
        self.assertEqual(report["winner"],1)
        self.assertTrue(all(n<=12 for n in report["turnsStarted"]))
        self.assertGreater(report["events"][-1]["state"]["players"][0]["life"],0)
        self.assertGreaterEqual(report["events"][-1]["state"]["players"][0]["commanderDamage"]["1-commander"],21)
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
        sim.resolve_entry_triggers(triggers,card)
        tokens=[x for x in player.battlefield if x.card.is_token]
        self.assertEqual(len(tokens),1)
        self.assertEqual(tokens[0].card.name,"Goblin")
        self.assertEqual(tokens[0].card.event_definition.subtypes,frozenset({"Goblin"}))
        self.assertTrue(any(e.get("operation")=="create_tokens" for e in triggers))
        sim.send_to_destination(player,tokens[0])
        self.assertFalse(any(c.is_token for c in player.graveyard))
        sim.invariant()

    def test_obyra_faerie_entry_affects_only_opponent_and_can_end_game(self):
        deck=json.loads((HERE/"decks/27521806-faeries.json").read_text())
        definition=deck["commanders"][0]
        sprite=next(c for c in deck["mainboard"] if c["name"]=="Zephyr Sprite")
        identity=set(definition["colorIdentity"])
        obyra=s.import_diagnostic_card(self.rules,definition,0,"obyra",identity)
        one=s.import_diagnostic_card(self.rules,sprite,0,"sprite-1",identity)
        two=s.import_diagnostic_card(self.rules,sprite,0,"sprite-2",identity)
        self.assertEqual(obyra.kind,"creature")
        self.assertIn("flying",obyra.traits)
        sim=s.Simulator(self.rules,42,decks=(s.demo_deck(0)+[obyra,one,two],s.demo_deck(1)),diagnostic=True)
        player=sim.players[0]
        for card in (obyra,one,two):
            (player.hand if card in player.hand else player.library).remove(card)
            triggers=sim.enter_creature(card,player)
            if card is obyra:self.assertEqual(triggers,[])
            sim.resolve_entry_triggers(triggers,card)
        self.assertEqual((player.life,sim.players[1].life),(40,38))
        self.assertEqual(len([e for e in sim.events if e["kind"]=="trigger" and "Obyra" in e["message"]]),2)
        sim.players[1].life=1
        third=s.Card("sprite-3","Zephyr Sprite","creature",mana_cost="{U}",traits="1;1;flying",
                     power=1,toughness=1,land_subtypes=("Faerie","Wizard"),is_token=True)
        triggers=sim.enter_creature(third,player)
        sim.resolve_entry_triggers(triggers,third)
        self.assertEqual(sim.result,"win")
        self.assertEqual(sim.winner,0)
        self.assertFalse(sim.report()["learningEligible"])
        sim.invariant()

    def test_actual_cohort_and_color_data_affect_simulator_combat_stats(self):
        deck=json.loads((HERE/"decks/27521806-faeries.json").read_text())
        lookup={c["name"]:c for c in deck["commanders"]+deck["mainboard"]}
        cards=[s.import_diagnostic_card(self.rules,lookup[name],0,"actual-"+str(i),{"Blue","Black"})
               for i,name in enumerate(("Obyra, Dreaming Duelist","Briarberry Cohort","Zephyr Sprite"))]
        sim=s.Simulator(self.rules,42,decks=(s.demo_deck(0)+cards,s.demo_deck(1)),diagnostic=True)
        player=sim.players[0]
        for card in cards:
            (player.hand if card in player.hand else player.library).remove(card)
            triggers=sim.enter_creature(card,player)
            sim.resolve_entry_triggers(triggers,card)
        cohort=next(x for x in player.battlefield if x.card.name=="Briarberry Cohort")
        self.assertEqual((sim.effective_card(cohort).power,sim.effective_card(cohort).toughness),(2,2))
        self.assertEqual(sim.players[1].life,38)
        # Ordinary parsed creatures preserve their actual blue color, not just their creature type.
        sim.send_to_destination(player,next(x for x in player.battlefield if x.card.name=="Obyra, Dreaming Duelist"))
        self.assertEqual(sim.effective_card(cohort).power,2)
        sim.send_to_destination(player,next(x for x in player.battlefield if x.card.name=="Zephyr Sprite"))
        self.assertEqual(sim.effective_card(cohort).power,1)
        sim.invariant()

    def test_bitterblossom_upkeep_creates_faerie_and_triggers_obyra(self):
        deck=json.loads((HERE/"decks/27521806-faeries.json").read_text())
        lookup={c["name"]:c for c in deck["commanders"]+deck["mainboard"]}
        cards=[s.import_diagnostic_card(self.rules,lookup[name],0,"upkeep-"+str(i),{"Blue","Black"})
               for i,name in enumerate(("Obyra, Dreaming Duelist","Bitterblossom"))]
        self.assertEqual(cards[1].kind,"enchantment")
        sim=s.Simulator(self.rules,42,decks=(s.demo_deck(0)+cards,s.demo_deck(1)),diagnostic=True)
        p=sim.players[0]
        for card in cards:
            (p.hand if card in p.hand else p.library).remove(card)
            sim.resolve_entry_triggers(sim.enter_creature(card,p),card)
        self.assertEqual(sim.players[1].life,39)  # Kindred enchantment is itself a Faerie.
        sim.phase="untap";sim.step()
        self.assertEqual((p.life,sim.players[1].life),(39,38))
        token=next(x for x in p.battlefield if x.card.is_token)
        self.assertEqual(token.card.event_definition.subtypes,frozenset({"Faerie","Rogue"}))
        self.assertEqual(token.card.event_definition.colors,frozenset({"Black"}))
        self.assertIn("flying",sim.effective_card(token).traits)
        sim.invariant()

    def test_lethal_upkeep_resolves_token_before_loss_but_not_later_trigger(self):
        deck=json.loads((HERE/"decks/27521806-faeries.json").read_text())
        lookup={c["name"]:c for c in deck["commanders"]+deck["mainboard"]}
        cards=[s.import_diagnostic_card(self.rules,lookup[name],0,"lethal-"+str(i),{"Blue","Black"})
               for i,name in enumerate(("Obyra, Dreaming Duelist","Bitterblossom"))]
        sim=s.Simulator(self.rules,42,decks=(s.demo_deck(0)+cards,s.demo_deck(1)),diagnostic=True)
        p=sim.players[0]
        for card in cards:
            (p.hand if card in p.hand else p.library).remove(card)
            sim.resolve_entry_triggers(sim.enter_creature(card,p),card)
        p.life=1;sim.players[1].life=1
        sim.phase="untap";sim.step()
        self.assertEqual(sim.result,"win")
        self.assertEqual(sim.winner,1)
        self.assertEqual(sim.players[1].life,1)
        self.assertTrue(any(x.card.is_token for x in p.battlefield))
        sim.invariant()

    def test_real_deck_bitterbloom_tokens_feed_obyra(self):
        decks=[json.loads((HERE/"decks"/name).read_text()) for name in
               ("27521806-faeries.json","14850373-budget-deck.json")]
        report=s.diagnose(self.rules,decks,3,10)
        self.assertEqual(report["turnsCompleted"],[10,10])
        upkeep=[e for e in report["events"] if e["kind"]=="upkeep" and "Bitterbloom" in e["message"]]
        triggers=[e for e in report["events"] if e["kind"]=="trigger" and "Obyra, Dreaming Duelist triggers" in e["message"]]
        self.assertEqual(len(upkeep),8)
        self.assertEqual(len(triggers),4)
        self.assertTrue(all(e["details"]["amount"]==1 for e in triggers))
        self.assertFalse(report["learningEligible"])

    def test_seer_scry_keeps_top_cards_private_and_does_not_draw(self):
        deck=json.loads((HERE/"decks/27521806-faeries.json").read_text())
        lookup={c["name"]:c for c in deck["commanders"]+deck["mainboard"]}
        cards=[s.import_diagnostic_card(self.rules,lookup[name],0,"seer-test-"+str(i),{"Blue","Black"})
               for i,name in enumerate(("Obyra, Dreaming Duelist","Faerie Seer"))]
        sim=s.Simulator(self.rules,42,decks=(s.demo_deck(0)+cards,s.demo_deck(1)),diagnostic=True)
        player=sim.players[0]
        (player.hand if cards[0] in player.hand else player.library).remove(cards[0])
        sim.resolve_entry_triggers(sim.enter_creature(cards[0],player),cards[0])
        (player.hand if cards[1] in player.hand else player.library).remove(cards[1])
        top=list(player.library[-2:])
        triggers=sim.enter_creature(cards[1],player)
        sim.resolve_entry_triggers(triggers,cards[1])
        self.assertEqual(player.library[-2:],top)
        self.assertEqual(sim.players[1].life,39)
        message=next(e["message"] for e in sim.events if "scries" in e["message"])
        self.assertIn("scries 2",message)
        self.assertTrue(all(c.name not in message for c in top))
        before=sim.observe(1)
        player.library[-2:]=reversed(player.library[-2:])
        self.assertEqual(before,sim.observe(1))
        sim.invariant()

    def test_faerie_rules_are_used_in_real_deck_match(self):
        decks=[json.loads((HERE/"decks"/name).read_text()) for name in ("5254666-garbo-gobbos.json","27521806-faeries.json")]
        result=s.diagnose(self.rules,decks,44,10)
        events=result["events"]
        self.assertTrue(any(e["kind"]=="cast" and e["details"].get("card")=="Obyra, Dreaming Duelist" for e in events))
        self.assertTrue(any(e["kind"]=="cast" and e["details"].get("card")=="Briarberry Cohort" for e in events))
        self.assertTrue(any(e["kind"]=="cast" and e["details"].get("card")=="Faerie Seer" for e in events))
        self.assertEqual(len([e for e in events if e["kind"]=="trigger" and "Obyra, Dreaming Duelist triggers" in e["message"]]),2)
        self.assertTrue(any("scries 2" in e["message"] for e in events))
        self.assertFalse(result["learningEligible"])
        partial={q["card"] for q in result["questions"] if q.get("diagnosticSupport")}
        self.assertTrue({"Obyra, Dreaming Duelist","Briarberry Cohort","Faerie Seer"}.issubset(partial))

    def test_scry_empty_library_is_not_a_failed_draw(self):
        sim=s.Simulator(self.rules,42)
        p=sim.players[0]
        p.graveyard.extend(p.library);p.library.clear()
        card=s.Card("scry-source","Test","creature")
        sim.resolve_entry_triggers([{"kind":"trigger","source":"scry-source","effect":"scry","amount":2,"controller":0}],card)
        self.assertFalse(p.failed_draw)
        self.assertFalse(sim.finished)
        self.assertIn("scries 0",sim.events[-1]["message"])

    def test_opposing_faerie_does_not_trigger_obyra(self):
        deck=json.loads((HERE/"decks/27521806-faeries.json").read_text())
        obyra=s.import_diagnostic_card(self.rules,deck["commanders"][0],0,"obyra",{"Blue","Black"})
        raw=next(c for c in deck["mainboard"] if c["name"]=="Zephyr Sprite")
        sprite=s.import_diagnostic_card(self.rules,raw,1,"opponent-sprite",{"Blue","Black"})
        sim=s.Simulator(self.rules,42,decks=(s.demo_deck(0)+[obyra],s.demo_deck(1)+[sprite]),diagnostic=True)
        for seat,card in ((0,obyra),(1,sprite)):
            sim.active=seat;p=sim.players[seat]
            (p.hand if card in p.hand else p.library).remove(card)
            triggers=sim.enter_creature(card,p)
            sim.resolve_entry_triggers(triggers,card)
        self.assertEqual([p.life for p in sim.players],[40,40])

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

    def test_old_mirror_training_state_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            out=Path(directory)
            legacy={"schemaVersion":1,"seed":42,"evaluationSeedsPerGeneration":2,
                    "champion":s.Policy().to_json(),"history":[{"generation":0}]}
            s.write_json(out/"state.json",legacy)
            before=(out/"state.json").read_bytes()
            with self.assertRaises(ValueError):s.train(self.rules,out,1,42,2)
            self.assertEqual(before,(out/"state.json").read_bytes())

    def test_viewer_payload_cannot_close_script(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"test.json"
            s.export_review(path,{"schemaVersion":1,"kind":"rules-review","questions":[],
                                  "test":"</script><script>alert(1)</script>"})
            self.assertNotIn("</script><script>alert",path.with_suffix(".html").read_text())


if __name__ == "__main__":unittest.main()
