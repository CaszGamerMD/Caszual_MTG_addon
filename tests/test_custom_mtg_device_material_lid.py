"""Verify Caszual Graveyard & Deck Control panel reskin and persistent lid."""
from pathlib import Path
import json
import unittest

ROOT=Path(__file__).resolve().parents[1]
JAVA=ROOT/"src/main/java/dev/casz/caszualmtg"
ASSETS=ROOT/"src/main/resources/assets/caszual_mtg"

def java(name):return (JAVA/name).read_text()

class CustomMtgDevices(unittest.TestCase):
 def test_native_block_entities_survive_reload_with_materials(self):
  control=java("CustomDeckControl.java")
  grave=java("CustomGraveyard.java")
  self.assertIn("new com.spider.mtgcard.deckcontrol.DeckControlBlockEntity(pos,state)",control)
  self.assertIn("new com.spider.mtgcard.graveyard.GraveyardBlockEntity(pos,state)",grave)
  mix=json.loads((ROOT/"src/main/resources/caszual_mtg.mixins.json").read_text())
  for name in ("DeckControlMaterialMixin","GraveyardMaterialMixin","GraveyardScreenHandlerMixin"):
   self.assertIn(name,mix["mixins"])
  for name in ("mixin/DeckControlMaterialMixin.java","mixin/GraveyardMaterialMixin.java"):
   code=java(name)
   for token in ("implements BoxMaterial","BoxMaterial.safe(value)",
                 'putString("CaszualMaterial",caszual$skin)',
                 'getStringOr("CaszualMaterial",BoxMaterial.DEFAULT)',
                 "getRenderData(){return caszual$skin;}",
                 "ClientboundBlockEntityDataPacket.create((BlockEntity)(Object)this)",
                 "getDisplayName"):
    self.assertIn(token,code,name+" "+token)
  helper=java("CustomGameDeviceMaterial.java")
  self.assertIn("instanceof BoxMaterial material",helper)
  self.assertIn("material.companion$material(next)",helper)
  self.assertIn("if(!player.getAbilities().instabuild)held.shrink(1)",helper)

 def test_native_graveyard_menu_accepts_caszual_block(self):
  handler=java("mixin/GraveyardScreenHandlerMixin.java")
  self.assertIn("getBlockState(pos).is(CaszualMtg.CUSTOM_GRAVEYARD)",handler)
  self.assertIn("cir.setReturnValue(",handler)
  self.assertIn("instanceof GraveyardBlockEntity",handler)

 def test_graveyard_lid_stays_open_and_can_be_closed_manually(self):
  mixin=java("mixin/GraveyardMaterialMixin.java")
  block=java("CustomGraveyard.java")
  for token in ("caszual$lidPinned", "caszual$setLidPinned(true)",
                "caszual$setLidPinned(boolean open)",
                'output.putBoolean("CaszualLidPinned",caszual$lidPinned)',
                "onViewerOpen","onViewerClose"):
   self.assertIn(token,mixin)
  self.assertIn("player.isShiftKeyDown()",block)
  self.assertIn("lid.caszual$setLidPinned(!open)",block)
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
