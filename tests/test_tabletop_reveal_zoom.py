"""Revealed-hand table layout and persisted wheel-resized battlefield cards."""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
JAVA=ROOT/"src/main/java/dev/casz/caszualmtg"

def source(file):return (JAVA/file).read_text(encoding="utf-8")

class TableRevealZoomTests(unittest.TestCase):
 def test_revealed_hand_is_on_owner_battlefield_for_every_viewer(self):
  gui=source("TabletopScreen.java")
  logic=source("TabletopLogic.java")
  self.assertIn('for(var hand:data.shownHands())if(hand.seat().equals(view))return hand;',gui)
  self.assertNotIn('shown.seat().equals(view)&&!shown.seat().equals(data.seat())',gui)
  self.assertIn('if(isHandRevealed(t.pos()))g.fill(',gui)
  self.assertIn('TabletopWire.ShownHand publicHand=shownHand()',gui)
  self.assertIn('g.drawString(font,font.plainSubstrByWidth(label,boardW()-28)',gui)
  self.assertIn('drawArt(g,publicHand.cards().get(i),x,by,shownCardW(),shownCardH())',gui)
  self.assertIn('int at=shownCardAt(mx,my)',gui)
  self.assertIn('if(shownCardAt(x,y)>=0&&event.button()==0)return true',gui)
  self.assertIn('List<TabletopWire.ShownHand> shownHands=new ArrayList<>()',logic)
  self.assertIn('if(handOwner==null||!REVEALED_HANDS.contains(handOwner))continue;',logic)
  self.assertIn('HandBlockEntity revealed=linkedHand(player,t,handOwner);',logic)
  self.assertIn('shownHands.add(new TabletopWire.ShownHand(t.getBlockPos(),t.seatName(),revealed.visibleCards()))',logic)

 def test_all_battlefield_cards_zoom_from_per_table_saved_scale(self):
  tile=source("TabletopBlockEntity.java")
  logic=source("TabletopLogic.java")
  wire=source("TabletopWire.java")
  gui=source("TabletopScreen.java")
  for token in ('private int cardScale=100','Math.clamp(percent,45,180)',
                'out.putInt("CardScale",cardScale)',
                'in.getIntOr("CardScale",100)'):
   self.assertIn(token,tile)
  for token in ('case "card_scale" -> {','target.ownedBy(player)',
                'target.cardScale(target.cardScale()+req.amount()*5)',
                't.cardScale(),count,libraryCount,Map.copyOf(counters)))'):
   self.assertIn(token,logic)
  self.assertIn('boolean active,int cardScale',wire)
  self.assertIn('b.writeVarInt(t.cardScale)',wire)
  self.assertIn('boolean hasLife=b.readBoolean(),active=b.readBoolean();int scale=b.readVarInt()',wire)
  self.assertIn('tile.cardScale()',gui)
  self.assertIn('Math.round(base*scale/100f)',gui)
  self.assertIn('send("card_scale","",view,0,0,(int)Math.signum(dy))',gui)
  self.assertIn('if(shown!=null&&!tokenTrayOpen',gui)
  self.assertIn('if(inTokenPanel((int)mx,(int)my))',gui)
  self.assertIn('if(my>=handTop())',gui)
  self.assertIn('CARDS "+tile.cardScale()+"%"',gui)

if __name__=="__main__":unittest.main()
