"""Shift-right-click battlefield routing must be owner-safe and lossless."""
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
JAVA=ROOT/"src/main/java/dev/casz/caszualmtg"

class QuickSendTests(unittest.TestCase):
 def test_shift_right_click_shortcut_precedes_counter_editor(self):
  gui=(JAVA/"TabletopScreen.java").read_text(encoding="utf-8")
  start=gui.index("if(event.button()==1){")
  click=gui[start:gui.index("if(own(c)&&event.button()==0)",start)]
  self.assertIn("GLFW.GLFW_KEY_LEFT_SHIFT",click)
  self.assertIn("GLFW.GLFW_KEY_RIGHT_SHIFT",click)
  self.assertLess(click.index('send("quick_send",c.id(),data.seat(),0,0,0)'),click.index("counterCard=c.id()"))
  self.assertIn("if(own(c))send(",click)
  self.assertIn("else if(own(c)&&!c.hidden())",click)
  self.assertIn("return true;",click)

 def test_server_rejects_other_players_and_routes_commander_first(self):
  logic=(JAVA/"TabletopLogic.java").read_text(encoding="utf-8")
  start=logic.index('case "quick_send" -> {')
  end=logic.index('case "token_store" -> {',start)
  action=logic[start:end]
  self.assertIn("if(!owned(player,found))",action)
  self.assertIn('found.card.id().startsWith("commander:")',action)
  self.assertIn("sameCommander(card,c.seat.commanderReference())",action)
  self.assertLess(action.index("if(commander){"),action.index("}else if(Catalogue.isToken("))
  self.assertLess(action.index("}else if(Catalogue.isToken("),action.index("}else{"))
  self.assertIn('"quick_send","copy_token","scry_cancel").contains(req.action())',logic)

 def test_server_preflights_each_destination_before_removing_card(self):
  logic=(JAVA/"TabletopLogic.java").read_text(encoding="utf-8")
  action=logic.split('case "quick_send" -> {',1)[1].split('case "token_store" -> {',1)[0]
  commander=action.split("if(commander){",1)[1].split("}else if(Catalogue.isToken",1)[0]
  token=action.split("}else if(Catalogue.isToken",1)[1].split("}else{",1)[0]
  grave=action.split("}else{",1)[1]
  self.assertIn("if(box==null)",commander)
  self.assertIn("SECOND_SIDE_SLOT).isEmpty()",commander)
  self.assertLess(commander.index("box.setStack("),commander.index("found.tile.remove("))
  self.assertIn("if(!c.seat.addToken(TabletopCounters.leavingBattlefield(card)))",token)
  self.assertLess(token.index("if(!c.seat.addToken(TabletopCounters.leavingBattlefield(card)))"),token.index("found.tile.remove("))
  self.assertIn("int slot=emptySlot(c.grave,0)",grave)
  self.assertIn("if(slot<0)",grave)
  self.assertLess(grave.index("c.grave.setStack("),grave.index("found.tile.remove("))

if __name__=="__main__":unittest.main()
