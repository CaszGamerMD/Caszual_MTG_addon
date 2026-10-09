# MTGCard + Mouse Tweaks: "loaded too early" startup crash

**Applies to Minecraft 26.2 / Fabric, MTGCard 1.7.0-26.2.**

## Cause

The startup error may say:

```text
Critical problem: mtgcard.client.mixins.json:MouseTweaksGuiContainerHandlerMixin
from mod mtgcard target yalter.mousetweaks.handlers.GuiContainerHandler was loaded too early.
```

This exception names **MTGCard's** compatibility mixin, not a Caszual MTG mixin.
In MTGCard's public source, `MouseTweaksCompatMixinPlugin.onLoad` uses
`Class.forName("yalter.mousetweaks.handlers.GuiContainerHandler", false, ...)`.
Even with initialization disabled, loading the target class prematurely can prevent
MTGCard's mixin from applying to it.

The proper upstream fix is to check for the class *without loading it* (such as a
class-file resource lookup) or use a mod-presence check when appropriate.

## Workaround while waiting for an upstream MTGCard update

**This patch modifies your local copy of MTGCard, not Caszual MTG.**
It *only* removes MTGCard's `mtgcard.client.mixins.json` configuration
registration from `fabric.mod.json`. The patcher refuses to run if that
configuration includes anything other than the single known Mouse Tweaks
mixin. MTGCard's main and Flashback mixin configurations are left untouched.

On **Windows**:
1. Back up `MtgCard-fabric-1.7.0-26.2.jar` from your `mods` folder.
2. Download these two files from this repository into **the same folder**:
   - [patch-mtgcard.bat](../tools/patch-mtgcard.bat)
   - [patch_mtgcard_mousetweaks.py](../tools/patch_mtgcard_mousetweaks.py)
3. Drag the official MTGCard JAR onto `patch-mtgcard.bat`.
4. A new `MtgCard-fabric-1.7.0-26.2-no-early-mousetweaks.jar` appears **beside the original**.
5. In your client `mods` folder, keep **only the patched MTGCard JAR**,
   Caszual MTG, Mouse Tweaks and their required dependencies. Do not leave
   both versions of MTGCard installed.

Or use Python 3 directly:

```powershell
python tools/patch_mtgcard_mousetweaks.py "C:\\path\\to\\MtgCard-fabric-1.7.0-26.2.jar"
```

The original JAR stays untouched. The script will refuse unknown versions,
unexpected mixin configurations, in-place changes, duplicate entries, and
overwriting an existing file.

**Tradeoff:** This temporarily disables MTGCard's special protection for
Card Database slots while Mouse Tweaks is running. Mouse Tweaks itself is
still installed, and its general inventory features are not disabled.
Avoid using Mouse Tweaks drag operations on MTGCard's Card Database slots
until MTGCard releases a native compatibility fix.

This is a **workaround**, not a replacement for upstream fix or a guarantee
against unrelated startup problems. The patched JAR is intended for the
**client**. Leave the dedicated server on the official MTGCard build.

## Developer verification

```bash
python3 -m unittest discover -s tests -p 'test_patch_mtgcard_mousetweaks.py' -v
```

Tests cover preserving all unrelated JAR entries, preserving original
input bytes, and failing safely on unknown mixins/mod IDs or collisions.
A successful test of the metadata patch is not equivalent to a
full GUI startup test in the user's modpack.

Upstream source: [MTGCard Mouse Tweaks compatibility plugin](https://github.com/blackspider9678/MtgCard/blob/master/common/src/client/java/com/spider/mtgcard/client/compat/mousetweaks/MouseTweaksCompatMixinPlugin.java).
