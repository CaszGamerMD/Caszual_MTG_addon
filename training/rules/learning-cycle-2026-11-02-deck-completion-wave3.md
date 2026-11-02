# MTG Golem — Goblins and Elves completion, third four-cycle pass (2026-11-02)

Scope: standalone diagnostic Oracle parser on `experiment/commander-ai-golem`.
No Minecraft changes; no diagnostic result is authorized as training data.

## Seven-deck coverage

Each new whole-card mechanic was compiled, exercised with real cards and
renamed/parameterized examples, then followed by a seven-deck diagnostic audit.
All seven saved lists retain exactly 100 cards; `learningEligible=false`.

| Cycle | Complete new Oracle program | Deck card added | Recognized card slots | Unique unsupported |
|---|---|---|---:|---:|
| Baseline | End of the previous published four-cycle pass | — | **588/700** | 109 |
| 1 | Repeated Squad additional mana payments; independent triggered copy batch; copied creature anthems remain live | Galadhrim Brigade (Elves) | **589/700** | 108 |
| 2 | Total *printed* mana value of controlled historic permanents reduces generic spell cost; only legendary creatures may be equipped | Excalibur, Sword of Eden (Mono-Red) | **590/700** | 107 |
| 3 | Alliance triggers for each other controlled creature entering; choose each of three modes at most once per turn; tapped Treasure and life gain | Gala Greeters (Elves) | **591/700** | 106 |
| 4 | Beginning-of-combat tokens per currently attached Aura and Equipment; next-end-step delayed exile of those exact tokens | Valduk, Keeper of the Flame (Mono-Red) | **592/700** | 105 |

Current deck totals: Lupitas elves **92/100** (8 unsupported), Mono Red Gobs
**87/100** (13 unsupported), Budget Deck 79/100, faeries 71/100, Getting Wild
with Enchantments 100/100, Garbo Gobbos 100/100, squirrels 63/100.

## Rules semantics

- **Squad:** A declared repeat count is validated and paid as part of the
  actual spell cost, carried on its stack event, and later converted into
  one batch of token copies. Copies preserve printed static abilities; their
  own Squad ability is not paid, and so does not recursively produce tokens.
  The trigger can resolve after the original source has left. The diagnostic
  agent enumerates affordable counts 0–3; direct casting accepts larger
  affordable counts.
- **Historic Equipment:** Artifact, legendary, or Saga characteristics are
  inspected on controlled battlefield permanents, excluding phased-out
  objects. Each qualifying permanent contributes its *printed* mana value
  exactly once. The resulting discount reduces generic casting cost only,
  not Equip's activation cost or colored requirements. The shared attachment
  grammar now preserves the `Equip legendary creature` target restriction;
  selection, activation, and resolution enforce it. The restriction does
  not detach Equipment if the attached creature later loses legendary status.
- **Alliance:** The Game event kernel creates independent entry triggers,
  excluding the source itself and opponents' creatures. The choice is made
  on trigger **resolution**, so simultaneous entries cannot select the same
  mode twice. Modes are self +1/+1 counter (using counter replacements),
  one tapped Treasure token, or life gain. A source's new battlefield
  incarnation receives new mode availability; the per-turn record clears
  at the next turn. Its ability can resolve after the source leaves.
- **Attached-combat tokens:** A closed Oracle grammar matches a beginning-of-
  combat trigger referencing the printed name or `this creature`, a fully
  described creature-token body, and the delayed exile sentence. The trigger
  counts currently attached Auras and Equipment on resolution, using their
  last-known count at the source's departure if it left the battlefield.
  Created IDs—not any future tokens with similar names—are scheduled for
  exile at the *beginning* of the next end step. The exile waits on the stack,
  even if the creating source has left. Tokens that have already left are not
  exiled again.
- **Determinism/identity repair:** Creature-token names assembled from
  unordered subtype sets now sort the subtypes deterministically. The shared
  battlefield adapter copies actual entry timestamps from its event kernel
  into simulator permanents; abilities bound to a specific incarnation can
  distinguish a newly returned source from the object that left.
- Every new grammar consumes the entire Oracle text after removal of
  balanced reminder text and refuses unmodeled extra instructions.

## Verification

- `python3 -m unittest discover -s training/tests -p test_deck_completion_cycles.py -q`:
  **25/25 passed** (eight new methods this pass), covering payability,
  legal/illegal targets, replacement timing, stack choices and delayed
  effects, last-known information, re-entry, controller scope, token types,
  and strict whole-card rejection of unknown text.
- Seven-deck `diagnostic_coverage.py` and regenerated
  `question_batches.py` inventory: **592/700**, no lost previously
  recognized slots, 105 unique unsupported names; training still blocked.
- Full regression, `python3 -m unittest discover -s training/tests -q`:
  **1,323 tests in 628.708 seconds; six failures, one skip**. The six
  failing methods match the previous published checkpoint exactly: five
  in `test_planeswalker_damage.py` and
  `test_simulator.py::test_real_deck_report_keeps_runtime_questions`.
  These are existing failures, not newly introduced regressions. The
  transient seventh failure reported in the previous session did not
  recur; deterministic token-subtype ordering now has a specific fix and
  independently passing regression coverage.

## Remaining completion queue

- **Mono-Red (13):** Squee, Dubious Monarch; Infantry Shield; Fortune Thief;
  Howlsquad Heavy; Sword of Hearth and Home; Sword of Hours; Sword of Truth
  and Justice; Sword of the Squeak; Mister Gutsy; Raubahn, Bull of Ala Mhigo;
  Armory Automaton; Rhuk, Hexgold Nabber; Dissection Tools.
- **Elves (8):** Kenrith's Transformation; Mosswort Bridge; The Great Henge;
  Growing Rites of Itlimoc // Itlimoc, Cradle of the Sun; Bow of Nylea;
  Umbral Mantle; Genesis Wave; Sword of Once and Future.

This is a two-player Oracle *diagnostic*, not a certified general-purpose
Commander game engine. Multiplayer targeting, replacement dependencies and
the remaining cards' instructions must be modeled before using the decks for
autonomous training; the existing safety gate remains closed.
