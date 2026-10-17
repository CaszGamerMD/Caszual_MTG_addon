"""Tabletop free drag, confirmable hand actions, and opt-in public reveal."""
from pathlib import Path
import unittest

JAVA=Path(__file__).resolve().parents[1]/"src/main/java/dev/casz/caszualmtg"

def read(name):
 return (JAVA/name).read_text(encoding="utf-8")

class TabletopHandSafetyTests(unittest.TestCase):
 def test_grab_offset_instead_of_card_center_snap(self):
  gui=read("TabletopScreen.java")
  self.assertIn("int dx=(mx-held.startX())*1000",gui)
  self.assertIn("int dy=(my-held.startY())*1000",gui)
  self.assertIn("Math.clamp(origin.x()+dx,0,1000)",gui)
  self.assertIn("Math.clamp(origin.y()+dy,0,1000)",gui)
  self.assertNotIn('send("move",held.id(),view,x,y,0)',gui)
  self.assertIn('else send("tap",held.id(),view,0,0,0)',gui)

 def test_hand_moves_need_client_confirmation_and_server_verification(self):
  gui=read("TabletopScreen.java")
  logic=read("TabletopLogic.java")
  self.assertIn('pendingHandZone=name;pendingHandSlot=selectedZone',gui)
  self.assertIn('"CONFIRM EXILE":"CONFIRM GY"',gui)
  self.assertIn('button("Cancel",width-385',gui)
  self.assertIn('send("hand_to_zone",pendingHandZone+"|"+id',gui)
  section=logic.split('case "hand_to_zone" -> {',1)[1].split('case "copy_token" -> {',1)[0]
  for token in ('if(slot<0||slot>=c.hand.cardCount())','if(!id.equals(expected))',
                'int target=emptySlot(c.grave,start)','if(target<0)',
                'ItemStack taken=c.hand.removeVisibleIndex(slot)','c.grave.setStack(target,taken)'):
   self.assertIn(token,section)
  self.assertLess(section.index('if(target<0)'),section.index('c.hand.removeVisibleIndex(slot)'))
  self.assertLess(section.index('if(!id.equals(expected))'),section.index('c.hand.removeVisibleIndex(slot)'))

 def test_public_hand_reveal_is_server_authorized_and_scoped_to_table(self):
  gui=read("TabletopScreen.java")
  logic=read("TabletopLogic.java")
  wire=read("TabletopWire.java")
  for token in ('Set<UUID> REVEALED_HANDS','case "reveal_hand" -> {',
                'if(!c.hand.owner().equals(player.getUUID()))',
                'if(!REVEALED_HANDS.contains(handOwner))continue',
                'HandBlockEntity revealed=linkedHand(player,t,handOwner)',
                'shownHands.add(new TabletopWire.ShownHand('):
   self.assertIn(token,logic)
  self.assertIn('c.hand==null||c.seat==null?List.of():c.hand.visibleCards()',logic)
  self.assertIn('boolean ownHandRevealed,List<ShownHand> shownHands',wire)
  self.assertIn('List.copyOf(shownHands)',wire)
  self.assertIn('"Reveal Hand"',gui)
  self.assertIn('"HIDE HAND !"',gui)
  self.assertIn('if(data.ownHandRevealed())',gui)
  self.assertIn('0xFFFF2020',gui)
  self.assertIn('TabletopWire.ShownHand publicHand=shownHand()',gui)
  self.assertIn('data.shownHands()',gui)
  self.assertIn('shown.seat().equals(view)&&!shown.seat().equals(data.seat())',gui)
  self.assertIn('shownScroll=Math.clamp',gui)
  self.assertIn('data.ownHandRevealed()!=reply.ownHandRevealed()',gui)

if __name__=="__main__":unittest.main()
