"""Verify rack UI hover tooltips and Card Store progress reporting."""
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
JAVA=ROOT/"src/main/java/dev/casz/caszualmtg"

class RackAndCardStorePolish(unittest.TestCase):
 def code(self,name):return (JAVA/name).read_text(encoding="utf-8")

 def test_deckbox_rack_hover_tooltips(self):
  screen=self.code("DeckboxRackScreen.java")
  self.assertIn("renderTooltip(g,mx,my)",screen)
  self.assertIn("hoveredSlot",screen)
  self.assertIn("Deckbox slot",screen)

 def test_direct_purchase_tracking_is_server_authoritative(self):
  mixin=self.code("mixin/CardStoreBoxMixin.java")
  self.assertIn('method="beginPrinting"',mixin)
  self.assertIn('method="tryDeliverOne"',mixin)
  self.assertIn('method="stopDelivering"',mixin)
  self.assertIn("caszual$inserted=Math.min",mixin)
  self.assertIn("caszual$overflow=Math.min",mixin)
  self.assertIn("elapsed<=60",mixin)
  self.assertIn("menu.blockPos.equals(pos)",mixin)
  self.assertIn("ci.cancel();return;",mixin)

 def test_progress_messages_and_registration(self):
  code=self.code("CardStoreDeckboxLayout.java")
  for expected in ("Loading deckbox:","Done","Deck box full:","drawProgress","updateProgress"):
   self.assertIn(expected,code)
  wire=self.code("CardStoreStatusWire.java")
  self.assertIn("record Progress(BlockPos pos",wire)
  self.assertIn("PRINTING=1, DONE=2, FULL=3",wire)
  server=self.code("CaszualMtg.java")
  client=self.code("CaszualMtgClient.java")
  self.assertIn("PayloadTypeRegistry.clientboundPlay().register(CardStoreStatusWire.Progress.TYPE",server)
  self.assertIn("ClientPlayNetworking.registerGlobalReceiver(CardStoreStatusWire.Progress.TYPE",client)
  self.assertIn("CardStoreDeckboxLayout.drawProgress(store,gg,mc.font)",client)

if __name__=="__main__":unittest.main()
