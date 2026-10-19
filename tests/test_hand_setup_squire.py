"""Regression coverage for explicit Card Hand device links and voxel squire visual."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JAVA = ROOT / "src/main/java/dev/casz/caszualmtg"
ASSETS = ROOT / "src/main/resources/assets/caszual_mtg"

def read(path): return (JAVA / path).read_text(encoding="utf-8")

class CardHandSetup(unittest.TestCase):
    def test_new_hand_has_manager_but_no_automatic_primary(self):
        hand = read("HandBlockEntity.java")
        self.assertIn("if(manager==null){manager=player.getUUID()",hand)
        self.assertNotIn("if(owner==null){owner=player.getUUID()",hand)
        self.assertIn("private BlockPos linkedTable;",hand)
        self.assertIn("private UUID manager;",hand)
        self.assertIn("assignPrimary(UUID id,String name)",hand)
        self.assertIn("out.putString(\"Manager\",manager.toString())",hand)
        self.assertIn('out.putString("LinkedTable",pos(linkedTable))',hand)
        self.assertIn('parsePos(in.getStringOr("LinkedTable",""))',hand)
        self.assertIn("legacyTableDiscovery",hand)

    def test_link_menu_and_server_authority(self):
        logic = read("HandLogic.java")
        hand_screen = read("HandScreen.java")
        wire = read("HandWire.java")
        entry = read("CaszualMtg.java")
        for action in ["link_all","link_table","link_life","primary_player",
                       "primary_golem","unlink_all","cancel_link","primary_clear"]:
            self.assertIn(action,logic)
        for label in ["Link Deck Control","Link Life Point","Link MTG Table",
                      "Set Primary Player","Select Golem"]:
            self.assertIn(label,hand_screen)
        for validator in ["hand.canManage(player)","inRange(handPos,tablePos)",
                          "inRange(handPos,lifePos)","inRange(handPos,controlPos)",
                          "golem.entityTags().contains(CommanderGolems.TAG)"]:
            self.assertIn(validator,logic)
        self.assertIn("HandLogic.completePendingTableLink(sp,hit.getBlockPos())",entry)
        self.assertIn("HandLogic.completePendingGolem(sp,iron)",entry)
        self.assertIn("String tableLink,String primaryName",wire)
        self.assertIn("p.tableLink",wire)
        self.assertIn("p.primaryName",wire)
        self.assertIn("hand.linkedTable()==null?",logic)

    def test_no_bot_autoclaim_or_device_stealing(self):
        bot=read("CommanderGolems.java")
        self.assertNotIn("hand.claimBot(",bot)
        self.assertNotIn("hand.linkedControl(control.getBlockPos())",bot)
        self.assertNotIn("hand.linkedLife(life.getBlockPos())",bot)
        self.assertIn("golem.getUUID().equals(h.owner())",bot)
        self.assertIn("at.equals(h.linkedTable())",bot)
        self.assertIn("hand.linkedControl()",bot)

    def test_voxel_model_and_world_proxy(self):
        item=json.loads((ASSETS/"models/item/commander_golem.json").read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(item["elements"]),30)
        self.assertIn("fixed",item["display"])
        self.assertIn("minecraft:block/copper_block",item["textures"].values())
        self.assertIn("minecraft:block/emerald_block",item["textures"].values())
        self.assertIn("minecraft:block/iron_block",item["textures"].values())
        for part in item["elements"]:
            self.assertEqual(3,len(part["from"]))
            self.assertEqual(3,len(part["to"]))
            for face in part["faces"].values():
                self.assertIn(face["texture"][1:],item["textures"])
        visuals=read("CommanderGolemVisuals.java")
        self.assertIn("Display.ItemDisplay",visuals)
        self.assertIn("setItemTransform(ItemDisplayContext.FIXED)",visuals)
        self.assertIn("setItemStack(new ItemStack(CaszualMtg.COMMANDER_GOLEM))",visuals)
        self.assertIn("world.addFreshEntity(display)",visuals)
        self.assertIn("display.setPos(golem.getX()",visuals)
        self.assertIn("d.discard()",visuals)
        self.assertIn("CommanderGolemVisuals.ensure(world,golem)",read("CommanderGolems.java"))

if __name__=="__main__":
    unittest.main()
