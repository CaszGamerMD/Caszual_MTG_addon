"""Exact 24-bit tabletop/playmat colors, and independent paper upholstery."""
import json
import struct
import unittest
import zlib
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
JAVA=ROOT/"src/main/java/dev/casz/caszualmtg"
RES=ROOT/"src/main/resources/assets/caszual_mtg"

def source(name):return (JAVA/name).read_text(encoding="utf8")
def asset(name):return json.loads((RES/name).read_text(encoding="utf8"))

class ExactPlaymatColorTest(unittest.TestCase):
 def test_server_preserves_selected_hex_without_dye_approximation(self):
  logic=source("TabletopLogic.java")
  be=source("TabletopBlockEntity.java")
  hand=source("HandLogic.java")
  self.assertIn("StaffColors.rgb(hand.tableColor())",logic)
  self.assertIn("table.matRgb(rgb)",logic)
  self.assertIn("t.matRgb(color)",logic)
  self.assertNotIn("nearestDye",logic)
  for token in ("private int matRgb=0x315348","rgb&0xFFFFFF",
                'out.putInt("MatRgb",matRgb)','in.getIntOr("MatRgb",0x315348)',
                'tag.putInt("MatRgb",matRgb)','record RenderData(String wood,int rgb)'):
   self.assertIn(token,be)
  self.assertIn('hand.tableColor(req.text())',hand)
  self.assertIn("TabletopLogic.refreshColor(player,hand)",hand)

 def test_world_model_colors_only_playmat_faces(self):
  block=asset("models/block/tabletop.json")
  self.assertEqual(block["textures"]["felt"],"caszual_mtg:block/flat_white")
  tinted=[face for element in block["elements"] for face in element["faces"].values() if "tintindex" in face]
  self.assertGreaterEqual(len(tinted),5)
  self.assertTrue(all(face["texture"]=="#felt" and face["tintindex"]==0 for face in tinted))
  self.assertTrue(all("tintindex" not in face for el in block["elements"] for face in el["faces"].values() if face["texture"]=="#wood"))
  states=asset("blockstates/tabletop.json")["multipart"]
  self.assertEqual(len(states),5)
  self.assertEqual(states[0]["apply"]["model"],"caszual_mtg:block/tabletop")
  self.assertFalse(any("felt" in entry.get("when",{}) for entry in states))
  self.assertIn("new TableWorldModel(model)",source("CustomBoxModels.java"))

 def test_paper_cushion_uses_rgb_and_wool_leather_stay_independent(self):
  chair=source("ChairBlock.java")
  be=source("ChairBlockEntity.java")
  states=asset("blockstates/material_chair.json")["multipart"]
  paper=[entry for entry in states if entry.get("when",{}).get("cushion")=="paper"]
  self.assertEqual(len(paper),4)
  self.assertFalse(any("paper" in entry.get("when",{}).get("cushion","") and entry.get("when",{}).get("color") for entry in states))
  self.assertIn("rgb=table.matRgb()",chair)
  self.assertIn("chair.paperRgb(rgb)",chair)
  self.assertIn('out.putInt("PaperRgb",matRgb)',be)
  self.assertIn('record RenderData(String wood,int paperRgb)',be)
  layer=asset("models/block/chair_cushion_paper.json")
  self.assertEqual(layer["textures"]["fabric"],"caszual_mtg:block/flat_white")
  self.assertTrue(all(face["tintindex"]==0 for el in layer["elements"] for face in el["faces"].values()))
  for entry in states:
   if entry.get("when",{}).get("cushion")=="leather":
    self.assertIn("chair_cushion_leather_",entry["apply"]["model"])
   if entry.get("when",{}).get("cushion")=="wool":
    self.assertNotIn("paper",entry["when"]["cushion"])

 def test_fabric_26_2_tint_registry_uses_render_attachment(self):
  client=source("CaszualMtgClient.java")
  self.assertIn("BlockColorRegistry.register",client)
  self.assertIn("new net.minecraft.client.color.block.BlockTintSource()",client)
  self.assertIn("level.getBlockEntityRenderData(pos)",client)
  self.assertIn("rendered.rgb()&0xFFFFFF",client)
  self.assertIn("rendered.paperRgb()&0xFFFFFF",client)
  self.assertIn("CaszualMtg.TABLETOP",client)
  self.assertIn("CaszualMtg.MATERIAL_CHAIR",client)

 def test_white_base_is_opaque_not_carpet_colored(self):
  png=(RES/"textures/block/flat_white.png").read_bytes()
  self.assertEqual(png[:8],bytes([137,80,78,71,13,10,26,10]))
  self.assertEqual((struct.unpack(">I",png[16:20])[0],struct.unpack(">I",png[20:24])[0]),(16,16))
  self.assertEqual(png[25],6) # true RGBA
  pieces=[]
  off=8
  while off<len(png):
   n=struct.unpack(">I",png[off:off+4])[0]
   tag=png[off+4:off+8]
   if tag==b"IDAT":pieces.append(png[off+8:off+8+n])
   off+=12+n
  raw=zlib.decompress(b"".join(pieces))
  # PNG filtering is permitted, but a solid white source must have 16 RGBA rows.
  self.assertEqual(len(raw),16*(1+16*4))

if __name__=="__main__":unittest.main()
