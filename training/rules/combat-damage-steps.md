# Separate strike damage steps

Combats involving first strike or double strike now use explicit `first_damage` and `regular_damage` stages rather than the combined Java combat result. The first-step eligibility set is retained; regular damage is assigned by surviving creatures that lacked both strike abilities initially, plus creatures that currently have double strike. Current characteristics are read again each step.

Damage to creatures is marked between steps and removed at cleanup. Each step assigns damage simultaneously, discovers deaths against the pre-death battlefield, moves dying creatures together, checks player losses, then queues supported death/combat-damage triggers through the priority stack. Priority is offered after damage even if the stack is empty. Mana expires at the step boundary. The original blocking relationship remains: a blocked attacker whose blocker dies cannot damage the player without trample. Trample uses remaining lethal damage after previous marks and deathtouch, then may carry damage through a departed blocker. Lifelink and commander damage are applied separately each step. Zurgo's existing supported self-counter rule is retained on this path.

The earlier first-strike/death-trigger blocking question is removed for this single-attacker, single-blocker model. Normal non-strike combat still uses the Java helper. Full multiple-attacker combat, general damage replacement/prevention, regeneration, and comprehensive cascading state-based actions remain unfinished. This is diagnostic simulator work, not live golem integration.

Focused coverage includes: first-strike blocker death and token triggers before normal damage; double-strike trample through a dead blocker; staying blocked without trample; lethal first-step player damage preventing later triggers; persistent marks and cleanup. The historical stop test now verifies actual staged resolution instead of expecting a question. Validation and same-seed batch results are retained in `training/examples/strike-1342.json`.

Rules reference: Wizards glossary, first strike and double strike: https://magic.wizards.com/en/keyword-glossary and Comprehensive Rules 510.4.

Validation: 141 tests pass, including an automatic instant response in an empty-stack damage window. All six pairings at seeds 1342–1347 reached ten turns per player without runtime questions; seed 1346 previously stopped after three turns per player on the first-strike question.

## Deathtouch with trample

For trample assignment, any positive amount assigned by a deathtouch source counts as lethal. A 5/5 with both abilities blocked by a 6/6 can assign one to the blocker and four to the defending player. Zero damage never destroys through deathtouch. Indestructible does not require assigning full toughness; it prevents the resulting destruction. In a later damage step, a blocker already marked with lethal damage needs zero additional assigned damage, even if indestructible kept it alive. The staged path now preserves that zero requirement instead of unconditionally requiring another one for deathtouch.

Regression tests cover ordinary 5/5-versus-6/6 assignment, zero power, and a double-striking 5/5 against an indestructible 1/1: four damage tramples over in the first step and five in the second. Multiple blockers remain outside the simulator's current combat model.

Official ruling: https://magic.wizards.com/en/news/feature/foundations-release-notes
