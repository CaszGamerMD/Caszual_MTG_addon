# Repeated creature state-based actions

The diagnostic simulator now checks creature toughness and marked damage repeatedly before placing waiting triggers on the stack. Each death batch uses a single battlefield snapshot for death watchers; continuous effects are recalculated before the next batch. All triggers waiting across those batches are then placed together in active-player/nonactive-player order. Players cannot respond between batches.

Zero or negative toughness sends a creature to its destination even with indestructible. Lethal marked damage does not destroy an indestructible creature. Existing damage/deathtouch handlers still handle the initial damage batch. Surviving creatures in the ordinary combat path now retain their marked damage until cleanup, just as creatures in the separate strike-step path already did.

Checks run after an entire spell/ability finishes, when other entry/death triggers would be placed, and after cleanup removes temporary toughness. They do not interrupt the middle of an ability. Entry/death triggers generated while resolving an object wait for its completion and the state-based checks. Previously pending source-dependent abilities preserve last-known information if their source leaves during those checks.

Tests include three consecutive death batches, delayed trigger placement and resolution, anthem removal, zero toughness versus indestructible, temporary mid-resolution zero toughness, and cleanup. Full-deck replay results are recorded separately; a replay need not naturally encounter each tested mechanic.

Scope remains limited: this is creature death processing, not all of rule 704. Planeswalker loyalty, legend choices, regeneration, replacement/prevention effects and full attachment legality remain unfinished. Cleanup priority is still a simplified single window rather than the full repeating cleanup procedure. No additional original blocked card is declared fully resolved by this change. The original queue remains 12 completely blocked cards plus Goblin Chainwhirler's unsupported planeswalker portion. Live Minecraft golem integration is unchanged.

Reference: Wizards Comprehensive Rules 704.3, 704.5f–h, https://media.wizards.com/2026/downloads/MagicCompRules%2020260619.pdf
