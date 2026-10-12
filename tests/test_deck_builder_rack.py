"""Static safety checks for the Deck Builder, rack and Card Store integration."""
import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
JAVA=ROOT/"src/main/java/dev/casz/caszualmtg"
ASSETS=ROOT/"src/main/resources/assets/caszual_mtg"
DATA=ROOT/"src/main/resources/data/caszual_mtg"

class DeckBuilderAndRack(unittest.TestCase):
 def test_builder_menu_and_persistence(self):
  source=(JAVA/"BuilderBlockEntity.java").read_text()
  self.assertIn('out.putString("Decklist",deck)',source)
  self.assertIn('out.putString("Url",url)',source)
  self.assertIn('out.putBoolean("Resolving",resolving)',source)
  self.assertIn('public long reset()',source)
  self.assertIn('System.currentTimeMillis()-cachedAt<6*60*60*1000L',source)
  self.assertIn('class BuilderMenu extends AbstractContainerMenu',(JAVA/"BuilderMenu.java").read_text())
  self.assertIn('DeckboxTransfer.save(p,be.getItem(0),loaded)',(JAVA/"ServerLogic.java").read_text())

 def test_rack_five_slots_and_actual_models(self):
  source=(JAVA/"DeckboxRackEntity.java").read_text()
  self.assertIn("SIZE=5",source)
  self.assertIn('DataComponents.CONTAINER',(JAVA/"DeckboxRackBlock.java").read_text())
  self.assertIn("ItemStackRenderState[] boxes",(JAVA/"DeckboxRackRenderer.java").read_text())
  states=json.loads((ASSETS/"blockstates/deckbox_rack.json").read_text())
  self.assertEqual(len(states["multipart"]),8,"4 facings by 2 wall/floor mount states")
  for part in states["multipart"]:
   self.assertIn("facing",part["when"])
   self.assertIn("wall",part["when"])
   path=ASSETS/"models"/(part["apply"]["model"].split(":",1)[1]+".json")
   self.assertTrue(path.is_file(),path)
  item=json.loads((ASSETS/"items/deckbox_rack.json").read_text())
  self.assertEqual(item["model"]["model"],"caszual_mtg:item/deckbox_rack")
  recipe=json.loads((DATA/"recipe/deckbox_rack.json").read_text())
  self.assertEqual(recipe["result"]["id"],"caszual_mtg:deckbox_rack")

 def test_card_store_slot_and_purchase_route(self):
  mixin=json.loads((ROOT/"src/main/resources/caszual_mtg.mixins.json").read_text())
  for name in ["MenuSlotInvoker","CardStoreBoxMixin","CardStoreBoxSlotMixin"]:
   self.assertIn(name,mixin["mixins"])
  server=(JAVA/"mixin/CardStoreBoxMixin.java").read_text()
  self.assertIn("DeckboxTransfer.load(level.getServer(),caszual$deckbox)",server)
  self.assertIn("CardStoreDeckbox",server)
  self.assertIn("ci.cancel()",server)
  menu=(JAVA/"mixin/CardStoreBoxSlotMixin.java").read_text()
  self.assertIn("DeckboxBlockItem",menu)

if __name__=="__main__":unittest.main()
