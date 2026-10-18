"""Verify Caszual Graveyard & Deck Control panel reskin and persistent lid."""
from pathlib import Path
import json
import unittest

ROOT=Path(__file__).resolve().parents[1]
JAVA=ROOT/"src/main/java/dev/casz/caszualmtg"
ASSETS=ROOT/"src/main/resources/assets/caszual_mtg"

def java(name):return (JAVA/name).read_text()

class CustomMtgDevices(unittest.TestCase):
 def test_material_persistence_and_multiplayer_updates_are_isolated(self):
  for name in ("CustomDeckControlEntity.java","CustomGraveyardEntity.java"):
   code=java(name)
   for token in ("implements BoxMaterial", "BoxMaterial.safe(value)",
                 "private String caszualMaterial=BoxMaterial.DEFAULT",
                 "getRenderData(){return caszualMaterial;}",
                 'out.putString("CaszualMaterial",caszualMaterial)',
                 'in.getStringOr("CaszualMaterial",BoxMaterial.DEFAULT)',
                 'result.putString("CaszualMaterial",caszualMaterial)',
                 "ClientboundBlockEntityDataPacket.create(this)",
                 "level.sendBlockUpdated(worldPosition,state,state,Block.UPDATE_ALL)"):
    self.assertIn(token,code,name+" "+token)
  mix=json.loads((ROOT/"src/main/resources/caszual_mtg.mixins.json").read_text())
  self.assertNotIn("DeckControlMaterialMixin",mix["mixins"])
  self.assertNotIn("GraveyardMaterialMixin",mix["mixins"])
  helper=java("CustomGameDeviceMaterial.java")
  self.assertIn("instanceof BoxMaterial material",helper)
  self.assertIn("material.companion$material(next)",helper)
  self.assertIn("if(!player.getAbilities().instabuild)held.shrink(1)",helper)

 def test_graveyard_lid_stays_open_and_can_be_closed_manually(self):
  ent=java("CustomGraveyardEntity.java")
  block=java("CustomGraveyard.java")
  self.assertIn("public void onViewerClose()",ent)
  self.assertIn("super.onViewerClose()",ent)
  self.assertIn("state.setValue(CustomGraveyard.OPEN,true)",ent)
  self.assertIn("level.setBlock(worldPosition,",ent)
  self.assertIn("player.isShiftKeyDown()",block)
  self.assertIn("state.setValue(OPEN,!open)",block)
  self.assertIn("player.openMenu(menu)",block)

 def test_graveyard_has_real_reskinnable_3d_surfaces_not_just_two_faces(self):
  for suffix in ("closed","open"):
   path=ASSETS/"models/block"/f"custom_graveyard_{suffix}.json"
   data=json.loads(path.read_text())
   self.assertEqual(data["textures"]["wood"],"minecraft:block/oak_planks")
   self.assertEqual(data["textures"]["0"],"mtgcard:block/graveyard_outer")
   self.assertEqual(len(data["elements"]),27)
   allfaces=[f.get("texture") for item in data["elements"] for f in item.get("faces",{}).values()]
   wood=allfaces.count("#wood")
   metal=allfaces.count("#0")
   self.assertGreaterEqual(wood,50)
   self.assertGreaterEqual(metal,40)

 def test_skinning_targets_renderable_placeholder_at_runtime(self):
  models=java("CustomBoxModels.java")
  self.assertIn("getBlockEntityRenderData(pos)",models)
  self.assertIn("new DeviceWorldModel(model)",models)
  self.assertIn("new DeviceItemModel(model)",models)
  self.assertIn("remap(q,skin,CHAIR_SOURCE)",models)
  deck=json.loads((ASSETS/"models/block/custom_deck_control.json").read_text())
  self.assertEqual(deck["textures"]["stone"],"minecraft:block/oak_planks")

if __name__=="__main__":unittest.main()
