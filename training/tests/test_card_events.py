import json
from pathlib import Path
import sys
import unittest

HERE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HERE))
from card_events import Game, Permanent, Definition, parse_card, NeedsRules, IllegalAction

deck=json.loads((HERE/"decks/14850373-budget-deck.json").read_text())
fairies=json.loads((HERE/"decks/27521806-faeries.json").read_text())
squirrels=json.loads((HERE/"decks/8321184-squirrels.json").read_text())
goblins=json.loads((HERE/"decks/5254666-garbo-gobbos.json").read_text())
cards={c["name"]:c for c in deck["commanders"]+deck["mainboard"]+fairies["commanders"]+fairies["mainboard"]+squirrels["commanders"]+squirrels["mainboard"]}
cards.update({c["name"]:c for c in goblins["mainboard"]})

def real(name,id,controller=0):
    return Permanent(id,parse_card(cards[name]),controller)

def creature(id,legendary=False,controller=0,power=2,fresh=False):
    return Permanent(id,Definition(id,frozenset({"Creature"}),frozenset({"Human"}),
                                  legendary,power,2,frozenset()),controller,fresh=fresh)

class CardEventChecks(unittest.TestCase):
    def test_impact_tremors_watches_creatures_and_tokens_not_enemy_or_vehicle(self):
        g=Game(); g.enter(real("Impact Tremors","tremors"))
        g.enter(real("Thundering Chariot","vehicle"))
        g.enter(real("Goblin Instigator","enemy",1))
        self.assertFalse(any(e.get("effect")=="deal 1 damage to each opponent" for e in g.events))
        g.enter(real("Goblin Instigator","ally"))
        triggers=[e for e in g.events if e.get("effect")=="deal 1 damage to each opponent"]
        self.assertEqual(len(triggers),1)  # The token trigger has not resolved yet.
        self.assertTrue(any(e.get("operation")=="create_tokens" for e in g.events))
        self.assertTrue(all(e["controller"]==0 and e["source"]=="tremors" for e in triggers))
        altered=dict(cards["Impact Tremors"],oracleText=cards["Impact Tremors"]["oracleText"]+"\nDraw a card.")
        self.assertFalse(parse_card(altered).supported)

    def test_nested_shambler_death_uses_last_known_power_and_counts_zero(self):
        g=Game(); g.enter(real("Nested Shambler","shambler"))
        g.battlefield["shambler"].counters=3
        self.assertEqual(g.death_triggers(["shambler"])[0]["amount"],4)
        g.battlefield["shambler"].counters=-2
        self.assertEqual(g.death_triggers(["shambler"])[0]["amount"],0)
        altered=dict(cards["Nested Shambler"],oracleText=cards["Nested Shambler"]["oracleText"]+"\nDraw a card.")
        self.assertFalse(parse_card(altered).supported)

    def test_death_triggers_look_back_and_distinguish_control(self):
        g=Game(); g.enter(real("Blood Artist","artist")); g.enter(real("Zulaport Cutthroat","z"))
        g.enter(creature("ally")); g.enter(creature("enemy",controller=1))
        triggers=g.death_triggers(["artist","z","ally","enemy"])
        self.assertEqual(sum(t["name"]=="Blood Artist" for t in triggers),4)
        self.assertEqual(sum(t["name"]=="Zulaport Cutthroat" for t in triggers),3)
        self.assertNotIn("enemy",[t["dead"] for t in triggers if t["name"]=="Zulaport Cutthroat"])
        self.assertIn("artist",[t["dead"] for t in triggers if t["name"]=="Blood Artist"])
        for name in ("Blood Artist","Zulaport Cutthroat"):
            self.assertFalse(parse_card(dict(cards[name],oracleText=cards[name]["oracleText"]+"\nDraw a card.")).supported)

    def test_squirrel_bonuses_count_controller_and_other_permanents(self):
        g=Game(); g.enter(real("Squirrel Mob","mob")); g.enter(real("Squirrel Sovereign","lord"))
        self.assertEqual(g.stats(g.battlefield["mob"]),(4,4))
        self.assertEqual(g.stats(g.battlefield["lord"]),(2,2))
        g.enter(real("Squirrel Sovereign","enemy",1))
        self.assertEqual(g.stats(g.battlefield["mob"]),(5,5))
        self.assertEqual(g.stats(g.battlefield["enemy"]),(2,2))
        g.enter(real("Squirrel Sovereign","second"))
        self.assertEqual(g.stats(g.battlefield["mob"]),(7,7))
        self.assertEqual(g.stats(g.battlefield["lord"]),(3,3))
        g.leave("second"); g.leave("enemy"); g.leave("lord")
        self.assertEqual(g.stats(g.battlefield["mob"]),(2,2))
        for name in ("Squirrel Mob","Squirrel Sovereign"):
            altered=dict(cards[name],oracleText=cards[name]["oracleText"]+"\nDraw a card.")
            self.assertFalse(parse_card(altered).supported)

    def test_actual_cards_and_unknown_text(self):
        for name in ("Kolodin, Triumph Caster","Andúril, Flame of the West","Brightfield Mustang","Thundering Chariot"):
            self.assertTrue(parse_card(cards[name]).supported,name)
        g=Game()
        with self.assertRaises(NeedsRules):g.enter(Permanent("b", parse_card(dict(cards["Bridled Bighorn"], oracleText=cards["Bridled Bighorn"]["oracleText"]+"\nDraw a card.")), 0))
        self.assertEqual(g.questions[0]["card"],"Bridled Bighorn")
        self.assertTrue(g.questions[0]["blocking"])
        self.assertNotIn("b",g.battlefield)
        modified=dict(cards["Kolodin, Triumph Caster"],oracleText=cards["Kolodin, Triumph Caster"]["oracleText"]+"\nDraw a card.")
        self.assertFalse(parse_card(modified).supported)

    def test_obyra_watches_each_other_faerie_controlled_by_her_player(self):
        g=Game();g.enter(real("Obyra, Dreaming Duelist","o"))
        self.assertFalse(any(e.get("effect")=="each opponent loses 1 life" for e in g.events))
        g.enter(real("Zephyr Sprite","enemy",1))
        self.assertFalse(any(e.get("effect")=="each opponent loses 1 life" for e in g.events))
        g.enter(real("Zephyr Sprite","sprite-a"))
        g.enter(real("Zephyr Sprite","sprite-b"))
        triggers=[e for e in g.events if e.get("effect")=="each opponent loses 1 life"]
        self.assertEqual([e["entered"] for e in triggers],["sprite-a","sprite-b"])
        self.assertTrue(all(e["controller"]==0 and e["amount"]==1 for e in triggers))
        self.assertTrue(g.has(g.battlefield["o"],"flying"))

    def test_obyra_rejects_changed_rules_text(self):
        altered=dict(cards["Obyra, Dreaming Duelist"],oracleText=cards["Obyra, Dreaming Duelist"]["oracleText"]+"\nDraw a card.")
        self.assertFalse(parse_card(altered).supported)

    def test_faerie_seer_and_obyra_both_trigger_on_entry(self):
        g=Game();g.enter(real("Obyra, Dreaming Duelist","o"));g.enter(real("Faerie Seer","seer"))
        effects=[e["effect"] for e in g.events if e["kind"]=="trigger"]
        self.assertEqual(effects,["each opponent loses 1 life","scry"])
        event=next(e for e in g.events if e.get("effect")=="scry")
        self.assertEqual((event["controller"],event["amount"]),(0,2))

    def test_obyra_watches_faerie_kindred_even_if_not_creature(self):
        g=Game();g.enter(real("Obyra, Dreaming Duelist","o"))
        g.enter(real("Bitterblossom","bb"))
        self.assertFalse(g.creature(g.battlefield["bb"]))
        self.assertTrue(any(e.get("source")=="o" and e.get("entered")=="bb" for e in g.events))
        upkeep=g.upkeep_triggers()
        self.assertEqual([(e["name"],list(e["tokenSpec"]["colors"]),list(e["tokenSpec"]["subtypes"])) for e in upkeep],
                         [("Bitterblossom",["Black"],["Faerie","Rogue"])])
        g.turn_player=1
        self.assertEqual(g.upkeep_triggers(),[])

    def test_bitterbloom_and_bitterblossom_have_separate_upkeep_tokens(self):
        g=Game();g.enter(real("Bitterblossom","bb"));g.enter(real("Bitterbloom Bearer","bearer"))
        triggers=g.upkeep_triggers()
        self.assertEqual(len(triggers),2)
        bearer=next(t for t in triggers if t["name"]=="Bitterbloom Bearer")
        self.assertEqual(list(bearer["tokenSpec"]["colors"]),["Blue","Black"])
        self.assertEqual(list(bearer["tokenSpec"]["subtypes"]),["Faerie"])

    def test_cohort_uses_another_blue_creature_you_control(self):
        g=Game();g.enter(real("Briarberry Cohort","c"))
        cohort=g.battlefield["c"]
        self.assertEqual(g.stats(cohort),(1,1))
        g.enter(real("Zephyr Sprite","enemy",1))
        self.assertEqual(g.stats(cohort),(1,1))
        g.enter(creature("red"))
        self.assertEqual(g.stats(cohort),(1,1))
        g.enter(real("Zephyr Sprite","ally"))
        self.assertEqual(g.stats(cohort),(2,2))
        g.enter(real("Zephyr Sprite","ally2"))
        self.assertEqual(g.stats(cohort),(2,2))
        g.leave("ally");g.leave("ally2")
        self.assertEqual(g.stats(cohort),(1,1))

    def test_cohort_does_not_count_a_blue_noncreature(self):
        g=Game();g.enter(real("Briarberry Cohort","c"))
        enchantment=Definition("Blue enchantment",frozenset({"Enchantment"}),frozenset(),False,0,0,frozenset(),colors=frozenset({"Blue"}))
        g.battlefield["enchantment"]=Permanent("enchantment",enchantment,0)
        self.assertEqual(g.stats(g.battlefield["c"]),(1,1))

    def test_kolodin_sees_types_on_entry_and_controller(self):
        g=Game();g.enter(real("Kolodin, Triumph Caster","k"))
        g.enter(real("Brightfield Mustang","m"));g.enter(real("Thundering Chariot","v"))
        g.enter(real("Brightfield Mustang","other",1))
        self.assertTrue(g.battlefield["m"].saddled)
        self.assertTrue(g.battlefield["v"].animated)
        self.assertTrue(g.creature(g.battlefield["m"]))
        self.assertTrue(g.creature(g.battlefield["v"]))
        self.assertTrue(g.has(g.battlefield["m"],"haste"))
        self.assertFalse(g.battlefield["other"].saddled)
        self.assertFalse(g.has(g.battlefield["other"],"haste"))

    def test_kolodin_entering_later_only_grants_haste(self):
        g=Game();g.enter(real("Brightfield Mustang","m"));g.enter(real("Thundering Chariot","v"))
        self.assertTrue(g.creature(g.battlefield["m"]))
        self.assertFalse(g.creature(g.battlefield["v"]))
        g.enter(real("Kolodin, Triumph Caster","k"))
        self.assertTrue(g.has(g.battlefield["m"],"haste"))
        self.assertFalse(g.battlefield["m"].saddled)
        self.assertFalse(g.battlefield["v"].animated)

    def test_crew_checks_power_control_other_and_taps_fresh_creature(self):
        g=Game();g.enter(real("Thundering Chariot","v"));g.enter(creature("new",power=1,fresh=True));g.enter(creature("opponent",controller=1))
        with self.assertRaises(IllegalAction):g.crew("v",[],0)
        with self.assertRaises(IllegalAction):g.crew("v",["opponent"],0)
        self.assertFalse(g.battlefield["new"].tapped)
        g.crew("v",["new"],0)
        self.assertTrue(g.battlefield["new"].tapped)
        self.assertTrue(g.creature(g.battlefield["v"]))
        with self.assertRaises(IllegalAction):g.crew("v",["v"],0)

    def test_saddle_is_sorcery_speed_and_does_not_make_mount_creature(self):
        g=Game();g.enter(real("Brightfield Mustang","m"));g.enter(creature("helper"))
        self.assertTrue(g.creature(g.battlefield["m"]))
        g.phase="combat"
        with self.assertRaises(IllegalAction):g.saddle("m",["helper"],0)
        g.phase="main";g.saddle("m",["helper"],0)
        self.assertTrue(g.battlefield["m"].saddled)
        self.assertTrue(g.battlefield["helper"].tapped)
        self.assertTrue(g.creature(g.battlefield["m"]))

    def test_anduril_nonlegendary_spirits_tapped_not_attacking(self):
        g=Game();g.enter(creature("bear"));g.enter(real("Andúril, Flame of the West","e"))
        g.mana[0]=2;g.equip("e","bear",0)
        self.assertEqual(g.stats(g.battlefield["bear"]),(5,3))
        self.assertEqual(g.mana[0],0)
        g.phase="combat";g.attack("bear",1)
        spirits=[p for p in g.battlefield.values() if p.token]
        self.assertEqual(len(spirits),2)
        self.assertTrue(all(p.tapped and p.attacking is None and g.has(p,"flying") for p in spirits))
        self.assertEqual(sum(e["kind"]=="attacks" for e in g.events),1)

    def test_anduril_legendary_spirits_enter_attacking(self):
        g=Game();g.enter(creature("legend",legendary=True));g.enter(real("Andúril, Flame of the West","e"))
        g.mana[0]=2;g.equip("e","legend",0);g.phase="combat";g.attack("legend",1)
        spirits=[p for p in g.battlefield.values() if p.token]
        self.assertEqual(len(spirits),2)
        self.assertTrue(all(p.attacking==1 and p.tapped for p in spirits))

    def test_opponent_attacker_equipment_controller_tokens_not_attacking(self):
        g=Game();g.enter(creature("legend",legendary=True));g.enter(real("Andúril, Flame of the West","e"))
        g.mana[0]=2;g.equip("e","legend",0)
        g.battlefield["legend"].controller=1
        g.turn_player=1;g.phase="combat";g.attack("legend",0)
        spirits=[p for p in g.battlefield.values() if p.token]
        self.assertTrue(all(p.controller==0 and p.tapped and p.attacking is None for p in spirits))

    def test_equip_cost_timing_and_retarget(self):
        g=Game();g.enter(creature("a"));g.enter(creature("b"));g.enter(real("Andúril, Flame of the West","e"))
        with self.assertRaises(IllegalAction):g.equip("e","a",0)
        g.mana[0]=4;g.phase="combat"
        with self.assertRaises(IllegalAction):g.equip("e","a",0)
        g.phase="main";g.equip("e","a",0);g.equip("e","b",0)
        self.assertEqual(g.stats(g.battlefield["a"]),(2,2))
        self.assertEqual(g.stats(g.battlefield["b"]),(5,3))
        self.assertEqual(g.mana[0],0)

    def test_mustang_saddled_attack_and_end_of_turn(self):
        g=Game();g.enter(real("Kolodin, Triumph Caster","k"));g.enter(real("Brightfield Mustang","m"))
        g.phase="combat";g.attack("m",1)
        m=g.battlefield["m"]
        self.assertFalse(m.tapped)
        self.assertEqual(g.stats(m),(4,4))
        g.cleanup()
        self.assertFalse(m.saddled)
        self.assertEqual(g.stats(m),(4,4))

    def test_vehicle_cleanup_detaches_equipment(self):
        g=Game();g.enter(real("Kolodin, Triumph Caster","k"));g.enter(real("Thundering Chariot","v"));g.enter(real("Andúril, Flame of the West","e"))
        g.mana[0]=2;g.equip("e","v",0)
        g.cleanup()
        self.assertFalse(g.creature(g.battlefield["v"]))
        self.assertIsNone(g.battlefield["e"].attached_to)
        self.assertTrue(g.has(g.battlefield["v"],"haste"))

    def test_losing_kolodin_removes_haste_but_not_entry_effect(self):
        g=Game();g.enter(real("Kolodin, Triumph Caster","k"));g.enter(real("Brightfield Mustang","m"))
        g.leave("k")
        self.assertFalse(g.has(g.battlefield["m"],"haste"))
        self.assertTrue(g.battlefield["m"].saddled)
        g.phase="combat"
        with self.assertRaises(IllegalAction):g.attack("m",1)

if __name__=="__main__": unittest.main()
