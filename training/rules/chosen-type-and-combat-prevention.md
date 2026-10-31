# Reusable Oracle blocks: chosen creature types and combat prevention

2026-10-31 — diagnostic Commander simulator, `experiment/commander-ai-golem`.
These are **executable diagnostic blocks**, not proof of complete Magic rules
coverage, multiplayer legality, or learning-ready matches.

## Three implementation cycles

1. **Chosen creature-type identity and entry-counter replacements.** A card
   that chooses a creature type on entering can now add that type to itself
   only while on the battlefield. Its `Other creatures you control of the
   chosen type` anthem excludes itself. `Each other creature you control of
   the chosen type enters with N additional +1/+1 counters` uses the normal
   entry-replacement engine, including Doubling Season and opponent scope.
   The same grammar works for renamed cards and different amounts. Existing
   chosen-type enchantments and artifacts continue to compile.
   Test: `test_chosen_type_identity_counters.py`.
2. **Whole-turn global combat prevention.** An Instant with `Prevent all combat
   damage that would be dealt this turn.` creates a prevention state only
   after spell-stack resolution. Both attacking and blocking damage, first
   strike, trample, lifelink, deaths and commander damage use the same
   prevention state. Noncombat damage remains untouched; cleanup expires it.
   Test: `test_combat_fog_spell.py`.
3. **Player-scoped prevention composed with populate.** `Prevent all combat
   damage that would be dealt to you this turn. Populate.` shields only the
   caster from combat damage, not their creatures. Populate chooses a
   controlled creature token on resolution (no token means no copy), then
   uses normal token-entry and replacement processing. New tokens copy
   base/copiable type, color, subtype, name, power/toughness and keyword
   characteristics; temporary buffs, counters, damage and tap state are not
   copied. Complex token programs not expressible by the current creator
   block deliberately halt diagnostic play. Test:
   `test_scoped_combat_populate.py`.

Every importer path requires the *whole* Oracle instruction; appended unknown
clauses reject the card. The motivating cards are Adaptive Automaton, Metallic
Mimic, Fog and Druid's Deliverance, but the execution does not use their names.

## Coverage measurements

Same seven saved decks, counting distinct unsupported card **names**:

| Audit | Unique unresolved | Elves accepted | Squirrels accepted | Garbo | Wilds |
| --- | ---: | ---: | ---: | ---: | ---: |
| Starting branch | 161 | 67/100 | 60/100 | 100/100 | 100/100 |
| Chosen-type cycle | 159 | 67/100 | 62/100 | 100/100 | 100/100 |
| All three cycles | 157 | 69/100 | 62/100 | 100/100 | 100/100 |

These counts are *diagnostic import coverage*, not behavioral certification.
The next high-leverage unresolved families include modal targeted spells,
activated equipment abilities and library choices. Correct targeting,
replacement ordering, priority and arbitrary token-copy programs remain
larger engine tasks; `learningEligible` stays `false`.
