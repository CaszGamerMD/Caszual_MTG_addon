"""Public per-player counts, read-only zones, turn alerts and safe life controls."""
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
JAVA=ROOT/"src/main/java/dev/casz/caszualmtg"
def read(name):return (JAVA/name).read_text(encoding="utf-8")

class TabletopPublicStatus(unittest.TestCase):
 def test_public_hand_and_deck_counts_preserve_secrecy(self):
  wire=read("TabletopWire.java")
  server=read("TabletopLogic.java")
  screen=read("TabletopScreen.java")
  for name in ["int handCount","int libraryCount","Map<String,Integer> counters"]:
   self.assertIn(name,wire)
  self.assertIn("other.cardCount()",server)
  self.assertIn("seatDeck.getLibraryCount()",server)
  self.assertIn('String deckCount="DECK "',screen)
  self.assertIn('String handCount="HAND "',screen)
  self.assertIn('int hx=boardX()+boardW()-font.width(handCount)',screen)
  self.assertIn('ItemStack shown=card.faceDown()&&!uuid.equals(card.owner())?ItemStack.EMPTY',server)
  self.assertIn('REVEALED_HANDS.contains(handOwner)',server)

 def test_public_graveyard_exile_and_own_only_mutations(self):
  wire=read("TabletopWire.java")
  server=read("TabletopLogic.java")
  screen=read("TabletopScreen.java")
  self.assertIn('public record PublicZone(',wire)
  self.assertIn('List<PublicZone> publicZones',wire)
  self.assertIn('CommanderBattleActions.graveyard(',server)
  self.assertIn('new TabletopWire.PublicZone(',server)
  self.assertIn('List.copyOf(publicZones)',server)
  self.assertIn('boolean viewingOtherZone()',screen)
  self.assertIn('if(viewingOtherZone())return true;',screen)
  self.assertIn('publicZone().grave()',screen)
  self.assertIn('publicZone().exile()',screen)
  self.assertIn('PUBLIC "+zone.toUpperCase(Locale.ROOT)',screen)
  self.assertNotIn('publicZone().hand()',screen)

 def test_local_only_pass_focus_and_sound(self):
  ui=read("TabletopScreen.java")
  sound=read("TabletopTurnChime.java")
  main=read("CaszualMtg.java")
  self.assertIn('awaitingTurnPass=true;action("pass_turn",0)',ui)
  self.assertIn('reply.message().startsWith("Turn passed")',ui)
  self.assertIn('reply.tiles().stream().filter(TabletopWire.Tile::active)',ui)
  self.assertIn('new net.minecraft.network.protocol.game.ClientboundSoundPacket(',sound)
  self.assertIn('SoundEvents.NOTE_BLOCK_CHIME',sound)
  self.assertIn('if(active&&!watch.active())',sound)
  self.assertIn('CommanderPod.status(world,lp).playable()',sound)
  self.assertIn('TabletopTurnChime::tick',main)
  self.assertIn('TabletopTurnChime.clear(h.player)',main)

 def test_edit_life_counters_authorized_by_seat_and_pod(self):
  server=read("TabletopLogic.java")
  ui=read("TabletopScreen.java")
  self.assertIn('case "life_adjust", "life_set", "life_counter_adjust", "life_counter_set", "life_counter_remove"',server)
  self.assertIn('!c.seat.ownedBy(player)',server)
  self.assertIn('LifePlayGroups.findGroupId(world,ownLife.getBlockPos())',server)
  self.assertIn('LifePlayGroups.findGroupId(world,targetLife.getBlockPos())',server)
  self.assertIn('ownPod==null||!ownPod.equals(targetPod)',server)
  self.assertIn('targetLife.addLife(value)',server)
  self.assertIn('targetLife.setCounter(key,updated)',server)
  self.assertIn('targetLife.removeCounter(key)',server)
  self.assertIn('event.button()==1&&y>=5&&y<30',ui)
  self.assertIn('openLifePanel(clicked.pos())',ui)
  self.assertIn('button("Life +"',ui)
  self.assertIn('button("Set Life"',ui)

if __name__=="__main__":unittest.main()
