"""Full-table card deposits and per-authorized-player persistent shortcut controls."""
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/"src/main/java/dev/casz/caszualmtg"
def read(n):return (SRC/n).read_text(encoding="utf-8")
class HandHotkeysAndDeposit(unittest.TestCase):
 def test_right_click_hand_deposits_only_tcg_cards(self):
  screen=read("TabletopScreen.java")
  logic=read("TabletopLogic.java")
  hand=read("HandLogic.java")
  self.assertIn('event.button()==1&&x>=12&&x<70&&y>=handTop()+5',screen)
  self.assertIn('send("hand_absorb_inventory"',screen)
  self.assertIn('case "hand_absorb_inventory" -> {',logic)
  self.assertIn('HandLogic.depositIntoHand(player,c.hand)',logic)
  self.assertIn('if(!hand.isAuthorized(player))',hand)
  self.assertIn('stack.is(com.spider.mtgcard.item.ModItemTags.TCG_CARD)',hand)
  self.assertIn('stack.shrink(1)',hand)
  self.assertIn('player.inventoryMenu.broadcastChanges()',hand)
 def test_per_player_hotkeys_persist_and_are_authorized(self):
  entity=read("HandBlockEntity.java")
  server=read("HandLogic.java")
  wire=read("HandWire.java")
  self.assertIn('Map<UUID,Map<String,Integer>> hotkeys',entity)
  self.assertIn('out.store("HotkeyBindings",Bind.CODEC.listOf(),savedKeys)',entity)
  self.assertIn('in.read("HotkeyBindings",Bind.CODEC.listOf())',entity)
  self.assertIn('case "hotkey_set" -> {',server)
  self.assertIn('hand.isAuthorized(player)',server)
  self.assertIn('hand.hotkey(player.getUUID()',server)
  self.assertIn('hand.hotkeys(player.getUUID())',server)
  self.assertIn('Map<String,Integer> hotkeys',wire)
 def test_only_table_screen_fires_hotkeys(self):
  server=read("TabletopLogic.java")
  wire=read("TabletopWire.java")
  ui=read("TabletopScreen.java")
  hand=read("HandScreen.java")
  client=read("CaszualMtgClient.java")
  self.assertIn('HandHotkeys.ACTIONS',ui)
  self.assertIn('data.hotkeys()',ui)
  self.assertIn('getFocused() instanceof EditBox',ui)
  self.assertIn('case "draw" -> {',server)
  self.assertIn('Map.copyOf(hotkeys)',wire)
  self.assertIn('c.hand.hotkeys(player.getUUID())',server)
  self.assertIn('boolean handleHotkey(int key)',hand)
  self.assertIn('button("Table Hotkeys"',hand)
  self.assertIn('button(label(chosen)+" : "+keyLabel(key)',hand)
  self.assertIn('hotkey_set',hand)
  self.assertIn('ScreenKeyboardEvents.allowKeyPress(screen)',client)
  self.assertIn('instanceof TabletopScreen table',client)
  self.assertIn('instanceof HandScreen hand',client)

if __name__=="__main__":unittest.main()
