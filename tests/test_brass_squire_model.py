"""Check the actual Commander Golem assets, not an illustrative screenshot."""
import json
import struct
import unittest
import zlib
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
ART=ROOT/"src/main/resources/assets/caszual_mtg"
JAVA=ROOT/"src/main/java/dev/casz/caszualmtg"

class BrassSquireModel(unittest.TestCase):
    def test_dedicated_png_is_valid_and_has_all_atlas_slots(self):
        data=(ART/"textures/item/brass_squire.png").read_bytes()
        self.assertTrue(data.startswith(b"\x89PNG\r\n\x1a\n"))
        offset=8
        info=None
        compressed=[]
        palette=b""
        while offset<len(data):
            length=struct.unpack(">I",data[offset:offset+4])[0]
            key=data[offset+4:offset+8]
            body=data[offset+8:offset+8+length]
            checksum=struct.unpack(">I",data[offset+8+length:offset+12+length])[0]
            self.assertEqual(zlib.crc32(key+body)&0xffffffff,checksum,key)
            if key==b"IHDR":
                info=struct.unpack(">IIBBBBB",body)
            elif key==b"PLTE":palette=body
            elif key==b"IDAT":compressed.append(body)
            elif key==b"IEND":break
            offset+=12+length
        self.assertEqual((64,64,8,3),info[:4])
        self.assertGreaterEqual(len(palette),48*3)
        self.assertEqual(len(zlib.decompress(b"".join(compressed))),64*(64+1))

    def test_seated_model_is_valid_3d_and_bright_faced(self):
        model=json.loads((ART/"models/item/commander_golem.json").read_text())
        elements=model["elements"]
        self.assertGreaterEqual(len(elements),120)
        self.assertEqual({"caszual_mtg:item/brass_squire"},set(model["textures"].values()))
        self.assertTrue(0.5<=min(e["from"][1] for e in elements)<=0.8)
        self.assertLessEqual(max(e["to"][1] for e in elements),16)
        self.assertEqual([0,0,0],model["display"]["fixed"]["rotation"])
        self.assertAlmostEqual(0.93,model["display"]["fixed"]["scale"][1])
        green=0
        tilted=0
        for e in elements:
            self.assertTrue(all(a<b for a,b in zip(e["from"],e["to"])))
            if "rotation" in e:
                self.assertIn(e["rotation"]["angle"],[-45,-22.5,0,22.5,45])
                tilted+=1
            for face in e["faces"].values():
                self.assertIn(face["texture"][1:],model["textures"])
                self.assertEqual(4,len(face["uv"]))
                self.assertTrue(all(0<=p<=16 for p in face["uv"]))
                green+=face["texture"]=="#emerald"
        self.assertGreater(green,12)
        self.assertGreater(tilted,20)

    def test_entity_model_is_seated_and_restored(self):
        src=(JAVA/"CommanderGolemVisuals.java").read_text()
        self.assertIn("golem.getY()+.50",src)
        self.assertIn("setItemTransform(ItemDisplayContext.FIXED)",src)
        self.assertIn("nearby.isEmpty()",src)
        self.assertIn("nearby.getFirst()",src)
        self.assertIn("display.setItemStack(new ItemStack(CaszualMtg.COMMANDER_GOLEM))",src)
        self.assertIn("d.discard()",src)

if __name__=="__main__":
    unittest.main()
