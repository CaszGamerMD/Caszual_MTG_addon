"""Safety/integration checks for autonomous URL import -> build -> shop."""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/"src/main/java/dev/casz/caszualmtg"


class AutonomousBuilderTests(unittest.TestCase):
 def read(self,name):
  return (SRC/name).read_text(encoding="utf-8")

 def test_import_is_owned_by_block_not_player_session(self):
  auto=self.read("AutoDeckBuilder.java")
  builder=self.read("BuilderBlock.java")
  server=self.read("ServerLogic.java")
  self.assertIn("public static void tick(ServerLevel level,BuilderBlockEntity be)",auto)
  self.assertIn("AutoDeckBuilder.tick((ServerLevel)world,builder)",builder)
  self.assertIn("AutoDeckBuilder.start(be,p.getUUID(),address,flags)",server)
  self.assertIn("ArchidektImport.fetch(url)",auto)
  # The async URL callbacks must check the block+generation and run on server.
  self.assertIn("level.getServer().execute(()->{",auto)
  self.assertIn("current(level,be,token)",auto)
  method=server.split("static void importArchidekt(",1)[1].split("static void resolveLands(",1)[0]
  self.assertNotIn("ArchidektImport.fetch",method)
  self.assertNotIn("whenComplete",method)

 def test_progress_persists_across_gui_close_logout_restart(self):
  be=self.read("BuilderBlockEntity.java")
  for key in ('"AutoStage"','"AutoMissing"','"AutoOwner"','"Decklist"','"Url"','"Rows"'):
   self.assertIn(key,be)
  self.assertIn("if(autoActive())resolving=true;",be)
  self.assertIn("autoInFlight=false;autoRetryAt=0;",be)
  self.assertIn("autoStage=\"idle\";autoMissing=\"\";autoOwner=null;",be)
  auto=self.read("AutoDeckBuilder.java")
  for stage in ('"fetch"','"scan"','"fill"','"shop"','"wait_box"','"wait_store"','"wait_shop_box"'):
   self.assertIn(stage,auto)
  self.assertNotIn("ServerPlayer",auto)
  self.assertNotIn("containerMenu",auto)

 def test_scan_before_fill_and_exact_card_counts(self):
  auto=self.read("AutoDeckBuilder.java")
  self.assertIn('be.autoScan(token,status,String.join("\\n",summary));',auto)
  self.assertIn("be.autoFilled(token,statuses,missing,added,target.name(),target.slotted());",auto)
  self.assertIn("boolean[] accounted=new boolean[items.size()]",auto)
  self.assertIn("!insertions.containsKey(i)",auto)
  self.assertIn("if(found.kind()==2)",auto)
  self.assertIn("DeckboxTransfer.save(level.getServer(),target.portable(),target.contents())",auto)
  self.assertIn("consumed.forEach(bank::take)",auto)
  self.assertIn("CardNbt.isCommanderLegal",auto)
  self.assertIn("DeckboxBlockEntity.SECOND_SIDE_SLOT",auto)

 def test_box_priority_and_safe_card_store_transfer(self):
  auto=self.read("AutoDeckBuilder.java")
  self.assertIn("if(!be.getItem(0).isEmpty())",auto)
  self.assertIn("instanceof DeckboxBlockEntity placed",auto)
  self.assertIn("if(!inserted.isEmpty()&&!((CardStoreBoxAccess)store).caszual$getDeckbox().isEmpty())",auto)
  self.assertIn("be.autoStage(token,\"wait_shop_box\"",auto)
  self.assertIn("destination.setSavedCart(be.autoOwner(),cart)",auto)
  self.assertIn("destination.setSelectedGame(be.autoOwner(),TcgGameRegistry.MTG)",auto)
  self.assertIn("be.setItem(0,ItemStack.EMPTY)",auto)
  self.assertIn("boolean moved=false;",auto)
  self.assertIn("CardStoreBoxAccess",auto)
  self.assertIn('if(missing.isEmpty()&&be.getItem(0).isEmpty())',auto)
  self.assertIn('if(missing.isEmpty()){\n   // Still hand a finished slotted deckbox to the shop',auto)
  self.assertNotIn("openMenu(",auto)
  self.assertNotIn("sendConfirm",auto)

 def test_shop_owns_remaining_after_available_fill(self):
  auto=self.read("AutoDeckBuilder.java")
  be=self.read("BuilderBlockEntity.java")
  self.assertIn("missing.add(new DeckList.Line",auto)
  self.assertIn("be.autoMissing()",auto)
  self.assertIn("futures.stream().map(f->f.getNow(null)).filter(Objects::nonNull)",auto)
  self.assertIn("autoMissing=missing.stream()",be)
  self.assertIn('autoStage=missing.isEmpty()&&!transferSlotted?"done":"shop"',be)


if __name__=="__main__":unittest.main()
