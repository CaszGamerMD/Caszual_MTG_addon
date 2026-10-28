import sys
from pathlib import Path
import json
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import mana_pool as m
import simulator as s

class ManaPoolChecks(unittest.TestCase):
    def test_colorless_generic_explicit_and_chosen_x(self):
        ring=[('ring',((0,0,0,0,0,2),))]
        for cost,x in [('{2}',None),('{C}{C}',None),('{X}',2),('{X}{X}',1)]:
            result=m.plan(cost,m.ZERO,ring,x)
            self.assertTrue(result['paid']);self.assertEqual(result['pool'],list(m.ZERO))
            self.assertEqual(result['sources'],['ring'])
        for cost,x in [('{U}',None),('{3}',None),('{X}',None),('{X}',-1),('{X}',True),('{WU}',None)]:
            self.assertFalse(m.plan(cost,m.ZERO,ring,x)['paid'])
        self.assertFalse(m.plan('{C}',(1,0,0,0,0,0),[])['paid'])

    def test_leftovers_and_failed_plans_do_not_mutate_inputs(self):
        pool=[0]*6;sources=[('ring',((0,0,0,0,0,2),))]
        result=m.plan('{1}',pool,sources)
        self.assertEqual(result['pool'],[0,0,0,0,0,1]);self.assertEqual(pool,[0]*6)
        second=m.plan('{C}',result['pool'],[])
        self.assertEqual(second['sources'],[]);self.assertEqual(second['pool'],[0]*6)
        self.assertFalse(m.plan('{U}',result['pool'],[])['paid'])
        self.assertEqual(result['pool'],[0,0,0,0,0,1])

    def test_production_consumes_whole_instruction(self):
        self.assertEqual(m.production('{T}: Add {C}{C}.'),(0,0,0,0,0,2))
        self.assertEqual(m.production('{T}: Add {U}{B}.'),(0,1,1,0,0,0))
        for text in ['{T}: Add {C}{C}. You lose 2 life.','{T}, Pay 1 life: Add {C}{C}.','{T}: Add {C}{C}. Spend this mana only to cast creatures.']:
            self.assertIsNone(m.production(text))

    def test_pool_planner_matches_shared_java_single_mana_rules(self):
        import itertools
        with s.RulesBridge() as rules:
            for masks in itertools.product((1,2,4,3,32),repeat=3):
                sources=[(str(i),tuple(tuple(int(j==c) for j in range(6)) for c in range(6) if mask&(1<<c))) for i,mask in enumerate(masks)]
                for cost in ('{W/U}{U/B}{1}','{C}{W}{1}'):
                    expected=rules.query('pay',cost,*[str(i)+':'+str(mask) for i,mask in enumerate(masks)])['paid']
                    self.assertEqual(m.plan(cost,m.ZERO,sources)['paid'],expected,(cost,masks))

    def test_land_decision_is_not_a_phase_boundary(self):
        with s.RulesBridge() as rules:
            sim=s.Simulator(rules,42,diagnostic=True)
            sim.phase='land';sim.players[0].mana_pool=[0,0,0,0,0,1]
            with patch.object(sim,'decide',return_value=s.Candidate('pass','pass')): sim.step()
            self.assertEqual(sim.phase,'main')
            self.assertEqual(sim.players[0].mana_pool,[0,0,0,0,0,1])

    def test_real_ring_cast_use_leftover_then_empty_at_boundary(self):
        with s.RulesBridge() as rules:
            deck=json.loads((Path(__file__).resolve().parents[1]/'decks/5254666-garbo-gobbos.json').read_text())
            raw=next(c for c in deck['mainboard'] if c['name']=='Sol Ring')
            ring=s.import_diagnostic_card(rules,raw,0,'ring',{'Red'})
            self.assertEqual(ring.kind,'mana_artifact')
            # Unfamiliar card names use the identical Oracle production grammar.
            other=s.import_diagnostic_card(rules,dict(raw,name='Unfamiliar mana stone'),0,'other',{'Red'})
            self.assertEqual(other.mana_production,ring.mana_production)
            land=s.Card('land','Wastes','land',mask=32)
            spells=[s.Card('spell'+str(i),'Draw','spell',mana_cost='{1}',draw=1) for i in range(2)]
            sim=s.Simulator(rules,42,decks=(s.demo_deck(0)+[ring,land]+spells,s.demo_deck(1)),diagnostic=True)
            p=sim.players[0]
            for card in [ring,land]+spells:
                (p.hand if card in p.hand else p.library).remove(card)
            p.hand.extend([ring]+spells);p.battlefield.append(s.Permanent(land));sim.phase='main'
            def cast(card):
                with patch.object(sim,'decide',return_value=s.Candidate('cast','cast',card_id=card.id)): sim.step()
            cast(ring)
            self.assertTrue(p.battlefield[0].tapped)
            self.assertTrue(any(x.card==ring and not x.tapped and x.fresh for x in p.battlefield))
            cast(spells[0]);self.assertEqual(p.mana_pool,[0,0,0,0,0,1])
            self.assertEqual(sim.payment(spells[1])['sources'],[])
            cast(spells[1]);self.assertEqual(p.mana_pool,[0]*6)
            self.assertFalse(sim.payment(spells[1])['paid'])
            p.mana_pool=[0,0,0,0,0,1]
            with patch.object(sim,'decide',return_value=s.Candidate('pass','pass')): sim.step()
            self.assertEqual(p.mana_pool,[0]*6)
            self.assertTrue(any(e['kind']=='mana_empty' for e in sim.events))
            sim.invariant()
