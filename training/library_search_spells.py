"""Whole-Oracle compositional library search spells.

No card-name whitelists: search, reveal, shuffle, place, random discard are
separate ordered steps. Fail closed on unmatched additional effects.
Search selection is deliberately deterministic; the library remains private
to its owner and all shuffle/discard operations use local seeded RNG.
"""
from dataclasses import dataclass
import random
import re

_COLORS={'white':'White','blue':'Blue','black':'Black','red':'Red','green':'Green'}
_TUTOR=re.compile(
    r'Search your library for a (?:(white|blue|black|red|green) )?'
    r'(creature|artifact|enchantment|land) card, reveal it, '
    r'then shuffle and put the card on top\.'
)
_GAMBLE=re.compile(
    r'Search your library for a card, put that card into your hand, '
    r'discard a card at random, then shuffle\.'
)

@dataclass(frozen=True)
class LibrarySearchProgram:
    selector: str
    color: str = ''
    steps: tuple[str,...] = ()

def compile_card(oracle, types):
    if types not in (['Instant'],['Sorcery']) or not isinstance(oracle,str):
        return None
    match=_TUTOR.fullmatch(oracle)
    if match:
        return LibrarySearchProgram(match[2].title(),
            _COLORS.get(match[1],''),('search','reveal','shuffle','put_top'))
    if _GAMBLE.fullmatch(oracle):
        return LibrarySearchProgram('Any','',
                                    ('search','put_hand','discard_random','shuffle'))
    return None

def matching(card,program):
    if program.selector=='Any':
        return True
    types=set(card.printed_types)
    if card.kind=='creature':types.add('Creature')
    if program.selector not in types:
        return False
    return not program.color or program.color in card.colors

def resolve(sim,seat,source,program):
    if not isinstance(program,LibrarySearchProgram):
        raise RuntimeError('Library search lacks compiled instructions')
    player=sim.players[seat]
    found=None
    # The selected card is momentarily in transit between zones. Log only
    # after placement so the simulator's per-event conservation invariant
    # still runs without weakening its checks.
    messages=[]
    def emit(kind,message,**details):
        messages.append((kind,message,details))
    for step in program.steps:
        if step=='search':
            matches=[c for c in player.library if matching(c,program)]
            # Documented deterministic agent choice, not a named-card shortcut.
            found=min(matches,key=lambda c:c.id) if matches else None
            if found is not None:player.library.remove(found)
            emit('library_search','Search a private library for a matching card.',
                    actor=seat,source=source.name,selector=program.selector,
                    found=bool(found))
        elif step=='reveal':
            if found is not None:
                emit('search_reveal','Reveal searched card.',
                        actor=seat,source=source.name,card=found.name)
        elif step=='shuffle':
            sim.library_random_sequence+=1
            random.Random(f'{sim.seed}:library:{sim.library_random_sequence}').shuffle(player.library)
            emit('library_shuffle','Shuffle library following search.',
                    actor=seat,source=source.name)
        elif step=='put_top':
            if found is not None:
                player.library.append(found)  # Simulator draws from the end.
                emit('search_put_top','Put searched card on top of library.',
                        actor=seat,source=source.name,card=found.name)
        elif step=='put_hand':
            if found is not None:
                player.hand.append(found)
                emit('search_put_hand','Put searched card into hand.',
                        actor=seat,source=source.name)
        elif step=='discard_random':
            if player.hand:
                sim.library_random_sequence+=1
                index=random.Random(
                    f'{sim.seed}:random-discard:{sim.library_random_sequence}'
                ).randrange(len(player.hand))
                card=player.hand.pop(index)
                player.graveyard.append(card)
                emit('random_discard','Discard a randomly selected card from hand.',
                        actor=seat,source=source.name,card=card.name)
        else:
            raise RuntimeError('Unsupported library search instruction: '+step)
    if found is not None and found not in (
            player.hand+player.library+player.graveyard+player.exile
            +[p.card for p in player.battlefield]):
        raise RuntimeError('Searched card lost during resolution')
    for kind,message,details in messages:
        sim.log(kind,message,**details)
