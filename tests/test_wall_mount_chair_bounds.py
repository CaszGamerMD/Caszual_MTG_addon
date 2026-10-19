"""Wall-click deckbox rack mounts and directional chair collision boxes."""
import json
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
JAVA=ROOT/"src/main/java/dev/casz/caszualmtg"
ASSET=ROOT/"src/main/resources/assets/caszual_mtg"

def read(path):
    return (JAVA/path).read_text(encoding="utf-8")

def rotate_y90(box):
    # Minecraft model 'y':90 rotates (x,z) to (16-z,x).
    x0,y0,z0,x1,y1,z1=box
    return (16-z1,y0,x0,16-z0,y1,x1)

class MountingAndChairBounds(unittest.TestCase):
    def test_wall_rack_uses_opposite_clicked_side_not_player_direction(self):
        src=read("DeckboxRackBlock.java")
        self.assertIn("Direction side=ctx.getClickedFace();",src)
        self.assertIn("boolean wall=side.getAxis().isHorizontal();",src)
        self.assertIn("Direction facing=wall?side.getOpposite():ctx.getHorizontalDirection().getOpposite();",src)
        self.assertIn(".setValue(WALL,wall).setValue(FACING,facing)",src)

    def test_rack_collision_is_on_supporting_face_in_all_four_directions(self):
        src=read("DeckboxRackBlock.java")
        expected={
            "NORTH":"Block.box(0,bottom,10,16,top,16)",
            "SOUTH":"Block.box(0,bottom,0,16,top,6)",
            "EAST":"Block.box(10,bottom,0,16,top,16)",
            "WEST":"Block.box(0,bottom,0,6,top,16)",
        }
        for direction,box in expected.items():
            self.assertIn(f"case {direction} -> {box}",src)
        # For each clicked face, rack facing is opposite it so the shelf
        # occupies the 6 model pixels closest to the clicked supporting wall.
        nearest={
            "north":("south","z",0,6),
            "south":("north","z",10,16),
            "east":("west","x",0,6),
            "west":("east","x",10,16),
        }
        parts=json.loads((ASSET/"blockstates/deckbox_rack.json").read_text())["multipart"]
        expected_y={"north":180,"east":90,"south":0,"west":270}
        for click,(facing,axis,low,high) in nearest.items():
            shelf=next(e for e in parts if e["when"]=={"wall":"true","facing":facing})
            self.assertEqual(shelf["apply"]["y"],expected_y[facing])
            if axis=="z":
                self.assertEqual((low,high),(0,6) if facing=="south" else (10,16))
            else:
                self.assertEqual((low,high),(0,6) if facing=="west" else (10,16))

    def test_chair_bounds_follow_json_rotation_not_inverse_direction(self):
        src=read("ChairBlock.java")
        self.assertIn("(1-box.maxZ)*16,box.minY*16,box.minX*16",src)
        self.assertIn("(1-box.minZ)*16,box.maxY*16,box.maxX*16",src)
        blocks=json.loads((ASSET/"models/block/material_chair.json").read_text())["elements"]
        # Top backrest crossbar is on south side of NORTH chair.
        back=tuple(blocks[-1]["from"]+blocks[-1]["to"])
        self.assertEqual(back,(0,14,14,16,16,16))
        expected={
            "north":(0,14,14,16,16,16),
            "east":(0,14,0,2,16,16),
            "south":(0,14,0,16,16,2),
            "west":(14,14,0,16,16,16),
        }
        current=back
        for direction in ("north","east","south","west"):
            self.assertEqual(current,expected[direction],direction)
            current=rotate_y90(current)
        self.assertEqual(current,back,"Full rotation should return to north")
        state=json.loads((ASSET/"blockstates/material_chair.json").read_text())
        rotations={"north":0,"east":90,"south":180,"west":270}
        self.assertEqual({
           e["when"]["facing"]:e["apply"]["y"] for e in state["multipart"]
           if "cushion" not in e["when"]
        },rotations)

if __name__=="__main__":
    unittest.main()
