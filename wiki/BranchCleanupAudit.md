# Safe branch-cleanup audit — 17 October 2026

The audit compares every repository branch **against `main`** (GitHub compare API). A branch with **zero commits ahead** is completely contained in `main` and deleting its *branch reference* is safe for the code; the commits remain in `main`. Do **not** delete any source folders, commits, or release JARs as part of branch cleanup.

## Keep (not safe to delete)

- `main` — canonical release/default branch.
- `feat/multiplayer-mtg-tabletop` — **open PR #25**, 385+ commits ahead of `main` at audit; includes all active multiplayer tabletop, chairs, tokens, and hand controls. **Keep until explicitly reviewed, tested in-game and merged.**
- `art/caszual-suite-redesign` — **one commit ahead of `main`, 18 behind**; unmerged art work. **Keep and review/merge or archive deliberately.**

## Safe candidates for removing only the branch ref

These 24 branches each had **zero commits ahead of `main`** when checked. Their commits are already reachable from `main`:

- `chore/remove-unused-mtgcard-fixer`
- `feat/autonomous-url-deck-assembly`
- `feat/caszual-content-tag`
- `feat/deck-builder-persistent-rack-cardstore`
- `feat/four-staff-wall-rack`
- `feat/hand-bulk-cards-community-loose-deposit`
- `feat/placed-deckbox-commander-art`
- `feat/staff-rgb-hand-controls`
- `feature/mtg-targeting-staff`
- `fix/deferred-mtgcard-be-verification`
- `fix/full-art-basic-land-artwork`
- `fix/fullscreen-deck-builder-community-ui`
- `fix/mtgcard-block-entity-validation`
- `fix/mtgcard-mousetweaks-earlyload`
- `fix/private-card-hand-hover`
- `fix/rack-orientation-zfight-staff-height`
- `fix/thin-deckbox-rack-ledge`
- `fix/utility-box-facing-player`
- `fix-hand-card-back-uv`
- `fix-hand-card-backs`
- `fix-mtgcompanion-polish`
- `fix-staff-hand-rendering`
- `hand-visualizer-temp`
- `rebrand-caszual-mtg`

## Recommended safe procedure

1. First verify no automation, active PRs, deployments, or collaborator checkouts depend on any branch.
2. Use GitHub's **Branches** view to delete only those **24 fully merged/behind** branch references. Do not force-delete `main`, `feat/multiplayer-mtg-tabletop`, or `art/caszual-suite-redesign`.
3. Keep PR #25 open until the multiplayer mod is tested and intentionally merged into `main`. Then verify the new JAR and delete the branch ref *after* merge, not before.
4. Any branch whose ahead/behind status changes after this audit must be rechecked before deletion.

**No branches were deleted in this audit.** Keeping refs intact does not alter Minecraft saves, installed JARs, or code behavior.
