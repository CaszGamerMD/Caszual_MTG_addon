# Equipment and creature Auras

Whole-text attachment programs compose keyword grants and fixed stat bonuses with either Equip generic costs or Enchant creature. No card names select behavior. Basilisk Collar and Lifelink now import as equipment and Aura, respectively. Keywords are computed through the attached source, rather than copied permanently onto the recipient.

Casting equipment uses the spell stack and enters unattached. Equip is activated only during its controller's main phase with priority and an empty stack. Costs are paid at activation, then attachment waits for both players to pass. Resolution requires the same equipment and a creature its controller controls to remain present. Equipment stays on the battlefield unattached when its creature leaves. The automated policy only offers unattached equipment to prevent repeated re-equip oscillation; the explicit API supports legal re-equipping.

Aura spells choose an existing creature on casting and check the same target on resolution. If it is gone the Aura goes to the graveyard without entering. A resolved Aura grants its abilities to that creature and goes to the graveyard if the creature leaves or becomes an illegal noncreature after cleanup (for example, an animated Vehicle). Equipment detaches in that case. Bulk destruction avoids moving an Aura twice when it and its creature are affected together.

This is diagnostic support. Protection, hexproof/ward targeting restrictions, Bestow, general control changes, copied Aura spells, and arbitrary additional Equipment abilities remain unsupported. Full state-based-action processing beyond the current attachment departure/cleanup paths is still pending. Unsupported remainder rejects the entire program.

Rules reference: Wizards keyword glossary, Equip/Enchant: https://magic.wizards.com/en/keyword-glossary

Validation: 148 tests pass. The seed-1142 real-deck replay completed without runtime questions and cast Basilisk Collar. Focused tests directly verify equip payment and delayed keyword grants, equipment detachment, Aura target loss, Aura cleanup, and rejection of unsupported remainder. The same-seed replay now casts ten spells; thirteen original cards remain unresolved even though only ten were encountered as unsupported in this altered replay. Summary: `training/examples/attachments-1142.json`.
