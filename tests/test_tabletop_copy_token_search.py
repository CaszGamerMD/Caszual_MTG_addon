"""Battlefield-only token copies and reliable tabletop token catalogue paging."""
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
JAVA=ROOT/"src/main/java/dev/casz/caszualmtg"

def read(name):
    return (JAVA/name).read_text(encoding="utf-8")

class CopyTokenAndSearchTests(unittest.TestCase):
    def test_counter_menu_exposes_token_copy(self):
        gui=read("TabletopScreen.java")
        self.assertIn('button("Create Token Copy"',gui)
        self.assertIn('send("copy_token",counterCard,data.seat(),0,0,0)',gui)
        self.assertIn('card.id().startsWith("copy:")',gui)
        self.assertIn('"TOKEN COPY"',gui)

    def test_copies_keep_card_art_but_not_counters_and_have_separate_id(self):
        logic=read("TabletopLogic.java")
        start=logic.index('case "copy_token" -> {')
        end=logic.index('case "counter_set" ->',start)
        action=logic[start:end]
        self.assertIn("if(!owned(player,found)||found.card.faceDown())",action)
        self.assertIn("MAX_CARDS",action)
        self.assertIn("CardDatabaseCards.copyForExtraction(found.card.stack())",action)
        self.assertIn("CardCounterNbt.setCounter(copy,key,0)",action)
        self.assertIn('new TabletopBlockEntity.PlayedCard("copy:"+UUID.randomUUID()',action)
        self.assertIn("found.tile",action)

    def test_copy_ceases_instead_of_entering_any_zone(self):
        logic=read("TabletopLogic.java")
        quick=logic.split('case "quick_send" -> {',1)[1].split('case "token_store" ->',1)[0]
        hand=logic.split('case "return" -> {',1)[1].split('case "grave", "exile" ->',1)[0]
        zones=logic.split('case "grave", "exile" -> {',1)[1].split('case "zone_to_hand" ->',1)[0]
        tray=logic.split('case "token_store" -> {',1)[1].split('case "pass_turn" ->',1)[0]
        reset=logic.split('private static String reset(',1)[1]
        for area in (quick,hand,zones,tray):
            self.assertIn('found.card.id().startsWith("copy:")',area)
            self.assertIn('found.tile.remove(found.card.id())',area)
        self.assertIn('if(entry.card.id().startsWith("copy:"))continue',reset)

    def test_online_token_results_are_shown_directly_not_only_through_bank(self):
        logic=read("TabletopLogic.java")
        self.assertIn('private static final Map<UUID,TokenPage> TOKEN_RESULTS',logic)
        self.assertIn('Catalogue.search(1,name,0,page/5)',logic)
        self.assertIn('int start=(page%5)*TOKEN_PAGE_SIZE',logic)
        self.assertIn('new TabletopWire.TokenResult(Banks.key(1,token),token)',logic)
        self.assertIn('TOKEN_RESULTS.put(player.getUUID(),new TokenPage',logic)
        self.assertIn('tokenResults.addAll(loaded.cards())',logic)
        self.assertIn('tokenMore=loaded.more()',logic)
        self.assertIn('if(active!=null&&query.equals(active.query()))',logic)
        self.assertIn('for(var row:active.cards())',logic)

    def test_search_is_available_on_tray_open_with_paging_feedback(self):
        gui=read("TabletopScreen.java")
        self.assertIn('if(tokenTrayOpen)searchTokens(0)',gui)
        self.assertIn('if(data.tokenMore())',gui)
        self.assertIn('searchTokens(Math.min(50,data.tokenPage()+1))',gui)
        self.assertIn('No results yet',gui)
        self.assertIn('tokenResultScroll=Math.clamp',gui)

if __name__=="__main__":
    unittest.main()
