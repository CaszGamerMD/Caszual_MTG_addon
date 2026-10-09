#!/usr/bin/env python3
"""Safely remove MTGCard's early-loading Mouse Tweaks mixin configuration.

Operates on a copy of a locally downloaded official MTGCard Fabric JAR.
No network access or third-party Python modules are required.
"""

import argparse
from copy import copy
import json
import os
from pathlib import Path
import shutil
import tempfile
from zipfile import BadZipFile, ZipFile

CONFIG = "mtgcard.client.mixins.json"
MIXIN = "MouseTweaksGuiContainerHandlerMixin"
PLUGIN = "com.spider.mtgcard.client.compat.mousetweaks.MouseTweaksCompatMixinPlugin"


class PatchError(ValueError):
    pass


def _load_json(jar, name):
    try:
        return json.loads(jar.read(name))
    except KeyError as exc:
        raise PatchError(f"Missing {name}: not a supported MTGCard Fabric JAR") from exc
    except (ValueError, UnicodeDecodeError) as exc:
        raise PatchError(f"Invalid JSON in {name}") from exc


def _manifest_config(entry):
    return entry if isinstance(entry, str) else entry.get("config") if isinstance(entry, dict) else None


def patch_jar(source: Path, destination: Path) -> None:
    source = Path(source)
    destination = Path(destination)
    if source.resolve() == destination.resolve():
        raise PatchError("Output must be a different path: the original JAR is never modified")
    if not source.is_file():
        raise PatchError(f"Cannot find JAR: {source}")
    if destination.exists():
        raise PatchError(f"Refusing to overwrite existing file: {destination}")

    try:
        with ZipFile(source, "r") as jar:
            names = jar.namelist()
            if len(names) != len(set(names)):
                raise PatchError("Duplicate ZIP entries: refusing to modify ambiguous JAR")
            manifest = _load_json(jar, "fabric.mod.json")
            if manifest.get("id") != "mtgcard":
                raise PatchError("Wrong mod ID; expected official MTGCard Fabric JAR")
            compat = _load_json(jar, CONFIG)
            if compat.get("plugin") != PLUGIN or compat.get("client") != [MIXIN]:
                raise PatchError("Unknown Mouse Tweaks configuration; no safe patch for this MTGCard version")
            if compat.get("mixins", []) or compat.get("server", []):
                raise PatchError("The compatibility config contains additional mixins; refusing to remove them")
            mixins = manifest.get("mixins", [])
            matched = [i for i, entry in enumerate(mixins) if _manifest_config(entry) == CONFIG]
            if len(matched) != 1:
                raise PatchError("Expected exactly one registration of MTGCard's Mouse Tweaks config")
            manifest["mixins"] = [entry for i, entry in enumerate(mixins) if i != matched[0]]
            patch_bytes = (json.dumps(manifest, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
            destination.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(prefix="mtgcard-hotfix-", suffix=".jar", dir=destination.parent)
            os.close(fd)
            try:
                with ZipFile(tmp, "w") as target:
                    target.comment = jar.comment
                    for entry in jar.infolist():
                        # Copy ZipInfo before writing, because ZipFile mutates its header offset.
                        with target.open(copy(entry), "w") as dst:
                            if entry.filename == "fabric.mod.json":
                                dst.write(patch_bytes)
                            else:
                                with jar.open(entry, "r") as src:
                                    shutil.copyfileobj(src, dst, 1024 * 1024)
                with ZipFile(tmp) as checked:
                    if checked.testzip() is not None:
                        raise PatchError("ZIP validation failed")
                    result = _load_json(checked, "fabric.mod.json")
                    if any(_manifest_config(x) == CONFIG for x in result.get("mixins", [])):
                        raise PatchError("The offending mixin config is still registered")
                os.replace(tmp, destination)
            finally:
                if os.path.exists(tmp):
                    os.unlink(tmp)
    except BadZipFile as exc:
        raise PatchError("Invalid JAR/ZIP file") from exc


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("jar", type=Path, help="Official MTGCard Fabric 1.7.0-26.2 JAR to patch")
    p.add_argument("--output", type=Path, help="Output patched JAR (default: beside input)")
    args = p.parse_args(argv)
    original = args.jar
    output = args.output or original.with_name(original.stem + "-no-early-mousetweaks.jar")
    try:
        patch_jar(original, output)
    except (PatchError, PermissionError, OSError) as exc:
        p.exit(1, f"Patch not applied: {exc}\n")
    print(f"Patched successfully: {output}")
    print("Keep the original JAR outside mods/ as a backup.")
    print("In mods/: use this patched MTGCard JAR INSTEAD of the original, plus Mouse Tweaks and Caszual MTG.")
    print("MTGCard's special Mouse Tweaks database-slot protection is disabled; other Mouse Tweaks features remain.")


if __name__ == "__main__":
    main()
