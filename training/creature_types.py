"""Creature-type membership for characteristic-defining changeling abilities.

A changeling is every *creature* type in all zones, not every land,
artifact or enchantment subtype. The caller still checks whether the
object is a creature when a rule asks for a creature permanent.
"""

# Noncreature subtypes must never be inferred from changeling. This list
# is intentionally a denylist only for the wildcard: printed membership
# still works for cards of these types.
NONCREATURE_SUBTYPES = frozenset({
    'Plains','Island','Swamp','Mountain','Forest','Cave','Desert','Gate','Lair','Locus','Mine','Power-Plant','Tower',"Urza's",
    'Aura','Cartouche','Class','Curse','Rune','Saga','Shard','Shrine','Role','Room','Case','Background',
    'Equipment','Vehicle','Fortification','Clue','Food','Treasure','Blood','Gold','Map','Powerstone',
    'Attraction','Contraption','Bobblehead','Junk','Spacecraft','Kindred','Lesson','Arcane','Trap',
})


def has_subtype(definition, subtype: str) -> bool:
    if subtype in definition.subtypes:
        return True
    return (bool(subtype) and subtype not in NONCREATURE_SUBTYPES
            and 'Creature' in definition.types
            and 'changeling' in definition.abilities)


def has_any_subtype(definition, subtypes) -> bool:
    return any(has_subtype(definition, subtype) for subtype in subtypes)


def shares_creature_type(first, second) -> bool:
    if 'Creature' not in first.types or 'Creature' not in second.types:
        return False
    # A changeling shares every actual creature type, even with another
    # changeling. The printed Shapeshifter subtype also remains present.
    return (has_any_subtype(first, second.subtypes) or
            has_any_subtype(second, first.subtypes))


def card_has_subtype(card, subtype: str) -> bool:
    return (subtype in card.land_subtypes or
            bool(card.event_definition and has_subtype(card.event_definition,subtype)))
