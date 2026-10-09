#!/usr/bin/env python3
"""CI check of Java 25 preserving hotfix against the real Gradle MTGCard dependency."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from zipfile import BadZipFile, ZipFile

CLASS = "com/spider/mtgcard/client/compat/mousetweaks/MouseTweaksCompatMixinPlugin.class"
CLASS_BINARY = "com.spider.mtgcard.client.compat.mousetweaks.MouseTweaksCompatMixinPlugin"


def main():
    cp = Path("build/runtime-classpath.txt").read_text(encoding="utf-8").split(os.pathsep)
    matches = []
    for filename in cp:
        path = Path(filename)
        if not path.is_file() or path.suffix != ".jar":
            continue
        try:
            with ZipFile(path) as jar:
                if (CLASS in jar.namelist()
                    and json.loads(jar.read("fabric.mod.json")).get("id") == "mtgcard"):
                    matches.append(path)
        except (BadZipFile, KeyError, ValueError):
            continue
    if len(matches) != 1:
        raise SystemExit(f"Expected exactly one MTGCard dependency, found {len(matches)}: {matches}")
    original = Path("build/mtgcard-java-hotfix-original.jar")
    shutil.copyfile(matches[0], original)
    cmd = ["java", "-jar", "build/mtgcard-mousetweaks-fixer.jar", str(original)]
    subprocess.run(cmd, check=True)
    patched = Path("build/mtgcard-java-hotfix-original-earlyload-fixed.jar")
    with ZipFile(original) as a, ZipFile(patched) as b:
        assert a.namelist() == b.namelist(), "Archive entries changed"
        assert all(a.read(name) == b.read(name) for name in a.namelist() if name != CLASS), (
            "Unexpected change outside compatibility plugin"
        )
        assert a.read(CLASS) != b.read(CLASS), "Fixer didn't modify plugin method"
    javap = subprocess.run(
        ["javap", "-p", "-c", "-classpath", str(patched), CLASS_BINARY],
        text=True, capture_output=True, check=True
    ).stdout
    fragment = javap.split("boolean isClassPresent(java.lang.String);")[-1].split("\n}")[0]
    assert "ClassLoader.getResource" in fragment, "Expected safe resource lookup"
    assert "Class.forName" not in fragment, "Dangerous class load still present"
    print("PASS: patched official MTGCard dependency; compatibility remains registered;")
    print("PASS: plugin uses resource lookup, unrelated JAR entries are byte-identical.")


if __name__ == "__main__":
    main()
