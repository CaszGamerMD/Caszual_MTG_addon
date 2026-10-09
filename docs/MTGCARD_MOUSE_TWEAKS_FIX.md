# MTGCard / Mouse Tweaks "loaded too early" hotfix

Minecraft **26.2 Fabric**, MTGCard **1.7.0-26.2**, Caszual MTG.

## Why it crashes even if both mods worked before

The exception is raised while preparing the MTGCard compatibility mixin:

```text
Critical problem: mtgcard.client.mixins.json:MouseTweaksGuiContainerHandlerMixin
from mod mtgcard target yalter.mousetweaks.handlers.GuiContainerHandler was loaded too early.
```

The `MouseTweaksCompatMixinPlugin` in MTGCard performs a class detection test using
`Class.forName(name, false, ...)`. The `false` prevents *initialization* but
**does not prevent loading**; this can load the Mouse Tweaks handler while Mixin
is still discovering/preparing its transformations. It can surface after unrelated
mod changes because class-loading order changes.

This does **not** mean Mouse Tweaks itself has broken.

## Recommended fix: small standalone fixer JAR

The Java 25 fixer modifies **one class in your own local copy of MTGCard**:
it changes the detection check to `ClassLoader.getResource`, which only
locates the class file and **does not load the handler class**.
The MTGCard compatibility mixin stays enabled, so this preserves its special
Card Database drag-slot handling and Mouse Tweaks' ordinary functionality.

1. Download the runnable [MTGCard Mouse Tweaks fixer JAR](../release/mtgcard-mousetweaks-fixer.jar).
2. Back up your original `MtgCard-fabric-1.7.0-26.2.jar` (outside `mods`).
3. With Java 25 installed, **double-click the fixer JAR** and select the original
   MTGCard JAR in the file picker. If your system does not run JARs by double-click,
   open a terminal in your downloads folder and run:
   ```powershell
   java -jar mtgcard-mousetweaks-fixer.jar "C:\\path\\to\\MtgCard-fabric-1.7.0-26.2.jar"
   ```
4. It creates `MtgCard-fabric-1.7.0-26.2-earlyload-fixed.jar` alongside the original.
   **The original is never overwritten.**
5. In your **client** `mods` folder, replace the original MTGCard JAR with the
   `-earlyload-fixed.jar` copy. Keep Caszual MTG, Fabric API and Mouse Tweaks installed.
6. Do **not** keep both MTGCard versions in `mods`; that causes a duplicate mod ID.
   The dedicated server can keep the original official MTGCard JAR.

The fixer refuses to modify unexpected or already-patched plugin classes, and it
verifies unrelated ZIP entries remain identical. A newer official MTGCard release
that fixes this upstream is preferable; this is a targeted local workaround.

The fixer JAR is **not a Fabric mod** and does not go in `mods`. It is a
one-time utility that produces a locally patched MTGCard JAR.

### Validation

On CI, this project builds the fixer using Java 25, runs it on the **resolved
MTGCard JAR used by the mod's Gradle build**, and confirms the patched class
uses `ClassLoader.getResource` rather than `Class.forName` while all other
JAR entries are identical. That is a bytecode/regression check, not a substitute
for launching the full user modpack.

## Older emergency workaround (less ideal)

The Python script at `tools/patch_mtgcard_mousetweaks.py` removes MTGCard's
optional Mouse Tweaks mixin registration instead of fixing the unsafe class
probe. This disables MTGCard's special Card Database slot protection, so use the
Java fixer above in preference to the Python workaround.

MTGCard upstream implementation:
[MouseTweaksCompatMixinPlugin.java](https://github.com/blackspider9678/MtgCard/blob/master/common/src/client/java/com/spider/mtgcard/client/compat/mousetweaks/MouseTweaksCompatMixinPlugin.java).
