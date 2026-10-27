# Death and creature-entry lessons

These are implemented, tested rules for the limited two-player diagnostic. They
are programmed rules knowledge, not evidence of strategic learning. The real
decks remain ineligible for shared-policy training and live golem deployment.

## Questions answered

| Question | Implemented answer | Evidence |
| --- | --- | --- |
| Does Blood Artist see creatures that die with it? | Yes. Inspect the battlefield immediately before simultaneous deaths; emit one trigger per dying creature, including enemies and itself. | `test_death_triggers_look_back_and_distinguish_control` |
| Does Zulaport Cutthroat see enemy deaths? | No. It sees itself and other creatures controlled by its controller, including simultaneous deaths. | Same test, plus actual combat resolution in `test_simultaneous_combat_deaths_trigger_artist_and_cutthroat` |
| Can a death trigger save a player who already lost from combat? | No. Check player loss before resolving the queued death triggers. | `test_combat_loss_is_checked_before_death_lifegain` |
| How many Squirrels does Nested Shambler make? | Use its last battlefield power, including bonuses/counters; negative or zero creates none. Tokens enter tapped under the dead creature's controller, even on an opponent's turn. | `test_nested_shambler_death_uses_last_known_power_and_counts_zero`, `test_nested_shambler_uses_last_power_and_defender_controls_tapped_tokens` |
| Does Impact Tremors see tokens and Vehicles? | It sees every allied creature entry, including tokens. An unanimated Vehicle entering is not a creature entry. | `test_impact_tremors_watches_creatures_and_tokens_not_enemy_or_vehicle` |
| Can a token-entry trigger interrupt a token-creation spell? | No. Create the full batch before resolving any of its entry triggers. Tremors damage is noncombat damage, not commander combat damage. | `test_token_spell_finishes_before_lethal_impact_tremors_trigger` |
| Are questions raised during play preserved? | Yes. Merge runtime questions with the card audit instead of replacing them. | `test_real_deck_report_keeps_runtime_questions` |

## Sources

- [Official comprehensive-rules entry point](https://magic.wizards.com/en/rules): triggered abilities, last known information, active/nonactive player ordering, and state-based actions.
- [Innistrad Remastered release notes](https://magic.wizards.com/en/news/feature/innistrad-remastered-release-notes): Blood Artist and simultaneous deaths.
- [Time Spiral Remastered release notes](https://magic.wizards.com/en/news/feature/time-spiral-remastered-release-notes-2021-03-23): Zulaport Cutthroat and simultaneous deaths.
- [Modern Horizons 2 release notes](https://magic.wizards.com/en/news/feature/modern-horizons-2-release-notes-2021-06-04): Nested Shambler uses its last battlefield power; nonpositive power creates no tokens.
- [Foundations release notes](https://magic.wizards.com/en/news/feature/magic-the-gathering-foundations-release-notes): Impact Tremors triggers once per entering creature.

## Still open

The combat helper combines first-strike and regular damage into one result. If
new death triggers would need resolution between those steps, the diagnostic
pauses before applying combat, records a blocking question, and preserves it in
the report. This is tested rather than silently inventing timing.

There is still no general priority/response stack, multi-attacker combat,
arbitrary target selection, death replacement system, or comprehensive
state-based-action loop. Blood Artist chooses the opponent in this two-player
pilot. Chatterfang, sacrifice engines, and other unsupported cards remain
unplayable and flagged. Learned-policy weights are unchanged by these diagnostics.

## Play-test record

Six distinct pairings, seeds 142–147, each completed ten turns per player. The
committed `examples/death-rules-pool-summary.json` reports plays, trigger log
entries, unsupported cards encountered, and runtime questions without using win
rate as a progress score. New death rules are verified by controlled combat
scenarios even when a shuffled ten-turn match never exercises them.
