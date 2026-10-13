"""Regression tests for the responsive Deck Builder, Community DB and Card Store slot."""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/"src/main/java/dev/casz/caszualmtg"

def intersects(a,b):
    return a[0]<b[2] and a[2]>b[0] and a[1]<b[3] and a[3]>b[1]

def rect(x,y,w,h):return (x,y,x+w,y+h)

def geometry(width,height):
    assert width>=640 and height>=430
    inv_top=height-98
    action=inv_top-49
    side=width-208
    browse_w=side-26
    return inv_top, action, side, browse_w

class FullscreenLayoutTests(unittest.TestCase):
    def test_dedicated_fullscreen_screen_geometry(self):
        for screen in ("BuilderScreen.java","CommunityScreen.java"):
            code=(SRC/screen).read_text()
            self.assertIn("imageWidth=width;",code)
            self.assertIn("imageHeight=height;",code)
            self.assertIn("FullScreenMenuLayout.positionInventory",code)
            self.assertNotIn("topPos+318",code)
            self.assertIn("renderBg",code)
        common=(SRC/"FullScreenMenuLayout.java").read_text()
        self.assertIn("MIN_WIDTH=640, MIN_HEIGHT=430",common)
        self.assertIn("menu.slots.get(first+i)",common)
        self.assertIn("(i<27?(i/9)*18:58)",common)
        mixins=(ROOT/"src/main/resources/caszual_mtg.mixins.json").read_text()
        self.assertIn("MenuSlotPositionAccessor",mixins)

    def test_responsive_zones_do_not_intersect_at_gui_sizes(self):
        # Minimum supported scaled GUI, user screenshot aspect, and large desktop.
        for w,h in ((640,430),(800,450),(960,540),(1280,720),(1920,1080)):
            inv,action,side,browse=geometry(w,h)
            with self.subTest(w=w,h=h):
                self.assertGreater(browse,348)
                self.assertLess(action+20,inv-14)
                inventory=[rect(12+(i%9)*18,inv+(i//9)*18,16,16) for i in range(27)]
                inventory += [rect(12+(i%9)*18,inv+58,16,16) for i in range(27,36)]
                builder_browse=rect(12,122,browse,action-9-122)
                community_browse=rect(12,86,browse,action-9-86)
                sidebar=rect(side+3,86,w-side-15,inv-86)
                for slot in inventory:
                    self.assertFalse(intersects(slot,builder_browse))
                    self.assertFalse(intersects(slot,community_browse))
                    self.assertFalse(intersects(slot,sidebar))
                self.assertFalse(intersects(builder_browse,rect(12,action,154,20)))
                self.assertFalse(intersects(community_browse,rect(12,action,78,20)))
                # Community list and sidebar never touch even at minimum 640px width.
                self.assertLess(builder_browse[2],side)
                self.assertLess(community_browse[2],side)
                # Builder deckbox slot left of label, outside browsing region.
                self.assertFalse(intersects(rect(side+17,128,16,16),builder_browse))

    def test_community_sidebar_transfer_actions_clear_inventory(self):
        for w,h in ((640,430),(960,540),(1920,1080)):
            inv,action,side,browse=geometry(w,h)
            ph=max(115,min(270,inv-213))
            loose=86+ph+14
            box=loose+26
            self.assertLessEqual(box+54+20,inv-12)
            self.assertFalse(intersects(rect(side+8,box,16,16),rect(side+36,box,180-42,20)))
            self.assertFalse(intersects(rect(side+8,loose,16,16),rect(side+36,loose,180-42,20)))

    def test_native_card_store_extra_slot_is_anchored_to_buy_controls(self):
        code=(SRC/"CardStoreDeckboxLayout.java").read_text()
        self.assertIn("SLOT_INDEX=36",code)
        self.assertIn('getMessage().getString().equals("Buy")',code)
        self.assertIn("screenY=buyY-25",code)
        self.assertIn("MenuSlotPositionAccessor",code)
        self.assertIn("screen.getMenu()",code)
        client=(SRC/"CaszualMtgClient.java").read_text()
        self.assertIn("CardStoreDeckboxLayout.arrange(store)",client)
        self.assertIn("CardStoreDeckboxLayout.screenSlotX(store)",client)
        self.assertNotIn("companion$getLeftPos()+190",client)

if __name__=="__main__":
    unittest.main()
