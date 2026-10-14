"""Check the universal material chair keeps wood block IDs and drops obsolete IDs."""
import unittest,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
JAVA=ROOT/"src/main/java/dev/casz/caszualmtg"
ASSETS=ROOT/"src/main/resources/assets/caszual_mtg"
DATA=ROOT/"src/main/resources/data/caszual_mtg"

def src(file):return (JAVA/file).read_text(encoding="utf8")
def js(file):return json.loads(file.read_text(encoding="utf8"))

class UniversalChairTests(unittest.TestCase):
 def test_single_recipe_is_dynamic_and_source_exact(self):
  recipe=src("ChairRecipe.java")
  self.assertIn("input.width()!=3||input.height()!=3",recipe)
  self.assertIn("ChairWood.eligible(item)",recipe)
  self.assertIn("material.equals(current)",recipe)
  self.assertIn("chair.set(CaszualMtg.CHAIR_MATERIAL,material)",recipe)
  self.assertIn('"type": "caszual_mtg:chair_material"', (DATA/"recipe/material_chair.json").read_text())
  self.assertIn("public static final ChairRecipe INSTANCE",recipe)

 def test_accepts_planks_logs_and_stripped_and_modded(self):
  code=src("ChairWood.java")
  for token in ('ItemTags.PLANKS','ItemTags.LOGS','"_planks"','"_log"','"_wood"','"_stem"','"_hyphae"','"stripped_"'):
   self.assertIn(token,code)
  self.assertIn("BuiltInRegistries.BLOCK.getKey(Block.byItem",code)
  self.assertIn("Identifier.tryParse(name)",code)

 def test_inventory_and_world_models_retarget_material_only(self):
  code=src("CustomBoxModels.java")
  for token in ("CHAIR_SOURCE","new ChairWorldModel(model)","new ChairItemModel(model)",
                "level.getBlockEntityRenderData(pos)","getParticleMaterial(ChairWood.block(id).defaultBlockState())",
                "remap(q,material,CHAIR_SOURCE)","appendModelIdentityElement(id)"):
   self.assertIn(token,code)
  self.assertIn('"minecraft","block/oak_planks"',code)
  self.assertEqual(js(ASSETS/"models/block/material_chair.json")["textures"]["wood"],"minecraft:block/oak_planks")

 def test_material_survives_placement_break_and_update(self):
  code=src("ChairBlock.java")
  entity=src("ChairBlockEntity.java")
  for text in ("stack.getOrDefault(CaszualMtg.CHAIR_MATERIAL","getCloneItemStack","getDrops",
               "result.set(CaszualMtg.CHAIR_MATERIAL,chair.material())"):
   self.assertIn(text,code)
  for text in ('out.putString("ChairWood"','in.getStringOr("ChairWood"','getUpdateTag',
               'getUpdatePacket','getRenderData','builder.set(CaszualMtg.CHAIR_MATERIAL,material)'):
   self.assertIn(text,entity)

 def test_only_generic_chair_is_registered(self):
  common=src("CaszualMtg.java")
  self.assertNotIn("CHAIRS=chairs()",common)
  self.assertIn("CHAIR_BE=chairEntityType()",common)
  self.assertIn("e.accept(MATERIAL_CHAIR)",common)
  for wood in ("oak","spruce","birch","jungle","acacia","dark_oak","mangrove","cherry",
               "bamboo","crimson","warped","pale_oak"):
   with self.subTest(wood=wood):
    self.assertNotIn('"'+wood+'_chair"',common)
    self.assertFalse((DATA/f"recipe/{wood}_chair.json").exists())

if __name__=="__main__":unittest.main()
