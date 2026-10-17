"""Tabletop P/T overlays, card counter edit ownership and persistent token tray."""
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
JAVA=ROOT/"src/main/java/dev/casz/caszualmtg"
def code(name):return (JAVA/name).read_text(encoding="utf-8")

class TabletopTokensAndCounters(unittest.TestCase):
 def test_power_toughness_includes_face_and_modifiers(self):
  stats=code("TabletopCardStats.java")
  screen=code("TabletopScreen.java")
  for token in ('meta.power()','meta.toughness()','meta.typeLine()','"card_faces"','"creature"',
                'counts.getOrDefault("+1/+1",0)-counts.getOrDefault("-1/-1",0)'):
   self.assertIn(token,stats)
  self.assertIn("TabletopCardStats.powerToughness(card.stack())",screen)
  self.assertIn("font.width(pt)+12",screen)
  self.assertIn("left+bw-labelW",screen)
  self.assertIn("card.tapped()?h:w",screen)

 def test_counter_mutation_requires_ownership(self):
  logic=code("TabletopLogic.java")
  screen=code("TabletopScreen.java")
  self.assertIn('case "counter_set"',logic)
  self.assertIn("if(!owned(player,found)||found.card.faceDown())",logic)
  self.assertIn("CardCounterNbt.setCounter(modified,key,req.amount())",logic)
  self.assertIn("found.tile.replace(new TabletopBlockEntity.PlayedCard(",logic)
  self.assertIn('event.button()==1',screen)
  self.assertIn("TabletopCardStats.counters(card.stack())",screen)
  self.assertIn("setCounter(false)",screen)
  self.assertIn("setCounter(true)",screen)

 def test_token_tray_persists_and_duplicates_are_templates(self):
  tile=code("TabletopBlockEntity.java")
  logic=code("TabletopLogic.java")
  for token in ('MAX_TOKEN_TEMPLATES=32','out.store("TokenTray",ItemStack.CODEC.listOf(),tokenTray)',
                'in.read("TokenTray",ItemStack.CODEC.listOf())',
                "List<ItemStack> tokenTray()","Banks.key(1,original)"):
   self.assertIn(token,tile)
  for token in ('case "token_query"','case "token_add"','case "token_play"','case "token_store"',
                'case "token_remove"','TOKEN_PAGE_SIZE=8','Catalogue.search(1,name,0,page/5)',
                'new TabletopBlockEntity.PlayedCard("token:"+UUID.randomUUID()'):
   self.assertIn(token,logic)
  self.assertIn("ItemStack template=c.seat.tokenAt(req.amount())",logic)
  self.assertIn("Catalogue.isToken(com.spider.mtgcard.util.TcgCardMeta.read(card).typeLine())",logic)

 def test_network_and_interface_support_catalogue(self):
  wire=code("TabletopWire.java")
  gui=code("TabletopScreen.java")
  self.assertIn("List<ItemStack> tray,List<TokenResult> tokenResults,int tokenPage,boolean tokenMore",wire)
  self.assertIn('n>32)throw new IllegalArgumentException("Token tray too large")',wire)
  self.assertIn('n>12)throw new IllegalArgumentException("Token search page too large")',wire)
  for token in ('"Tokens ▴":"Tokens ▾"','"Search"','"Add selected"','"Play selected"',
                'new Drag("token"','case "token" -> send("token_play"'):
   self.assertIn(token,gui)

if __name__=="__main__":unittest.main()
