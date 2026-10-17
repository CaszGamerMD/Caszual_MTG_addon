"""Exiting the MTG tabletop must remove all counters without altering identity or failed moves."""
from pathlib import Path
import unittest

BASE=Path(__file__).resolve().parents[1]/"src/main/java/dev/casz/caszualmtg"

def java(name):
 return (BASE/name).read_text(encoding="utf-8")

class BattlefieldCounterExitTests(unittest.TestCase):
 def test_counter_sanitizer_preserves_other_card_metadata(self):
  code=java("TabletopCounters.java")
  for token in ('source.copy()', 'DataComponents.CUSTOM_DATA', 'component.copyTag()',
                'root.getCompound("mtg_meta")', 'meta.remove("counters")',
                'meta.remove("counter_icons")', 'root.put("mtg_meta",meta)',
                'CustomData.of(root)', 'return result;'):
   self.assertIn(token,code)
  self.assertNotIn('source.set(',code)

 def test_every_successful_field_to_zone_transfer_sanitizes(self):
  logic=java("TabletopLogic.java")
  quick=logic.split('case "quick_send" -> {',1)[1].split('case "token_store" ->',1)[0]
  self.assertIn('TabletopCounters.leavingBattlefield(card)',quick)
  self.assertIn('box.setStack(DeckboxBlockEntity.SECOND_SIDE_SLOT,TabletopCounters.leavingBattlefield(card))',quick)
  self.assertIn('c.grave.setStack(slot,TabletopCounters.leavingBattlefield(card))',quick)
  self.assertIn('c.seat.addToken(TabletopCounters.leavingBattlefield(card))',quick)
  store=logic.split('case "token_store" -> {',1)[1].split('case "pass_turn" ->',1)[0]
  self.assertIn('c.seat.addToken(TabletopCounters.leavingBattlefield(found.card.stack()))',store)
  home=logic.split('case "commander_home" -> {',1)[1].split('case "put_hand" ->',1)[0]
  self.assertIn('TabletopCounters.leavingBattlefield(found.card.stack())',home)
  hand=logic.split('case "return" -> {',1)[1].split('case "grave", "exile" ->',1)[0]
  self.assertIn('c.hand.addCard(TabletopCounters.leavingBattlefield(found.card.stack()))',hand)
  grave=logic.split('case "grave", "exile" -> {',1)[1].split('case "zone_to_hand" ->',1)[0]
  self.assertIn('c.grave.setStack(slot,TabletopCounters.leavingBattlefield(found.card.stack()))',grave)

 def test_reset_and_table_break_strip_counters_from_real_cards(self):
  logic=java("TabletopLogic.java")
  reset=logic.split('private static String reset(',1)[1].split('public static void refreshColor(',1)[0]
  self.assertIn('commanderReturn=TabletopCounters.leavingBattlefield(card)',reset)
  self.assertIn('returning.add(TabletopCounters.leavingBattlefield(card))',reset)
  self.assertIn('if(entry.card.id().startsWith("copy:"))continue',reset)
  tile=java("TabletopBlockEntity.java")
  self.assertIn('out.add(TabletopCounters.leavingBattlefield(c.stack()))',tile)
  self.assertIn('if(!c.id().startsWith("copy:"))',tile)

 def test_moves_and_failed_transfers_keep_existing_counters(self):
  logic=java("TabletopLogic.java")
  move=logic.split('case "move" -> {',1)[1].split('case "untap_all" ->',1)[0]
  self.assertNotIn('TabletopCounters.leavingBattlefield(',move)
  self.assertIn('var updated=found.card.moved(req.x(),req.y())',move)
  quick=logic.split('case "quick_send" -> {',1)[1].split('case "token_store" ->',1)[0]
  self.assertLess(quick.index('if(slot<0)'),quick.index('c.grave.setStack(slot,TabletopCounters.leavingBattlefield(card))'))
  self.assertLess(quick.index('if(box==null)'),quick.index('box.setStack(DeckboxBlockEntity.SECOND_SIDE_SLOT,TabletopCounters.leavingBattlefield(card))'))

 def test_scry_cancel_can_work_without_card_hand_and_does_not_change_library(self):
  code=java("TabletopLogic.java")
  self.assertIn('"scry_cancel").contains(req.action())',code)
  self.assertIn('case "scry_cancel" -> {SCRIES.remove(player.getUUID());message="Scry cancelled; library order unchanged.";}',code)
  ui=java("TabletopScreen.java")
  self.assertIn('button("Cancel",width-97,by,84,()->action("scry_cancel",0))',ui)

if __name__=="__main__":
 unittest.main()
