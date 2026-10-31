"""LLM Oracle analysis stays complete, evidence-backed, and non-executable."""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import oracle_semantic_reader as semantic
import oracle_semantic_batch as batch


def card(name,text,**kw):
    return dict(name=name,layout='normal',oracleText=text,types=['Sorcery'],**kw)


def operation(verb,evidence,amount='',recipient='',subject='',obj='',qualifier=''):
    return dict(verb=verb,evidence=evidence,amount=amount,recipient=recipient,
                subject=subject,object=obj,qualifier=qualifier)


def proposal(raw,ops=None,needs=(),category='spell_effect'):
    lines=semantic.oracle_units(raw)
    return dict(units=[dict(face_index=unit.face_index,line_index=unit.line_index,
        source=unit.source,category=category,timing='',cost='',
        operations=([operation('other',unit.source)] if ops is None else ops[i]),
        needs=list(needs),explanation='Candidate only') for i,unit in enumerate(lines)],
        summary='Unverified proposed interpretation',uncertainties=[])


class SemanticReaderTests(unittest.TestCase):
    def test_unseen_attack_linked_mill_is_understood_without_executor_promotion(self):
        raw=dict(name='Unfamiliar attacker',layout='normal',types=['Creature'],
                 oracleText='Whenever this creature attacks, mill two cards. For each creature card '
                            'milled this way, create a 1/1 green Saproling creature token.')
        ops=[[operation('mill','mill two cards',amount='two',recipient='you'),
              operation('create_token','create a 1/1 green Saproling creature token',
                        amount='for each creature card milled this way')]]
        candidate=proposal(raw,ops,('trigger_attack','linked_effect_count','token_creation'),
                           category='triggered')
        result=semantic.report([raw],[candidate],executable=[False])
        self.assertEqual(result['cards'][0]['executableDiagnostic'],False)
        self.assertEqual(result['proposalChecked'],1)
        self.assertEqual(result['proposalRejected'],0)
        self.assertFalse(result['cards'][0]['semanticAccuracyVerified'])
        self.assertFalse(result['learningEligible'])
        self.assertEqual([x['verb'] for x in result['cards'][0]['units'][0]['operations']],
                         ['mill','create_token'])
        self.assertEqual([x['capability'] for x in result['capabilities']],
                         ['linked_effect_count','token_creation','trigger_attack'])

    def test_reworded_cards_share_capabilities_without_name_dispatch(self):
        a=card('One name','You draw two cards and lose 2 life.')
        b=card('A completely different name','You draw two cards and lose 2 life.')
        self.assertEqual(semantic.fingerprint(a),semantic.fingerprint(b))
        self.assertEqual(semantic.model_input(a)['units'],semantic.model_input(b)['units'])
        self.assertNotEqual(semantic.model_input(a)['faces'][0]['name'],
                            semantic.model_input(b)['faces'][0]['name'])
        ops=[[operation('draw','draw two cards',amount='two'),
              operation('lose_life','lose 2 life',amount='2')]]
        frames=[proposal(x,ops,('stack_resolution',)) for x in (a,b)]
        result=semantic.report([a,b],frames,executable=[False,False])
        self.assertEqual(result['capabilities'][0]['cardCount'],2)
        self.assertEqual(result['capabilities'][0]['unsupportedDiagnosticCards'],2)
        self.assertEqual(result['capabilities'][0]['capability'],'stack_resolution')

    def test_modals_and_bifacial_cards_require_every_face_and_bullet(self):
        split=dict(name='Unknown split spell',layout='split',
                   faces=[dict(text='Target creature gains deathtouch until end of turn.'),
                          dict(text='Destroy target artifact, creature, or enchantment.')])
        units=semantic.oracle_units(split)
        self.assertEqual([(u.face_index,u.line_index) for u in units],[(0,0),(1,0)])
        self.assertEqual(len(semantic.validate_proposal(split,proposal(split))['units']),2)
        modal=card('Unfamiliar selection','Choose one —\n• Draw a card.\n• Gain 2 life.')
        candidate=proposal(modal)
        candidate['units'][0]['category']='modal_header'
        candidate['units'][0]['operations']=[]
        self.assertEqual(len(semantic.validate_proposal(modal,candidate)['units']),3)

    def test_missing_line_or_fabricated_effect_fails_closed(self):
        raw=card('Unknown','Draw two cards.\nScry 2.')
        valid=proposal(raw)
        self.assertEqual(len(semantic.validate_proposal(raw,valid)['units']),2)
        missing=proposal(raw);missing['units'].pop()
        with self.assertRaisesRegex(semantic.SemanticProposalError,'omitted'):
            semantic.validate_proposal(raw,missing)
        changed=proposal(raw);changed['units'][1]['source']='Surveil 2.'
        with self.assertRaisesRegex(semantic.SemanticProposalError,'Source evidence'):
            semantic.validate_proposal(raw,changed)
        hallucinated=proposal(raw);hallucinated['units'][0]['operations']=[
            operation('deal_damage','Draw two cards.')]
        with self.assertRaisesRegex(semantic.SemanticProposalError,'not grounded'):
            semantic.validate_proposal(raw,hallucinated)
        forged=proposal(raw);forged['units'][0]['operations']=[
            operation('draw','Draw 200 cards')]
        with self.assertRaisesRegex(semantic.SemanticProposalError,'exact source'):
            semantic.validate_proposal(raw,forged)
        bad_amount=proposal(raw);bad_amount['units'][0]['operations']=[
            operation('draw','Draw two cards',amount='200')]
        with self.assertRaisesRegex(semantic.SemanticProposalError,'amount'):
            semantic.validate_proposal(raw,bad_amount)
        valid_amount=proposal(raw);valid_amount['units'][0]['operations']=[
            operation('draw','Draw two cards',amount='2')]
        self.assertIs(semantic.validate_proposal(raw,valid_amount),valid_amount)

    def test_missing_second_sentence_or_coordinated_verb_is_rejected(self):
        attack=dict(name='Unknown attacker',layout='normal',
            oracleText='Whenever this creature attacks, mill two cards. '
                       'For each creature card milled this way, create a 1/1 green Saproling creature token.')
        missing=proposal(attack,[[operation('mill','mill two cards')]])
        with self.assertRaisesRegex(semantic.SemanticProposalError,'instruction within'):
            semantic.validate_proposal(attack,missing)
        draw=card('Unknown exchange','You draw two cards and lose 2 life.')
        missing=proposal(draw,[[operation('draw','draw two cards')]])
        with self.assertRaisesRegex(semantic.SemanticProposalError,'instruction within'):
            semantic.validate_proposal(draw,missing)
        complete=proposal(draw,[[operation('draw','draw two cards'),
                                 operation('lose_life','lose 2 life')]])
        self.assertIs(semantic.validate_proposal(draw,complete),complete)
        self.assertEqual(len(semantic.instruction_clauses(attack['oracleText'])),2)
        self.assertEqual(len(semantic.instruction_clauses(draw['oracleText'])),2)

    def test_unknown_operations_are_explicit_not_dropped(self):
        raw=card('Unfamiliar','You win the game if you control seven Mountains.')
        candidate=proposal(raw)
        candidate['units'][0]['needs']=['unknown']
        candidate['units'][0]['operations']=[operation('other',raw['oracleText'])]
        self.assertIs(semantic.validate_proposal(raw,candidate),candidate)
        candidate['units'][0]['operations']=[]
        with self.assertRaisesRegex(semantic.SemanticProposalError,'no accounted-for'):
            semantic.validate_proposal(raw,candidate)

    def test_api_opt_in_no_key_and_mocked_strict_json_schema(self):
        raw=card('Any name','Draw two cards.')
        candidate=proposal(raw)
        with self.assertRaisesRegex(RuntimeError,'not configured'):
            semantic.request_model(raw,model='example-model',api_key='')
        seen=[]
        def transport(payload,key):
            seen.append((payload,key))
            return dict(status='completed',output=[dict(type='message',content=[
                dict(type='output_text',text=json.dumps(candidate))])])
        actual=semantic.request_model(raw,model='example-model',api_key='test-only',
                                      transport=transport)
        self.assertEqual(actual,candidate)
        self.assertEqual(seen[0][0]['text']['format']['type'],'json_schema')
        self.assertEqual(seen[0][0]['text']['format']['strict'],True)
        self.assertIs(seen[0][0]['store'],False)
        self.assertNotIn('test-only',json.dumps(seen[0][0]))
        self.assertEqual(seen[0][1],'test-only')

    def test_model_refusal_and_incomplete_output_do_not_persist(self):
        raw=card('Any','Scry 3.')
        for response in (
            dict(status='incomplete',output=[]),
            dict(status='completed',output=[dict(type='message',content=[dict(type='refusal',refusal='no')])]),
            dict(status='completed',output=[dict(type='message',content=[dict(type='output_text',text='{')])]),
        ):
            with self.subTest(response=response):
                with self.assertRaises(semantic.SemanticProposalError):
                    semantic.request_model(raw,model='test-model',api_key='test-only',
                                           transport=lambda body,key:response)

    def test_batch_real_random_input_keeps_all_oracle_faces_and_lines(self):
        path=Path(__file__).resolve().parents[1]/'reports/random-commander-exam-20261031/scryfall-source.json'
        if not path.exists():self.skipTest('Optional random Scryfall snapshot absent')
        cards=batch.load_cards(path)
        self.assertEqual(len(cards),15)
        units=sum(len(semantic.oracle_units(x)) for x in cards)
        self.assertEqual(units,33)
        split=next(x for x in cards if x['name']=='Status // Statue')
        self.assertEqual([u.face_index for u in semantic.oracle_units(split)],[0,1])
        # The batch transport can account for every instruction without
        # claiming that placeholder 'other' labels understood the cards.
        hypotheses=[]
        for source in cards:
            candidate=proposal(source)
            for unit in candidate['units']:
                unit['operations']=[operation('other',clause) for clause in
                                    semantic.instruction_clauses(unit['source'])]
            hypotheses.append(candidate)
        result=semantic.report(cards,hypotheses)
        self.assertEqual(result['proposalChecked'],15)
        self.assertEqual(result['sourceLines'],33)
        self.assertFalse(result['semanticAccuracyVerified'])


if __name__=='__main__':unittest.main()
