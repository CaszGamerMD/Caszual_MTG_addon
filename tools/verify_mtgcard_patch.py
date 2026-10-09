#!/usr/bin/env python3
"""CI: exercise our fail-closed patcher against the actual resolved MTGCard dependency."""
import json
import os
from pathlib import Path
import sys
import tempfile
from zipfile import BadZipFile, ZipFile

from patch_mtgcard_mousetweaks import patch_jar, CONFIG


def main():
    if len(sys.argv) != 2:
        sys.exit("Usage: verify_mtgcard_patch.py build/runtime-classpath.txt")
    entries = Path(sys.argv[1]).read_text(encoding="utf-8").split(os.pathsep)
    found = []
    for entry in entries:
        path = Path(entry)
        if not path.is_file() or not path.name.endswith(".jar"):
            continue
        try:
            with ZipFile(path) as jar:
                if CONFIG in jar.namelist() and json.loads(jar.read("fabric.mod.json")).get("id") == "mtgcard":
                    found.append(path)
        except (BadZipFile, KeyError, ValueError):
            continue
    if len(found) != 1:
        sys.exit(f"Expected one MTGCard runtime JAR, found {len(found)}: {found}")
    with tempfile.TemporaryDirectory() as temp:
        target = Path(temp) / "patched-mtgcard.jar"
        patch_jar(found[0], target)
        with ZipFile(found[0]) as a, ZipFile(target) as b:
            assert a.namelist() == b.namelist()
            assert all(a.read(name) == b.read(name) for name in a.namelist() if name != "fabric.mod.json")
            original = json.loads(a.read("fabric.mod.json"))
            patched = json.loads(b.read("fabric.mod.json"))
            assert len(patched["mixins"]) == len(original["mixins"]) - 1
        print(f"PASS: patching real MTGCard dependency leaves all unrelated entries intact ({found[0].name})")


if __name__ == "__main__":
    main()
