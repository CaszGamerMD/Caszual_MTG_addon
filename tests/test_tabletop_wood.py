"""Single material-driven tabletop and removal of obsolete chair assets."""
import json
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
JAVA=ROOT/"src/main/java/dev/casz/caszualmtg"
RES=ROOT/"src/main/resources"
WOODS=("oak","spruce","birch","jungle","acacia","dark_oak","mangrove","cherry","bamboo","crimson","warped","pale_oak")

def code(file):return (JAVA/file).read_text(encoding="utf-8")

class MaterialTableTests(unittest.TestCase):
 def test_table_recipe_is_material_driven(self):
  recipe=json.loads((RES/"data/caszual_mtg/recipe/tabletop.json").read_text())
  self.assertEqual(recipe["type"],"caszual_mtg:tabletop_material")
  source=code("TabletopRecipe.java")
  for token in ("ChairWood.eligible(item)","ChairWood.fromItem(item)","source.equals(current)",
                "Blocks.GREEN_WOOL.asItem()","Items.STICK","table.set(CaszualMtg.TABLE_MATERIAL,id)"):
   self.assertIn(token,source)
 def test_table_wood_persists_without_changing_battlefield_storage(self):
  block=code("TabletopBlock.java")
  entity=code("TabletopBlockEntity.java")
  for token in ("getCloneItemStack","getDrops","TABLE_MATERIAL","ChairWood.fromItem(held)",
                "p.isShiftKeyDown()","useWithoutItem(s,level,pos,p,hit)"):
   self.assertIn(token,block)
  for token in ('"TableWood"',"getRenderData()","getUpdateTag","getUpdatePacket",
                "collectImplicitComponents",'out.store("PlayedCards"',
                "CommanderReference","SeatOwner","minecraft:dark_oak_planks"):
   self.assertIn(token,entity)
 def test_retexture_only_wood_not_felt_or_cards(self):
  c=code("CustomBoxModels.java")
  for token in ('TABLE_SOURCE','new TableWorldModel(model)','new TableItemModel(model)',
                'remap(q,wood,TABLE_SOURCE)','getBlockEntityRenderData(pos)',
                'state.appendModelIdentityElement(id)'):
   self.assertIn(token,c)
  model=json.loads((RES/"assets/caszual_mtg/models/block/tabletop.json").read_text())
  self.assertEqual(model["textures"]["wood"],"minecraft:block/dark_oak_planks")
  self.assertEqual(model["elements"][1]["faces"]["up"]["texture"],"#felt")
 def test_single_chair_remains_no_dead_assets(self):
  src=code("CaszualMtg.java")
  self.assertIn('id("material_chair")',src)
  self.assertNotIn('CHAIRS=chairs()',src)
  self.assertIn('FabricBlockEntityTypeBuilder.create(ChairBlockEntity::new,MATERIAL_CHAIR)',src)
  for wood in WOODS:
   for relative in (f"assets/caszual_mtg/models/block/{wood}_chair.json",
                    f"assets/caszual_mtg/blockstates/{wood}_chair.json",
                    f"assets/caszual_mtg/items/{wood}_chair.json",
                    f"data/caszual_mtg/loot_table/blocks/{wood}_chair.json",
                    f"data/caszual_mtg/recipe/{wood}_chair.json"):
    self.assertFalse((RES/relative).exists(),relative)
 def test_registers_persistent_component_serializer(self):
  src=code("CaszualMtg.java")
  self.assertIn("TABLE_MATERIAL",src)
  self.assertIn('id("tabletop_material")',src)
  self.assertIn("new TabletopBlockItem(",src)

if __name__=="__main__":unittest.main()
