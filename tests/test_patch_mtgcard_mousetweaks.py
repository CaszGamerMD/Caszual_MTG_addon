"""Tests for the optional MTGCard compatibility hotfix."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile

SPEC = importlib.util.spec_from_file_location(
    "mtgcard_patch", Path(__file__).resolve().parents[1] / "tools" / "patch_mtgcard_mousetweaks.py"
)
patch = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(patch)


class PatcherTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.original = Path(self.tmp.name) / "MtgCard-fabric-1.7.0-26.2.jar"
        self.patched = Path(self.tmp.name) / "MtgCard-hotfix.jar"
        self.manifest = {
            "schemaVersion": 1, "id": "mtgcard",
            "mixins": [
                "mtgcard.mixins.json",
                {"config": "mtgcard.client.mixins.json", "environment": "client"},
                "mtgcard.flashback.mixins.json",
            ],
        }
        self.compat = {"required": False, "plugin": patch.PLUGIN, "client": [patch.MIXIN]}
        self.prepare()

    def prepare(self):
        with ZipFile(self.original, "w") as jar:
            jar.writestr("fabric.mod.json", json.dumps(self.manifest))
            jar.writestr(patch.CONFIG, json.dumps(self.compat))
            jar.writestr("mtgcard.mixins.json", '{"mixins":["CoreMixin"]}')
            jar.writestr("mtgcard.flashback.mixins.json", '{"client":["FlashbackMixin"]}')
            jar.writestr("com/spider/mtgcard/MyClass.class", b"\\xca\\xfe\\xba\\xbe".decode("unicode_escape").encode("latin1"))

    def test_only_registration_removed(self):
        patch.patch_jar(self.original, self.patched)
        with ZipFile(self.original) as a, ZipFile(self.patched) as b:
            self.assertEqual(a.namelist(), b.namelist())
            for name in a.namelist():
                if name != "fabric.mod.json":
                    self.assertEqual(a.read(name), b.read(name))
            mod = json.loads(b.read("fabric.mod.json"))
            self.assertEqual(mod["mixins"], ["mtgcard.mixins.json", "mtgcard.flashback.mixins.json"])
        with ZipFile(self.original) as a:
            self.assertEqual(json.loads(a.read("fabric.mod.json")), self.manifest)

    def test_fail_closed_on_other_mixins(self):
        self.compat["client"].append("UnrelatedMixin")
        self.prepare()
        with self.assertRaisesRegex(patch.PatchError, "Unknown Mouse Tweaks"):
            patch.patch_jar(self.original, self.patched)
        self.assertFalse(self.patched.exists())

    def test_fail_closed_on_wrong_mod(self):
        self.manifest["id"] = "not_mtgcard"
        self.prepare()
        with self.assertRaisesRegex(patch.PatchError, "Wrong mod ID"):
            patch.patch_jar(self.original, self.patched)

    def test_no_overwrite(self):
        self.patched.write_text("existing")
        with self.assertRaisesRegex(patch.PatchError, "overwrite"):
            patch.patch_jar(self.original, self.patched)

    def test_no_in_place(self):
        with self.assertRaisesRegex(patch.PatchError, "different path"):
            patch.patch_jar(self.original, self.original)


if __name__ == "__main__":
    unittest.main()
