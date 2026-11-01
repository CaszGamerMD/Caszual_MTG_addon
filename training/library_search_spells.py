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
    r'Search your library for an? (?:(white|blue|black|red|green) )?'
    r'(creature|artifact|enchantment|land) card, reveal it, '
    r'then shuffle and put the card on top\.'
)
_GAMBLE=re.compile(
    r'Search your library for a card, put that card into your hand, '
    r'discard a card at random, then shuffle\.'
)
_BATTLEFIELD=re.compile(
    r'Search your library for an? (?:(white|blue|black|red|green) )?'
    r'(creature|artifact|enchantment|land) card, '
    r'(reveal it, )?put it onto the battlefield, then shuffle\.'
)
_ADDITIONAL_SACRIFICE=re.compile(
    r'As an additional cost to cast this spell, sacrifice an? '
    r'(?:(white|blue|black|red|green) )?'
    r'(creature|artifact|enchantment)\.'
)
_X_BATTLEFIELD=re.compile(
    r'Search your library for an? (?:(white|blue|black|red|green) )?'
    r'(creature|artifact|enchantment|land) card with mana value X or less, '
    r'put it onto the battlefield, then shuffle\. '
    r'Shuffle (.+?) into its owner\'s library\.'
)

@dataclass(frozen=True)
class SacrificeCost:
    permanent_type: str
    color: str = ''

    def __post_init__(self):
        if self.permanent_type not in ('Creature','Artifact','Enchantment') or self.color not in ('','White','Blue','Black','Red','Green'):
            raise ValueError('Unimplemented sacrifice cost')

    def eligible_ids(self,game,controller):
        return tuple(state.id for state in game.battlefield.values()
                     if state.controller==controller
                     and (game.creature(state) if self.permanent_type=='Creature'
                          else self.permanent_type in state.definition.types)
                     and (not self.color or self.color in state.definition.colors))

@dataclass(frozen=True)
class LibrarySearchProgram:
    selector: str
    color: str = ''
    steps: tuple[str,...] = ()
    additional_cost: SacrificeCost | None = None
    mana_value_limit_x: bool = False
    shuffle_self: bool = False

def compile_card(oracle, types, name=''):
    if types not in (['Instant'],['Sorcery']) or not isinstance(oracle,str):
        return None
    cost=None
    lines=oracle.splitlines()
    if len(lines)==2:
        required=_ADDITIONAL_SACRIFICE.fullmatch(lines[0])
        if required is None:return None
        cost=SacrificeCost(required[2].title(),_COLORS.get(required[1],''))
        oracle=lines[1]
    elif len(lines)!=1:return None
    match=_X_BATTLEFIELD.fullmatch(oracle)
    if match and match[3] in (name,'this spell'):
        if cost is not None:return None  # X search + extra cost is not yet compiled.
        return LibrarySearchProgram(match[2].title(),_COLORS.get(match[1],''),
            ('search','put_battlefield','shuffle','shuffle_self'),
            mana_value_limit_x=True,shuffle_self=True)
    match=_TUTOR.fullmatch(oracle)
    if match:
        return LibrarySearchProgram(match[2].title(),
            _COLORS.get(match[1],''),('search','reveal','shuffle','put_top'),cost)
    if _GAMBLE.fullmatch(oracle):
        return LibrarySearchProgram('Any','',
                                    ('search','put_hand','discard_random','shuffle'),cost)
    match=_BATTLEFIELD.fullmatch(oracle)
    if match:
        return LibrarySearchProgram(match[2].title(),_COLORS.get(match[1],''),
            ('search',)+(('reveal',) if match[3] else ())+('put_battlefield','shuffle'),cost)
    return None

def matching(card,program,x=None):
    if program.selector=='Any':
        return True
    types=set(card.printed_types)
    if card.kind=='creature':types.add('Creature')
    if program.selector not in types:
        return False
    return ((not program.color or program.color in card.colors)
            and (not program.mana_value_limit_x or
                 card.printed_mana_value is not None and card.printed_mana_value<=x))

def resolve(sim,seat,source,program,x=None,copy=False):
    if not isinstance(program,LibrarySearchProgram):
        raise RuntimeError('Library search lacks compiled instructions')
    if program.mana_value_limit_x and (type(x) is not int or not 0<=x<=1000):
        raise RuntimeError('Missing or invalid bound X for library search')
    player=sim.players[seat]
    found=None
    battlefield_triggers=[]
    # The selected card is momentarily in transit between zones. Log only
    # after placement so the simulator's per-event conservation invariant
    # still runs without weakening its checks.
    messages=[]
    def emit(kind,message,**details):
        messages.append((kind,message,details))
    for step in program.steps:
        if step=='search':
            matches=[c for c in player.library if matching(c,program,x)]
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
        elif step=='put_battlefield':
            if found is not None:
                battlefield_triggers.extend(sim.enter_creature(found,player))
                emit('search_put_battlefield','Put searched permanent onto battlefield.',
                        actor=seat,source=source.name,card=found.name)
        elif step=='shuffle_self':
            if not program.shuffle_self:raise RuntimeError('Self-shuffle step lacks verified program')
            if not copy:
                graveyard=next((p.graveyard for p in sim.players if source in p.graveyard),None)
                if graveyard is None:raise RuntimeError('Resolving spell is missing from graveyard')
                graveyard.remove(source)
                owner=sim.card_owners.get(source.physical_id or source.id,seat)
                library=sim.players[owner].library
                library.append(source)
                sim.library_random_sequence+=1
                random.Random(f'{sim.seed}:library:{sim.library_random_sequence}').shuffle(library)
                emit('search_shuffle_self','Shuffle resolving spell into owner library.',
                     actor=seat,source=source.name,owner=owner)
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
    # Entry triggers wait until the entire spell (including its shuffle)
    # finishes instead of interrupting the written sequence.
    if battlefield_triggers:
        sim.resolve_entry_triggers(battlefield_triggers,source)
