"""Regression coverage for Commander Golem's real MTGCard pod and deck flow."""
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/"src/main/java/dev/casz/caszualmtg"
def read(name):return (SOURCE/name).read_text(encoding="utf-8")

class PodIntegration(unittest.TestCase):
 def test_real_pod_membership_and_turn_owner(self):
  pod=read("CommanderPod.java")
  self.assertIn("LifePlayGroups.findGroupId(world,pos)",pod)
  self.assertIn("LifePlayGroups.getGroup(world,id)",pod)
  self.assertIn("g.order.indexOf(pos)",pod)
  self.assertIn("g.order.get(g.activeIndex).equals(pos)",pod)
  self.assertIn("g.started&&!g.rolling",pod)
  self.assertIn("life.isGameStarted()&&life.isTurnActive()",pod)
  self.assertIn("g.dead.contains(pos)",pod)

 def test_join_only_one_pregame_group(self):
  pod=read("CommanderPod.java")
  self.assertIn("CommanderCombat.connected(world,seat.getBlockPos())",pod)
  self.assertIn("candidates.size()!=1",pod)
  self.assertIn("if(target.started||target.rolling)",pod)
  self.assertIn("LifePlayGroups.saveGroup(world,id,target.name,newOrder)",pod)
  self.assertIn("newOrder.add(life.getBlockPos().immutable())",pod)
  gui=read("HandScreen.java")
  logic=read("HandLogic.java")
  self.assertIn('button("Connect to nearby Pod"',gui)
  self.assertIn('case "join_pod" ->',logic)
  self.assertIn("hand.canManage(player)",logic)
  self.assertIn("CommanderPod.joinNearbyPod(world,seat,lp)",logic)

 def test_physical_seven_card_hand_and_per_turn_draw(self):
  bot=read("CommanderGolems.java")
  self.assertIn("s.deck.shuffle();",bot)
  self.assertIn("drawIntoHand(s.deck,s.hand,7)",bot)
  self.assertIn("drawIntoHand(s.deck,s.hand,1)",bot)
  self.assertIn("hand.cardCount()+count>HandBlockEntity.SIZE",bot)
  self.assertIn("deck.getLibraryCount()<count",bot)
  self.assertIn("deck.takeTopCards(count)",bot)
  self.assertIn("deck.putCardsOnBottom(drawn)",bot)
  self.assertIn("golem.addTag(FIRST_HAND)",bot)
  self.assertIn("golem.addTag(ACTION_DONE)",bot)
  self.assertIn("golem.removeTag(ACTION_DONE)",bot)
  self.assertIn("if(!pod.started()||pod.rolling()||!pod.active())",bot)
  self.assertIn("CommanderPod.status(world,s.life).playable()",bot)

 def test_continues_after_commander_leaves_deckbox(self):
  bot=read("CommanderGolems.java")
  self.assertIn('if(!golem.entityTags().contains(FIRST_HAND)',bot)
  self.assertIn('&&box.getStack(DeckboxBlockEntity.SECOND_SIDE_SLOT).isEmpty())',bot)
  self.assertIn("CommanderBattleActions.castHand(golem,s.table,s.hand)",bot)
  self.assertIn("CommanderBattleActions.playLand(golem,s.table,s.hand)",bot)
  self.assertIn("CommanderBattleActions.castCommander(golem,s.table,box)",bot)
  self.assertIn("LifePlayGroups.passTurn(world,s.life.getBlockPos())",bot)

if __name__=="__main__":unittest.main()
