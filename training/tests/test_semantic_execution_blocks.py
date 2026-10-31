"""Reusable effect blocks, with a hard boundary against model promotion."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from oracle_abilities import Effect, effect, parse_token_creation
from semantic_execution_blocks import (BlockCompilationError, compile_effects,
                                       inspect_semantic_proposal)
from semantic_block_audit import audit
from oracle_semantic_reader import report as semantic_report
from scryfall_random_exam import convert_scryfall


class SemanticExecutionBlocksChecks(unittest.TestCase):
    @staticmethod
    def source(number,oracle):
        return dict(object='card',id=f'printed-{number}',oracle_id=f'oracle-{number}',
            name=f'Unknown spell {number}',type_line='Sorcery',mana_cost='{1}{U}',
            oracle_text=oracle,colors=['U'],color_identity=['U'],
            games=['paper'],legalities=dict(commander='legal'),layout='normal')

    def test_compiled_ordered_effects_lower_to_existing_stack_handlers(self):
        compiled=effect('you draw two cards and lose 2 life.')
        self.assertEqual(compiled.operation,'ordered_effects')
        plan=compile_effects((compiled,))
        self.assertEqual([(b.operation,b.amount,b.recipient) for b in plan.blocks],
                         [('draw_cards',2,'controller'),('lose_life',2,'self')])
        event=plan.stack_event(controller=0,source='spell-1',name='Unseen exchange')
        self.assertEqual(event['operation'],'ordered_effects')
        self.assertEqual([s['operation'] for s in event['steps']],
                         ['draw_cards','lose_life'])
        self.assertNotIn('tokenSpec',event['steps'][0])

    def test_token_and_library_blocks_are_reusable_and_strict(self):
        token=parse_token_creation('Create two tapped 2/3 green Elk creature tokens with reach.')
        self.assertIsNotNone(token)
        plan=compile_effects((Effect('create_tokens',2,token=token),
                              Effect('surveil',2),Effect('scry',1),
                              Effect('mill_cards',3,'each opponent')))
        steps=plan.stack_event(controller=1,source='spell-2',name='Different spell')['steps']
        self.assertEqual(steps[0]['tokenSpec']['amount'],2)
        self.assertEqual(steps[0]['tokenSpec']['keywords'],['reach'])
        self.assertTrue(steps[0]['tokenSpec']['tapped'])
        self.assertEqual(steps[-1]['recipient'],'each opponent')

    def test_whole_program_fails_closed_if_one_step_is_unhandled(self):
        valid=Effect('draw_cards',2)
        bad=(Effect('destroy',1),Effect('lose_life',1,'target player'),
             Effect('draw_cards',2,optional=True),
             Effect('draw_cards',2,gain=1),Effect('draw_cards',0),
             Effect('draw_cards',True),Effect('create_tokens',2),
             Effect('gain_life',3,'each opponent'))
        for rejected in bad:
            with self.subTest(rejected=rejected):
                with self.assertRaises(BlockCompilationError):
                    compile_effects((valid,rejected,valid))

    def test_model_semantics_are_candidates_even_if_handler_exists(self):
        card=dict(name='Unknown Library Lesson',layout='normal',types=['Sorcery'],
                  oracleText='Draw two cards.\nYou win the game.')
        proposal=dict(units=[
            dict(face_index=0,line_index=0,source='Draw two cards.',
                 category='spell_effect',timing='',cost='',
                 operations=[dict(verb='draw',evidence='Draw two cards',amount='two',
                                  subject='you',recipient='you',object='cards',qualifier='')],
                 needs=['stack_resolution'],explanation='Draw cards'),
            dict(face_index=0,line_index=1,source='You win the game.',
                 category='spell_effect',timing='',cost='',
                 operations=[dict(verb='other',evidence='win the game',amount='',
                                  subject='you',recipient='',object='game',qualifier='')],
                 needs=['unknown'],explanation='Win the game')],
            summary='Unverified',uncertainties=[])
        report=inspect_semantic_proposal(card,proposal)
        self.assertFalse(report['executionReady'])
        self.assertFalse(report['approved'])
        self.assertFalse(report['learningEligible'])
        self.assertEqual(report['handlerCandidates'],1)
        self.assertEqual([x['candidateHandler'] for x in report['candidates']],
                         ['draw_cards',None])
        self.assertNotIn('steps',report)

    def test_forged_model_evidence_is_rejected_before_candidate_mapping(self):
        card=dict(name='Unknown',layout='normal',types=['Sorcery'],
                  oracleText='Draw a card.')
        proposal=dict(units=[dict(face_index=0,line_index=0,
            source='Draw a card.',category='spell_effect',timing='',cost='',
            operations=[dict(verb='destroy',evidence='Draw a card.',amount='',
                             subject='',recipient='',object='',qualifier='')],
            needs=['unknown'],explanation='Hallucinated removal')],
            summary='Incorrect',uncertainties=[])
        with self.assertRaises(ValueError):
            inspect_semantic_proposal(card,proposal)

    def test_counted_oracle_exposes_read_only_candidate_operands_not_execution(self):
        oracle='Draw a card for each creature you control.'
        card=dict(name='Unknown quantity',layout='normal',types=['Sorcery'],
                  oracleText=oracle)
        proposal=dict(units=[dict(face_index=0,line_index=0,source=oracle,
            category='spell_effect',timing='',cost='',operations=[dict(
                verb='draw',evidence='Draw a card',amount='a',subject='you',
                recipient='you',object='card',qualifier='for each creature you control')],
            needs=['stack_resolution'],explanation='Untrusted interpretation')],
            summary='Untrusted',uncertainties=[])
        report=inspect_semantic_proposal(card,proposal)
        self.assertEqual(report['candidateOperations'],1)
        self.assertEqual(report['handlerCandidates'],1)
        self.assertEqual(report['candidates'][0]['candidateCountOperand'],dict(
            relation='controller',cardType='Creature',subtype='',tapped=None,
            nontoken=False,factor=1))
        self.assertFalse(report['executionReady'])
        self.assertFalse(report['approved'])
        self.assertFalse(report['learningEligible'])

    def test_saved_report_audit_preserves_rejections_and_source_binding(self):
        sources=[self.source(1,'Draw a card.'),self.source(2,'Draw a card.')]
        cards=[convert_scryfall(source) for source in sources]
        candidate=dict(units=[dict(face_index=0,line_index=0,
            source='Draw a card.',category='spell_effect',timing='',cost='',
            operations=[dict(verb='draw',evidence='Draw a card',amount='a',
                             subject='you',recipient='you',object='card',qualifier='')],
            needs=['stack_resolution'],explanation='Draw one card')],
            summary='Unverified',uncertainties=[])
        semantic=semantic_report(cards,[candidate,None],
            executable=[False,False],failures=[None,'bad verb evidence'])
        result=audit(sources,semantic)
        self.assertEqual((result['evidenceCheckedCards'],result['rejectedCards']),(1,1))
        self.assertEqual(result['handlerCounts'],{'draw_cards':1})
        self.assertFalse(result['executionReady'])
        changed=[dict(s) for s in sources]
        changed[0]['oracle_text']='Exile a card.'
        with self.assertRaisesRegex(ValueError,'not bound'):
            audit(changed,semantic)


if __name__=='__main__':unittest.main()
