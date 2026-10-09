"""Static regression coverage for the Hand Block's opaque block-atlas card back."""
import json
from pathlib import Path
import struct
import unittest
import zlib

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "src/main/resources/assets/caszual_mtg"


class HandCardBackTests(unittest.TestCase):
    def test_all_twenty_models_use_existing_block_sprite(self):
        png = ASSETS / "textures/block/mtg_card_back.png"
        self.assertTrue(png.is_file(), "The referenced Hand card-back texture must be packaged")
        for i in range(1, 21):
            path = ASSETS / f"models/block/hand_cards_{i}.json"
            model = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(model["textures"]["card"], "caszual_mtg:block/mtg_card_back")
            self.assertGreater(len(model["elements"]), 0)
            for element in model["elements"]:
                self.assertEqual(element["faces"]["up"]["texture"], "#card")

    def test_sprite_is_fully_opaque_rgba_png(self):
        blob = (ASSETS / "textures/block/mtg_card_back.png").read_bytes()
        self.assertEqual(blob[:8], b"\x89PNG\r\n\x1a\n")
        offset = 8
        image_data = bytearray()
        width = height = None
        while offset < len(blob):
            length = struct.unpack_from(">I", blob, offset)[0]
            name = blob[offset + 4:offset + 8]
            data = blob[offset + 8:offset + 8 + length]
            checksum = struct.unpack_from(">I", blob, offset + 8 + length)[0]
            self.assertEqual(zlib.crc32(name + data) & 0xFFFFFFFF, checksum)
            if name == b"IHDR":
                width, height, depth, color, compression, filters, interlace = struct.unpack(">IIBBBBB", data)
                self.assertEqual((depth, color, compression, filters, interlace), (8, 6, 0, 0, 0))
            elif name == b"IDAT":
                image_data.extend(data)
            offset += 12 + length
        self.assertIsNotNone(width)
        self.assertGreater(height, 0)
        scan = zlib.decompress(image_data)
        self.assertEqual(len(scan), (width * 4 + 1) * height)
        for row in range(height):
            start = row * (width * 4 + 1)
            self.assertEqual(scan[start], 0, "The test expects filter 0 on opaque sprite")
            alpha = scan[start + 4:start + width * 4 + 1:4]
            self.assertTrue(all(a == 255 for a in alpha), "Card-back texels must never be translucent")


if __name__ == "__main__":
    unittest.main()
