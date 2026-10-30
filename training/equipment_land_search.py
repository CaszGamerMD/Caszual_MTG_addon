"""Whole-text equipped-attacker optional basic-land search with Equipment grants."""
from attachments import parse as parse_attachment

SEARCH='Whenever equipped creature attacks, you may search your library for a basic land card, put it onto the battlefield tapped, then shuffle.'


def parse(text, types, subtypes):
    if 'Artifact' not in types or 'Equipment' not in subtypes:
        return ()
    lines=[line.strip() for line in text.splitlines()]
    living=bool(lines and lines[0]=='Living weapon')
    if living:lines=lines[1:]
    if lines.count(SEARCH)!=1:
        return ()
    rest=[line for line in lines if line!=SEARCH]
    attachment=parse_attachment('\n'.join(rest),types,subtypes)
    return (attachment,living) if attachment else ()
