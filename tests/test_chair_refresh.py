"""Regression checks for immediate material and playmat-color chair updates."""
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
JAVA=ROOT/"src/main/java/dev/casz/caszualmtg"

def read(name):
 return (JAVA/name).read_text(encoding="utf-8")

class ChairRefreshTests(unittest.TestCase):
 def test_server_sends_model_refresh_for_both_mutations(self):
  chair=read("ChairBlockEntity.java")
  for method in ("public void material(String source)", "public void paperRgb(int rgb)"):
   self.assertIn(method,chair)
  self.assertEqual(chair.count("refreshAppearance();"),2)
  self.assertIn("level instanceof ServerLevel server",chair)
  self.assertIn("level.sendBlockUpdated(worldPosition,state,state,Block.UPDATE_ALL)",chair)
  self.assertIn("DeckboxRefreshWire.broadcast(server,worldPosition)",chair)
  # Never flood nearby clients for updates that don't actually change appearance.
  self.assertIn("if(next.equals(material))return",chair)
  self.assertIn("if(matRgb==next)return",chair)

 def test_client_marks_block_mesh_section_dirty(self):
  wire=read("DeckboxRefreshWire.java")
  client=read("CaszualMtgClient.java")
  self.assertIn("for(ServerPlayer player:",wire)
  self.assertIn("new Refresh(pos.immutable())",wire)
  self.assertIn("ClientPlayNetworking.registerGlobalReceiver(DeckboxRefreshWire.Refresh.TYPE",client)
  self.assertIn("setSectionDirtyWithNeighbors",client)

 def test_geometry_cache_accounts_for_paper_rgb(self):
  model=read("CustomBoxModels.java")
  self.assertIn("static int chairPaperRgb(BlockAndTintGetter level,BlockPos pos)",model)
  self.assertIn("state.getValue(ChairBlock.CUSHION)==ChairBlock.Cushion.PAPER?chairPaperRgb(level,pos):-1",model)
  self.assertIn("return List.of(state,chairSkin(level,pos)",model)
  self.assertIn("new ChairWorldModel(model)",model)

 def test_chair_interactions_and_adjacent_mat_changes_trigger_refresh(self):
  block=read("ChairBlock.java")
  table=read("TabletopLogic.java")
  self.assertIn("chair.material(ChairWood.fromItem(stack))",block)
  self.assertIn("chair.paperRgb(rgb)",block)
  self.assertIn("if(next.getValue(CUSHION)==Cushion.PAPER)refreshPaperColor(level,pos)",block)
  self.assertIn("refreshNextToTable(player.level(),pos)",table)

if __name__=="__main__":unittest.main()
