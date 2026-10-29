# Simultaneous opposing-board damage

A whole-text trigger grammar recognizes fixed damage to each opponent and each creature and planeswalker they control. Within the diagnostic's supported player/creature battlefield, damage is marked on every affected creature and deducted from opposing life together. Surviving creatures retain marks until cleanup; ordinary combat involving marked creatures now uses the staged damage path so earlier noncombat damage counts toward lethal damage.

Indestructible prevents damage-based destruction, not damage marking. Current source deathtouch/lifelink are used; supported source departure records last-known keyword state for the pending effect. Lifelink counts actual unprevented damage dealt to each supported recipient. Death discovery examines the pre-death battlefield, creatures leave together, player-loss checks occur before death triggers are queued, and resulting abilities resolve through the priority stack. The former destruction helper is shared with damage deaths while retaining distinct log kinds.

Goblin Chainwhirler imports with its First strike and complete trigger grammar. Pronoun “it” is normalized only for self-entry/death trigger subjects, avoiding interpretation as the wrong source in arbitrary watchers. Unparsed extra text rejects the entire card.

Limitations: the simulator does not yet import planeswalkers or track loyalty, so that part of Chainwhirler's text is not exercised or implemented. Damage prevention/replacement, protection, and comprehensive cascading state-based actions remain unfinished. This is diagnostic support only; live golem actions are unchanged.

Focused tests cover simultaneous Artist/Shambler deaths, nonlethal marks, indestructible, source removal, lethal player damage stopping later triggers, parsed amounts/keywords, and ordinary combat after prior noncombat damage.

Official reference: https://magic.wizards.com/en/news/feature/dominaria-release-notes

Validation: 152 tests pass, including last-known lifelink/deathtouch after source departure. The seed-1142 replay completed without runtime questions but did not resolve a board-damage effect, so focused tests supply direct coverage. Summary: `training/examples/boarddamage-1142.json`. Twelve original cards remain completely blocked; Chainwhirler is enabled for the diagnostic player/creature model with planeswalker handling still pending.

Follow-up: represented planeswalkers now lose loyalty to this instruction, zero-loyalty state-based actions ignore indestructible, and dual-type permanents are damaged once. See `ward-ability-loss-loyalty.md`. Arbitrary planeswalker abilities and attacks against planeswalkers remain unsupported.
