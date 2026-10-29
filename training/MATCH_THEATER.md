# Commander Golem Match Theater

The Match Theater is an **offline, read-only replay viewer** for the standalone Commander rules diagnostic. It does not play Magic itself, implement additional rulings, or integrate with Minecraft.

## Open and watch a match

- **Open [the ready-to-watch Budget Deck vs. Garbo Gobbos HTML](examples/match-theater-real-decks.html).** Download the HTML file using GitHub's file Download action and open it in Chrome or another modern browser. No server or installed software is needed.
- To watch your own matches, open [the reusable viewer](viewer.html) in a browser, select **Open replay**, and choose a simulator **turn-replay JSON**. You can also drag and drop the JSON file onto the page.
- Running a new simulation with \`python training/simulator.py simulate --demo\`, \`diagnose\`, or \`pool-diagnose\` exports fresh self-contained HTML from this template. New exported matches carry a public LIFO stack, priority, exile cards, and mana pools.
- Press **Play** or **Space** to advance automatically. Switch between 0.5×, 1×, 2×, and 4×; enable **Highlights** to skip low-interest log entries during automatic playback, or use arrows and the timeline to inspect every event.
- Select a permanent to see its public characteristics; select **Player 1 zones** or **Player 2 zones** for graveyards and exile. **Rules questions** remain separately editable and exportable for review.

## What you see

The top half of the felt tabletop is Player 2. The bottom half is Player 1. Each has separate creature, other-permanent, and land rows, plus a hidden-card hand count and life wheel. New cards glow as they appear; changes in counters or tapped status are outlined. When recorded in an event, attackers and blockers receive a combat highlight. Cards use original offline CSS frames and abstract symbols; card art is not invented or loaded remotely.

The center shows the active player, turn, phase, and current event. The right side shows the *actual recorded* public priority stack with its next-to-resolve item first, plus a searchable nearby play log. Each physical card can be inspected for public attributes. No hidden identities are shown, and search, draw, and hand information are represented only as counts unless the engine has explicitly revealed a card.

## Replay format and backward compatibility

- Viewer input remains \`schemaVersion: 1\` and \`kind: "turn-replay"\` or \`kind: "rules-review"\`.
- Raw \`events\` and older \`packedReplay: 1\` / \`compactEvents\` both work.
- The packed format keeps its original card-index and player-array slots, appending new **public** information rather than changing existing indexes.
- New compact event states include \`state.stack\`, \`state.priority\`, \`players[].exile\`, and \`players[].manaPool\`, with event-varying kind, creature status, loyalty, charge counters, attachment, hexproof, and ward characteristics.
- Older compact files genuinely lack some state fields. The viewer identifies the stack as **not recorded**, not empty or fabricated; old exile and mana records default to empty/unknown in display. Re-exporting from a new simulation produces richer state.
- Saved sample HTML contains a replay generated before stack capture was added. Its existing combat events and life history are authentic; its stack cannot be reconstructed retroactively.

## Safety and limits

The viewer intentionally has **no network dependencies** and uses text nodes to display replay/card names, not \`innerHTML\`. Generated replay HTML escapes script delimiters from card/deck text. Saved hand cards, library order, and future decisions are never serialized to public replay state. Rules questions are review notes only, not proof that a card is supported.

This is still a **two-player diagnostic approximation**, not a complete Commander engine. Visual flourishes never substitute for simulator decisions. The viewer does not change the engine's scoring or training and is not an AI player.

Regression checks are in \`training/tests/test_match_theater.py\`. The JavaScript is syntax-checked when Node.js is available, and the self-contained sample is checked for valid, nonempty replay data.
