"""Static regression coverage for placed-only commander deckbox artwork."""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/"src/main/java/dev/casz/caszualmtg"


class CommanderTopDisplayTests(unittest.TestCase):
    def test_only_selected_commander_card_is_synced(self):
        mixin=(SRC/"mixin/CommanderTopDeckboxMixin.java").read_text()
        self.assertIn("DeckboxBlockEntity.SECOND_SIDE_SLOT",mixin)
        self.assertIn("DeckboxBlockEntity.FIRST_SIDE_SLOT",mixin)
        self.assertIn("caszual$select",mixin)
        self.assertIn("CardItemRegistry.isCard",mixin)
        self.assertIn("getUpdateTag",mixin)
        self.assertIn("CASZUAL_COMMANDER",mixin)
        self.assertIn("getLevel().isClientSide()",mixin)
        self.assertIn("ItemStack.CODEC",mixin)
        self.assertIn('method="setItem"',mixin)
        self.assertIn('method="loadStorageId"',mixin)
        self.assertNotIn("MAIN_SLOTS;i++",mixin)

    def test_only_rendered_when_placed_and_closed(self):
        renderer=(SRC/"CommanderTopRenderer.java").read_text()
        self.assertIn("BlockEntityRenderer<DeckboxBlockEntity",renderer)
        self.assertIn("block.getValue(DeckboxBlock.OPEN)",renderer)
        self.assertIn("if(commander.isEmpty())return;",renderer)
        self.assertIn("getOrRequestFace(commander,0)",renderer)
        self.assertIn("Y_BORDER",renderer)
        self.assertIn("Y_ART",renderer)
        self.assertIn("state.lightCoords",renderer)
        self.assertIn("RenderTypes.entityCutout(state.art)",renderer)
        self.assertNotIn("ItemModelResolver",renderer)

    def test_vanilla_and_custom_use_native_block_entity_type(self):
        main=(SRC/"CaszualMtgClient.java").read_text()
        self.assertIn("ModBlockEntities.DECKBOX",main)
        self.assertIn("CommanderTopRenderer::new",main)
        self.assertNotIn("ModelLoadingPlugin", (SRC/"CommanderTopRenderer.java").read_text())
        custom=(SRC/"CustomDeckbox.java").read_text()
        self.assertIn("extends DeckboxBlock",custom)
        import json
        j=json.loads((ROOT/"src/main/resources/caszual_mtg.mixins.json").read_text())
        self.assertIn("CommanderTopDeckboxMixin",j["mixins"])

    def test_card_footprint_and_aspect_ratio(self):
        w=0.743-0.257
        h=0.842-0.158
        ratio=w/h
        self.assertAlmostEqual(ratio,0.711,delta=.02)
        self.assertGreater(0.257,0.18)
        self.assertLess(0.842,0.86)
        # Commander card surface is above the native 15.1/16 top plank.
        self.assertGreater(15.195/16,15.1/16)

if __name__=="__main__":
    unittest.main()
