"""Regression coverage for placing every utility box with its control face toward the player."""
import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
JAVA=ROOT/"src/main/java/dev/casz/caszualmtg"
ASSETS=ROOT/"src/main/resources/assets/caszual_mtg"
BOXES=("land_database","token_database","community_database","deck_builder")
FACING={"north":0,"east":90,"south":180,"west":270}


class UtilityBoxFacingTests(unittest.TestCase):
    def test_all_four_boxes_have_horizontal_facing_variants(self):
        for name in BOXES:
            with self.subTest(name=name):
                blockstate=json.loads((ASSETS/f"blockstates/{name}.json").read_text())
                variants=blockstate["variants"]
                self.assertEqual(set(variants),{f"facing={direction}" for direction in FACING})
                for facing,y in FACING.items():
                    self.assertEqual(variants[f"facing={facing}"],
                                     {"model":f"caszual_mtg:block/{name}","y":y})
                model=json.loads((ASSETS/f"models/block/{name}.json").read_text())
                self.assertEqual(model["textures"]["north"],
                                 f"caszual_mtg:block/{name}_front",
                                 "Only the front should rotate toward the player")
                self.assertEqual(model["textures"]["up"],
                                 f"caszual_mtg:block/{name}_top")
                item=json.loads((ASSETS/f"items/{name}.json").read_text())
                self.assertIn("model",item)

    def test_placement_orientation_uses_opposite_player_direction(self):
        bank=(JAVA/"CaszualMtg.java").read_text()
        builder=(JAVA/"BuilderBlock.java").read_text()
        for name,code in (("bank",bank[bank.index("static final class BankBlock extends Block"):]),
                          ("builder",builder)):
            with self.subTest(type=name):
                self.assertIn("BlockStateProperties.HORIZONTAL_FACING",code)
                self.assertIn("builder.add(FACING)",code)
                self.assertIn("Direction.NORTH",code,
                              "Previous placed blocks without facing must default to north")
                self.assertIn("context.getHorizontalDirection().getOpposite()",code)
                self.assertIn("getStateForPlacement(BlockPlaceContext context)",code)

    def test_saved_data_and_block_ids_unchanged(self):
        mod=(JAVA/"CaszualMtg.java").read_text()
        for name in BOXES:
            self.assertIn(f'"{name}"',mod)
        builder=(JAVA/"BuilderBlock.java").read_text()
        self.assertIn("new BuilderBlockEntity(pos,s)",builder)
        self.assertIn("ServerLogic.open(sp,pos,3)",builder)

if __name__=="__main__":
    unittest.main()
