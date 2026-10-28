# Priority-stack foundation

The diagnostic now has a two-player LIFO stack with unique object IDs, priority ownership, consecutive passes, and one-object resolution. New actions reset pass counts. After resolution the active player regains priority. Two passes on an empty stack return an advance signal. A counter primitive removes a specific stack object without resolving it. Public stack metadata excludes effect payloads and private cards.

Supported entry/upkeep/death effects routed through the common trigger resolver are placed in APNAP controller order. Within a controller's batch the existing deterministic discovery resolution order is retained. Newly generated entry triggers wait until their parent effect finishes; they then sit above older pending objects. Mana abilities still bypass the stack. The game logs stack placement, passes, and resolution. Automated play passes automatically; manual-priority tests can hold resolution and alter the public game state. Turn stepping refuses to skip pending manual stack objects.

Krenko-style counter-then-power-token effects now defer both operations until resolution. A live source gets the counter first and its resulting current power determines the token count. If it leaves, departure records last-known power and resolution creates tokens without adding a counter to the departed source. Repeated/full and short Oracle self references still select no name-specific behavior.

Validation: 122 tests pass, covering LIFO order, two-pass requirements, wrong-player rejection, reset after a response, a countered object, empty-stack advance, APNAP placement, deferred Krenko resolution, and source removal with last-known power. Seed 1142 completed without runtime questions and recorded two stack placements, four priority passes, and two resolutions. Summary: `training/examples/stack-1142.json`.

## Still pending

This is an ability-stack foundation, not a complete stack implementation. Casting ordinary spells still resolves through the existing direct path; actual instant response actions, target validation, counterspell cards, full state-based-action loops, and first/double-strike damage windows remain unavailable. Some legacy attack triggers still execute immediately. The counter primitive is tested engine infrastructure, not a playable counterspell. Manual mode is a test/API mode and is not yet exposed as policy response choices. Live Minecraft actions are unchanged.

Rules reference: Wizards Comprehensive Rules 117.3b, 117.4, 405 and 603: https://media.wizards.com/2026/downloads/MagicCompRules%2020260619.pdf
