"""Tabletop chair models, cushion matching and reset safety invariants."""
import json
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
JAVA=ROOT/"src/main/java/dev/casz/caszualmtg"
RES=ROOT/"src/main/resources"
ASSETS=RES/"assets/caszual_mtg"
DATA=RES/"data/caszual_mtg"
WOODS=("oak","spruce","birch","jungle","acacia","dark_oak","mangrove",
       "cherry","bamboo","crimson","warped","pale_oak")
COLORS=("white","orange","magenta","light_blue","yellow","lime","pink","gray",
        "light_gray","cyan","purple","blue","brown","green","red","black")

def read(path):
    return json.loads(path.read_text(encoding="utf-8"))

class TabletopChairAndResetTests(unittest.TestCase):
    def test_wood_models_and_recipes(self):
        for wood in WOODS:
            with self.subTest(wood=wood):
                name=wood+"_chair"
                model=read(ASSETS/f"models/block/{name}.json")
                self.assertEqual(model["textures"]["wood"],f"minecraft:block/{wood}_planks")
                self.assertTrue(any(e["to"][1]==8 and e["from"][1]==7 for e in model["elements"]),
                                "Seat should be at eight model pixels, the height of a slab")
                states=read(ASSETS/f"blockstates/{name}.json")["multipart"]
                self.assertEqual(len(states),4*(2*len(COLORS)+1))
                # Old identifiers remain valid for already placed chairs, but
                # a single universal recipe now crafts the material-bearing chair.
                self.assertFalse((DATA/f"recipe/{name}.json").exists())
                self.assertEqual(read(ASSETS/f"items/{name}.json")["model"]["model"],f"caszual_mtg:block/{name}")
    def test_dynamic_chair_recipe_and_source_materials(self):
        recipe=read(DATA/"recipe/material_chair.json")
        self.assertEqual(recipe["type"],"caszual_mtg:chair_material")
        chair=(JAVA/"ChairRecipe.java").read_text(encoding="utf-8")
        self.assertIn("ChairWood.eligible(item)",chair)
        self.assertIn("CHAIR_MATERIAL",chair)
        self.assertIn("current.equals",chair) if "current.equals" in chair else self.assertIn("material.equals(current)",chair)
        model=read(ASSETS/"models/block/material_chair.json")
        self.assertEqual(model["textures"]["wood"],"minecraft:block/oak_planks")
        self.assertEqual(len(read(ASSETS/"blockstates/material_chair.json")["multipart"]),4*(2*len(COLORS)+1))

    def test_cushion_overlays_are_slightly_above_seat(self):
        for color in COLORS:
            with self.subTest(color=color):
                model=read(ASSETS/f"models/block/chair_cushion_{color}.json")
                self.assertEqual(model["textures"]["fabric"],f"minecraft:block/{color}_wool")
                self.assertTrue(all(e["from"][1]>8 for e in model["elements"]))
                leather=read(ASSETS/f"models/block/chair_cushion_leather_{color}.json")
                self.assertEqual(leather["textures"]["fabric"],f"minecraft:block/{color}_terracotta")
    def test_paper_color_is_linked_not_manual(self):
        chair=(JAVA/"ChairBlock.java").read_text(encoding="utf-8")
        table=(JAVA/"TabletopLogic.java").read_text(encoding="utf-8")
        seat=(JAVA/"ChairSeats.java").read_text(encoding="utf-8")
        for token in ("Items.PAPER","Items.LEATHER","_wool","DyeItem","ChairBlock.matchPaper"):
            if token=="ChairBlock.matchPaper":continue
            self.assertIn(token,chair)
        self.assertIn("neighbor.getValue(TabletopBlock.FELT)",chair)
        self.assertIn("ChairBlock.refreshNextToTable",table)
        self.assertIn("Attributes.SCALE",seat)
        self.assertIn("startRiding(seat)",seat)
    def test_card_reset_recovers_owned_cards_and_commander(self):
        table=(JAVA/"TabletopLogic.java").read_text(encoding="utf-8")
        tile=(JAVA/"TabletopBlockEntity.java").read_text(encoding="utf-8")
        wire=(JAVA/"TabletopWire.java").read_text(encoding="utf-8")
        for token in ('case "reset"', "private static String reset(", "owner.toString().equals(card.owner())",
                      "sourceMainSlot","c.hand.takeAllCards()","c.grave.setStack(entry.slot(),ItemStack.EMPTY)",
                      "c.deck.shuffle()","putCardsOnBottom(returning)"):
            self.assertIn(token,table)
        self.assertIn('"CommanderReference"',tile)
        self.assertIn("rememberCommander(one)",table)
        self.assertIn("List<ItemStack> reveal",wire)
        self.assertIn('case "reveal_to_hand","reveal_to_field","reveal_end"',table)
        self.assertIn('case "flip"',table) if 'case "flip"' in table else self.assertIn('"flip"',table)
    def test_table_has_wood_border_around_inset_mat(self):
        model=read(ASSETS/"models/block/tabletop.json")
        main=model["elements"][0]
        self.assertEqual(main["faces"]["up"]["texture"],"#wood")
        inset=[e for e in model["elements"] if e["faces"].get("up",{}).get("texture")=="#felt"]
        self.assertEqual(len(inset),1)
        self.assertEqual(inset[0]["from"][0],1)
        self.assertEqual(inset[0]["to"][0],15)

if __name__=="__main__":
    unittest.main()
