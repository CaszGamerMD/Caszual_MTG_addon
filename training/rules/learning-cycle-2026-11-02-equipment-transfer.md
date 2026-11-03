# MTG Golem — Rhuk's Equipment transfer (2026-11-02)

This experimental standalone Python checkpoint adds a reusable, complete
Oracle-language rule for a creature with trample, haste and an optional
trigger when another equipped creature you control attacks or dies.

- Recognizes unfamiliar names with the same valid grammar; fails closed on
  unsupported trailing instructions or changed selection wording.
- Attack-time trigger observes live attachments on resolution, including a
  snapshot taken immediately before the attacked creature changes zones.
- Death-time trigger retains the attachments of the dying creature before
  they detach. No Equipment owner or controller changes.
- Resolution checks the receiving creature's instance and the Equipment
  instances, protection, and whether objects still exist. A player may
  decline the optional transfer.
- Four focused tests plus a dedicated early CI step cover parser strictness,
  attack timing, death last-known information, optional refusal and departed
  recipient identity.

Published baseline before this change: 600/700 recognized slots; Mono-Red
91/100 and Elves 95/100. This adds a candidate Mono-Red slot; its actual
coverage and regression status must be confirmed by GitHub Actions.
Autonomous training remains disabled (`learningEligible=false`).
