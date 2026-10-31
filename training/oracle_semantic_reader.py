"""LLM-assisted Oracle *comprehension*, strictly separate from rule execution.

An external model can propose a complete line-by-line semantic breakdown for
arbitrary unfamiliar cards. We verify source evidence and schema shape before
retaining it, but model interpretations are ALWAYS untrusted hypotheses:
neither an approved proposal nor a high coverage score grants legal actions.

No model is contacted unless the caller explicitly invokes `request_model`.
The game engine deliberately does not import this module.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass
import hashlib
import json
import os
import re
from urllib.request import Request, urlopen


CATEGORIES = ('triggered', 'activated', 'static', 'replacement', 'keyword',
              'spell_effect', 'modal_header', 'modal_option', 'restriction',
              'cost', 'other')
VERBS = ('draw', 'lose_life', 'gain_life', 'mill', 'create_token',
         'move_zone', 'deal_damage', 'destroy', 'exile', 'counter', 'tap',
         'untap', 'modify_stats', 'grant_ability', 'search', 'choose',
         'scry', 'surveil', 'add_mana', 'sacrifice', 'discard',
         'look', 'play_permission', 'other')
CAPABILITIES = ('stack_resolution', 'trigger_attack', 'trigger_cast',
                'trigger_entry', 'trigger_death', 'trigger_upkeep',
                'trigger_discard', 'trigger_life_gain', 'activated_cost',
                'targeting', 'modal_choice', 'linked_effect_count',
                'token_creation', 'token_embedded_ability', 'static_modifier',
                'keyword_rule', 'ward', 'cycling', 'zone_movement',
                'topdeck_permission', 'conditional_effect', 'turn_duration',
                'replacement', 'unknown')

# Each operation cites the exact words it claims to interpret. This is a
# hallucination *check*, not a proof of correct Magic interpretation.
ANCHORS = {
    'draw': ('draw',), 'lose_life': ('lose', 'loses'),
    'gain_life': ('gain', 'gains'), 'mill': ('mill',),
    'create_token': ('create',), 'move_zone': ('put', 'return', 'move', 'exile'),
    'deal_damage': ('damage', 'deals'), 'destroy': ('destroy',),
    'exile': ('exile',), 'counter': ('counter',), 'tap': ('tap',),
    'untap': ('untap',), 'modify_stats': ('get ', 'gets ', '+', '-', 'power', 'toughness'),
    'grant_ability': ('have ', 'has ', 'gain', 'reach', 'flying', 'menace',
                      'trample', 'ward', 'prowess', 'deathtouch', 'vigilance',
                      'haste', 'first strike', 'double strike', 'fear', 'lifelink',
                      'hexproof', 'shroud', 'indestructible', 'defender',
                      'landwalk', 'plainswalk', 'islandwalk', 'swampwalk',
                      'mountainwalk', 'forestwalk', 'flash', 'protection'),
    'search': ('search',), 'choose': ('choose',), 'scry': ('scry',),
    'surveil': ('surveil',), 'add_mana': ('add ',), 'sacrifice': ('sacrifice',),
    'discard': ('discard',), 'look': ('look',),
    'play_permission': ('play ', 'cast '),
}
_NUMBER_WORDS = ('zero','one','two','three','four','five','six','seven',
                 'eight','nine','ten','eleven','twelve','thirteen','fourteen',
                 'fifteen','sixteen','seventeen','eighteen','nineteen','twenty')


def _amount_grounded(amount: str, source: str) -> bool:
    if not amount:return True
    if amount.casefold() in source.casefold():return True
    if amount.isdecimal():
        number=int(amount)
        if number<len(_NUMBER_WORDS):
            return re.search(r'\b'+_NUMBER_WORDS[number]+r'\b',source,re.I) is not None
    for number,word in enumerate(_NUMBER_WORDS):
        if amount.casefold()==word:
            return re.search(r'(?<!\d)'+str(number)+r'(?!\d)',source) is not None
    return False


def _object_schema(properties: dict) -> dict:
    return dict(type='object',properties=properties,
                required=list(properties),additionalProperties=False)


OP_SCHEMA = _object_schema(dict(
    verb=dict(type='string',enum=list(VERBS)),
    evidence=dict(type='string',description='Exact contiguous quotation from source line'),
    amount=dict(type='string',description='Quantity/expression as printed, or empty'),
    subject=dict(type='string',description='Actor or affected object, or empty'),
    recipient=dict(type='string',description='Recipient/target, or empty'),
    object=dict(type='string',description='The cards, permanents, tokens or zone involved'),
    qualifier=dict(type='string',description='Conditions or characteristics, or empty'),
))
UNIT_SCHEMA = _object_schema(dict(
    face_index=dict(type='integer'),
    line_index=dict(type='integer'),
    source=dict(type='string',description='Exact entire supplied Oracle line'),
    category=dict(type='string',enum=list(CATEGORIES)),
    timing=dict(type='string',description='Trigger or timing condition, if any'),
    cost=dict(type='string',description='Activation/alternate cost, if any'),
    operations=dict(type='array',items=OP_SCHEMA),
    needs=dict(type='array',items=dict(type='string',enum=list(CAPABILITIES))),
    explanation=dict(type='string',description='Plain English interpretation'),
))
SCHEMA = _object_schema(dict(
    units=dict(type='array',items=UNIT_SCHEMA),
    summary=dict(type='string'),
    uncertainties=dict(type='array',items=dict(type='string')),
))


@dataclass(frozen=True)
class OracleUnit:
    face_index: int
    line_index: int
    source: str


def oracle_units(card: dict) -> tuple[OracleUnit, ...]:
    """Keep each face and printed instruction distinct, even for split cards."""
    layout=card.get('layout','normal')
    faces=card.get('faces') or card.get('card_faces') or ()
    if layout in ('split','adventure','modal_dfc','transform','flip','meld') and faces:
        texts=[f.get('text') or f.get('oracle_text') or '' for f in faces]
    else:
        texts=[card.get('oracleText') or card.get('oracle_text') or '']
    result=[]
    for face_index,text in enumerate(texts):
        for index,line in enumerate(x.strip() for x in text.splitlines()):
            if line:result.append(OracleUnit(face_index,index,line))
    return tuple(result)


def fingerprint(card: dict) -> str:
    """Cache by Oracle program plus mechanical face context, never card name."""
    context=model_input(card)
    for face in context['faces']:face.pop('name',None)
    data=context
    return hashlib.sha256(json.dumps(data,sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def model_input(card: dict) -> dict:
    """Only public rules facts; names contextualize Oracle self-references."""
    layout=card.get('layout','normal')
    raw_faces=card.get('faces') or card.get('card_faces') or ()
    faces=raw_faces if layout in ('split','adventure','modal_dfc','transform','flip','meld') and raw_faces else [card]
    return dict(layout=card.get('layout','normal'),
                faces=[dict(name=face.get('name',card.get('name','')),
                            types=face.get('types',card.get('types',[])),
                            subtypes=face.get('subTypes',face.get('subtypes',[])),
                            cost=face.get('manaCost',face.get('mana_cost','')),
                            power=str(face.get('power','')),
                            toughness=str(face.get('toughness','')))
                       for face in faces],
                units=[asdict(unit) for unit in oracle_units(card)])


# Multi-instruction Oracle *lines* are common. Require evidence for every
# independent sentence and for coordinated verbs ("draw ... and lose ...").
# Parsing here is solely an omission check, not an executable rules parser.
_COORDINATED = re.compile(
    r'\s+and\s+(?=(?:(?:you|its controller|that player)\s+)?'
    r'(?:draws?|loses?|gains?|creates?|scrys?|surveils?|mills?|'
    r'exiles?|destroys?|deals?|puts?|has|have|searches?|'
    r'sacrifices?|taps?|untaps?|looks?|returns?|counters?|adds?)\b)',
    re.IGNORECASE)


def instruction_clauses(source: str) -> tuple[str, ...]:
    """Evidence spans expected from complete sentences and coordinated verbs."""
    sentences=[];start=0;depth=0;quoted=False
    for i,ch in enumerate(source):
        if ch=='"':quoted=not quoted
        elif ch=='(' and not quoted:depth+=1
        elif ch==')' and depth and not quoted:depth-=1
        elif ch=='.' and not quoted and not depth and i+1<len(source) and source[i+1].isspace():
            after=source[i+1:].lstrip()
            if after and after[0].isupper():
                sentences.append(source[start:i+1].strip())
                start=i+1
    sentences.append(source[start:].strip())
    parts=[]
    for sentence in sentences:
        parts.extend(piece.strip() for piece in _COORDINATED.split(sentence) if piece.strip())
    return tuple(parts)


INSTRUCTIONS = """You are an expert Magic: The Gathering Oracle-text reader.
Translate EACH supplied source line into a compositional semantic breakdown.
Keep face_index, line_index and source EXACTLY as supplied and in order.
List EVERY distinct instruction, including sequential, conditional, repeated,
linked ('this way'), replacement, keyword, modal, activated and triggered ones.
For each operation give an EXACT contiguous evidence quote from its source;
do not synthesize quotes. Explain quantities, targets, costs and timing.
Use 'other' and unknown capability when a mechanic does not fit the vocabulary.
Do not silently drop a line or an effect. Do not make a card-name exception.
Do not decide whether execution is implemented, legal, or safe; this is ONLY
a proposed interpretation, never permission to change a game state.
Output strictly according to the specified JSON schema."""


class SemanticProposalError(ValueError):
    pass


def validate_proposal(card: dict, proposed: dict) -> dict:
    """Reject omissions and fabricated evidence; never confer executability."""
    if not isinstance(proposed,dict) or set(proposed)!=set(SCHEMA['properties']):
        raise SemanticProposalError('Semantic response has missing or extra top-level keys')
    expected=oracle_units(card)
    actual=proposed['units']
    if not isinstance(actual,list) or len(actual)!=len(expected):
        raise SemanticProposalError('Oracle lines were omitted, duplicated or added')
    if not isinstance(proposed['summary'],str) or not isinstance(proposed['uncertainties'],list) or any(
            not isinstance(x,str) for x in proposed['uncertainties']):
        raise SemanticProposalError('Invalid semantic summary or uncertainties')
    for unit,source in zip(actual,expected):
        if not isinstance(unit,dict) or set(unit)!=set(UNIT_SCHEMA['properties']):
            raise SemanticProposalError('Malformed semantic unit')
        if (type(unit['face_index']) is not int or type(unit['line_index']) is not int
                or (unit['face_index'],unit['line_index'],unit['source']) !=
                (source.face_index,source.line_index,source.source)):
            raise SemanticProposalError('Source evidence does not match this Oracle face and line')
        if unit['category'] not in CATEGORIES:
            raise SemanticProposalError('Unknown semantic category')
        if any(not isinstance(unit[key],str) for key in ('timing','cost','explanation')):
            raise SemanticProposalError('Non-string timing, cost or explanation')
        needs=unit['needs']
        if not isinstance(needs,list) or any(x not in CAPABILITIES for x in needs):
            raise SemanticProposalError('Invalid capability vocabulary')
        ops=unit['operations']
        if not isinstance(ops,list) or (not ops and unit['category']!='modal_header'):
            raise SemanticProposalError('A semantic instruction has no accounted-for operation')
        for op in ops:
            if not isinstance(op,dict) or set(op)!=set(OP_SCHEMA['properties']):
                raise SemanticProposalError('Malformed operation')
            if op['verb'] not in VERBS or any(not isinstance(x,str) for x in op.values()):
                raise SemanticProposalError('Unknown operation or field type')
            evidence=op['evidence']
            if not evidence or evidence not in source.source:
                raise SemanticProposalError('Proposed operation lacks exact source evidence')
            if not _amount_grounded(op['amount'],source.source):
                raise SemanticProposalError('Proposed amount is not present in Oracle text')
            if op['verb'] in ANCHORS and not any(
                    word in evidence.casefold() for word in ANCHORS[op['verb']]):
                raise SemanticProposalError(
                    'Proposed operation is not grounded in its verb: '
                    f"{op['verb']} from {evidence[:160]!r} on line "
                    f"{source.face_index}:{source.line_index}")
        if unit['category']!='modal_header':
            for clause in instruction_clauses(source.source):
                if not any(op['evidence'] in clause for op in ops):
                    raise SemanticProposalError('An instruction within the Oracle line was omitted')
    # A validated proposal is still not certified correct, and never executable.
    return proposed


def report(cards: list[dict], proposals: list[dict | None],
           executable: list[bool] | None = None,
           failures: list[str | None] | None = None) -> dict:
    """Group validated mechanics; retain rejected cards without accepting guesses."""
    if (len(cards)!=len(proposals) or executable is not None and len(executable)!=len(cards)
            or failures is not None and len(failures)!=len(cards)):
        raise ValueError('One semantic proposal and diagnostic verdict are required per card')
    if failures is None:failures=[None]*len(cards)
    families=defaultdict(lambda:dict(cards=set(),unsupported=set(),lines=0,examples=[]))
    rows=[];checked=0
    for i,(card,candidate,problem) in enumerate(zip(cards,proposals,failures)):
        if candidate is None:
            if not problem:raise ValueError('Rejected card requires a rejection reason')
            rows.append(dict(card=card.get('name',''),fingerprint=fingerprint(card),
                semanticStatus='rejected-unverified',semanticAccuracyVerified=False,
                executableDiagnostic=executable[i] if executable is not None else None,
                units=[],summary='',uncertainties=[],rejectionReason=problem))
            continue
        if problem:raise ValueError('Accepted card cannot have a rejection reason')
        validate_proposal(card,candidate)
        checked+=1
        for unit in candidate['units']:
            for cap in set(unit['needs']):
                family=families[cap];family['cards'].add(i);family['lines']+=1
                if executable is not None and not executable[i]:
                    family['unsupported'].add(i)
                if len(family['examples'])<3:family['examples'].append(
                    dict(card=card.get('name',''),source=unit['source']))
        rows.append(dict(card=card.get('name',''),fingerprint=fingerprint(card),
            semanticStatus='model-proposal-evidence-checked',
            # Explicitly separate this from a correctness/legality score.
            semanticAccuracyVerified=False,
            executableDiagnostic=executable[i] if executable is not None else None,
            units=candidate['units'],summary=candidate['summary'],
            uncertainties=candidate['uncertainties']))
    clusters=[dict(capability=cap,cardCount=len(data['cards']),
                   unsupportedDiagnosticCards=(len(data['unsupported'])
                       if executable is not None else None),
                   lineCount=data['lines'],examples=data['examples'])
              for cap,data in families.items()]
    clusters.sort(key=lambda x:(-(x['unsupportedDiagnosticCards']
                if executable is not None else x['cardCount']),
                -x['cardCount'],x['capability']))
    return dict(schemaVersion=1,kind='oracle-semantic-proposals',
                totalCards=len(cards),sourceLines=sum(len(oracle_units(c)) for c in cards),
                proposalChecked=checked,proposalRejected=len(rows)-checked,
                semanticAccuracyVerified=False,
                learningEligible=False,
                notice=('Text-evidence validation is NOT semantic correctness, rules '
                        'compilation, or legal gameplay; model programs cannot execute.'),
                capabilities=clusters,cards=rows)


def request_model(card: dict, *, model: str, api_key: str | None = None,
                  transport=None) -> dict:
    """Explicit opt-in Responses request; never called during a game.

    `transport` is injectable for offline tests. Credential is never logged or
    placed in the report. No SDK dependency and no automatic retries/costs.
    """
    key=api_key if api_key is not None else os.environ.get('OPENAI_API_KEY','')
    if not key:
        raise RuntimeError('OPENAI_API_KEY is not configured; no model request sent')
    if not model or not isinstance(model,str):
        raise ValueError('Specify an explicit Responses model')
    payload=dict(model=model,instructions=INSTRUCTIONS,
                 input=json.dumps(model_input(card),ensure_ascii=False),
                 text=dict(format=dict(type='json_schema',name='mtg_oracle_semantics',
                                       strict=True,schema=SCHEMA)),
                 store=False)
    if transport is None:
        def transport(body,key):
            request=Request('https://api.openai.com/v1/responses',
                data=json.dumps(body).encode('utf-8'),method='POST',
                headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'})
            with urlopen(request,timeout=90) as response:
                return json.load(response)
    response=transport(payload,key)
    if not isinstance(response,dict) or response.get('status')!='completed':
        raise SemanticProposalError('Model response was not completed')
    contents=[content for item in response.get('output',[]) if item.get('type')=='message'
              for content in item.get('content',[])]
    if any(x.get('type')=='refusal' for x in contents):
        raise SemanticProposalError('Model refused; no semantic program available')
    texts=[x.get('text') for x in contents if x.get('type')=='output_text']
    if len(texts)!=1 or not isinstance(texts[0],str):
        raise SemanticProposalError('Model returned no single structured output')
    try:candidate=json.loads(texts[0])
    except json.JSONDecodeError as exc:
        raise SemanticProposalError('Model output was not valid JSON') from exc
    return validate_proposal(card,candidate)
