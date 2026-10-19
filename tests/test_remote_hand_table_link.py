"""Remote Card Hand links must work up to 70 blocks without chunk loading/scans."""
import unittest
from pathlib import Path

SRC=Path(__file__).resolve().parents[1]/"src/main/java/dev/casz/caszualmtg"
def source(name):return (SRC/name).read_text(encoding="utf-8")

class RemoteTableLinks(unittest.TestCase):
 def test_table_range_separate_from_deck_and_life(self):
  logic=source("HandLogic.java")
  hand_links=source("HandLinks.java")
  self.assertIn("public static final int TABLE_RANGE=70;",hand_links)
  self.assertIn("hand.distSqr(table)<=TABLE_RANGE*TABLE_RANGE",hand_links)
  self.assertIn("private static final int LINK_RANGE=8;",logic)
  self.assertIn('if(!inRange(handPos,controlPos))',logic)
  self.assertIn('if(!inRange(handPos,lifePos))',logic)
  self.assertIn('if(!inTableRange(handPos,tablePos))',logic)
  self.assertIn("within 70 blocks",logic)
  self.assertIn("table.linkedHand(handPos);",logic)
  self.assertIn("hand.linkedTable(tablePos);",logic)
  self.assertIn("clearTableReverse(player,hand)",logic)

 def test_reverse_link_persists_across_save_and_unload(self):
  seat=source("TabletopBlockEntity.java")
  hand=source("HandBlockEntity.java")
  self.assertIn('out.putString("LinkedHand",HandBlockEntity.pos(linkedHand))',seat)
  self.assertIn('HandBlockEntity.parsePos(in.getStringOr("LinkedHand",""))',seat)
  self.assertIn('out.putString("LinkedTable",pos(linkedTable))',hand)
  self.assertIn('parsePos(in.getStringOr("LinkedTable",""))',hand)
  helper=source("HandLinks.java")
  self.assertIn("world.hasChunkAt(handPos)",helper)
  self.assertIn("at.equals(hand.linkedTable())",helper)
  self.assertIn("owner.equals(hand.owner())",helper)
  self.assertIn("LEGACY_RANGE=8",helper)
  self.assertNotIn("LEGACY_RANGE=70",helper)

 def test_golem_combat_and_player_table_share_hand(self):
  table=source("TabletopLogic.java")
  golem=source("CommanderGolems.java")
  combat=source("CommanderCombat.java")
  self.assertIn("HandLinks.linked((ServerLevel)player.level(),seat,owner)",table)
  self.assertIn("HandLinks.linked(world,table,golem.getUUID())",golem)
  self.assertIn("HandLinks.linked(level,seat,seat.seatOwner())",combat)
  self.assertIn("BlockPos precise=seat.linkedHand()",golem)
  self.assertIn("Link the Hand to this table",golem)
  self.assertIn("hand.linkedTable()",table)
  self.assertIn("hand.getBlockPos().equals(table.linkedHand())",table)

 def test_relink_and_primary_recheck_distance(self):
  logic=source("HandLogic.java")
  self.assertIn('inTableRange(hand.getBlockPos(),at)',logic)
  self.assertIn('inTableRange(handPos,golem.blockPosition())',logic)
  self.assertIn('table.linkedHand(null)',logic)
  self.assertIn('table.linkedHand(handPos)',logic)

if __name__=="__main__":unittest.main()
