"""Static invariants for the first experimental tabletop implementation."""
import json
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/"src/main/java/dev/casz/caszualmtg"
ASSETS=ROOT/"src/main/resources/assets/caszual_mtg"
DATA=ROOT/"src/main/resources/data/caszual_mtg"

class TabletopAssetsTest(unittest.TestCase):
    def source(self,name):
        return (BASE/name).read_text(encoding="utf-8")

    def test_block_item_recipe_and_loot_are_consistent(self):
        state=json.loads((ASSETS/"blockstates/tabletop.json").read_text())
        item=json.loads((ASSETS/"items/tabletop.json").read_text())
        model=json.loads((ASSETS/"models/block/tabletop.json").read_text())
        recipe=json.loads((DATA/"recipe/tabletop.json").read_text())
        loot=json.loads((DATA/"loot_table/blocks/tabletop.json").read_text())
        self.assertEqual(len([entry for entry in state["multipart"] if "felt" in entry["when"]]),16)
        self.assertEqual(len([entry for entry in state["multipart"] if "cards" in entry["when"]]),4)
        self.assertEqual(item["model"]["model"],"caszual_mtg:item/tabletop")
        self.assertTrue(any(e["faces"].get("up",{}).get("texture")=="#felt" for e in model["elements"]))
        self.assertEqual(recipe["result"]["id"],"caszual_mtg:tabletop")
        self.assertEqual(loot["pools"][0]["entries"][0]["name"],"caszual_mtg:tabletop")

    def test_registration_and_creative_tag(self):
        common=self.source("CaszualMtg.java")
        client=self.source("CaszualMtgClient.java")
        tag=json.loads((ROOT/"src/main/resources/data/caszual_additions/tags/item/caszual_content.json").read_text())
        self.assertIn('id("tabletop")',common)
        self.assertIn("e.accept(TABLETOP)",common)
        self.assertIn("TabletopWire.Request.TYPE",common)
        self.assertIn("TabletopWire.Reply.TYPE",client)
        self.assertIn("caszual_mtg:tabletop",tag["values"])

    def test_server_validates_ownership_and_card_conservation(self):
        server=self.source("TabletopLogic.java")
        entity=self.source("TabletopBlockEntity.java")
        for action in ("put_hand","put_grave","put_exile","move","tap","hide","return",
                       "grave","exile","zone_to_hand","draw","mill","shuffle","scry_begin",
                       "scry_cancel","scry_commit"):
            self.assertIn('"'+action+'"',server)
        self.assertIn("owned(player,found)",server)
        self.assertIn("card.faceDown()&&!uuid.equals(card.owner())?ItemStack.EMPTY",server)
        self.assertIn("MAX_CARDS",entity)
        self.assertIn('out.store("PlayedCards"',entity)

    def test_existing_commanders_survive_packet_roundtrips(self):
        """A commander can already be saved using 'commander:' plus a UUID."""
        wire=self.source("TabletopWire.java")
        logic=self.source("TabletopLogic.java")
        be=self.source("TabletopBlockEntity.java")
        commander_id="commander:"+"00000000-0000-0000-0000-000000000000"
        self.assertEqual(len(commander_id),46)
        self.assertIn("MAX_CARD_ID_LENGTH=64",wire)
        self.assertGreaterEqual(64,len(commander_id))
        self.assertIn("b.writeUtf(c.id,MAX_CARD_ID_LENGTH)",wire)
        self.assertIn("b.readUtf(MAX_CARD_ID_LENGTH)",wire)
        self.assertIn("id.length()>TabletopWire.MAX_CARD_ID_LENGTH",logic)
        self.assertIn('"commander:"+UUID.randomUUID()',logic)
        self.assertIn('found.card.id().startsWith("commander:")',logic)
        self.assertIn("Codec.STRING.fieldOf(\"Id\")",be)
        self.assertIn('out.store("PlayedCards"',be)

    def test_screen_has_battlefield_and_private_zone_tabs(self):
        screen=self.source("TabletopScreen.java")
        for label in ("Hand","GY","Exile","Draw","Draw 7","Scry 1","Scry 3","Mill","Mill 5",
                      "Shuffle","Pass Turn","COMMANDER","mouseReleased(MouseButtonEvent"):
            self.assertIn(label,screen)
        self.assertIn("handTop()",screen)
        self.assertIn("boardHit(mx,my)",screen)
        self.assertIn("drag=new Drag",screen)
        self.assertIn("lifeLink()",self.source("HandScreen.java"))

if __name__=="__main__":
    unittest.main()
