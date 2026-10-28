import sys,json,unittest
from pathlib import Path
from dataclasses import replace
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
from oracle_abilities import parse_token_creation

class LandTokenChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.rules=s.RulesBridge()
    @classmethod
    def tearDownClass(cls): cls.rules.close()

    def fixture(self):
        deck=json.loads((Path(__file__).resolve().parents[1]/'decks/8321184-squirrels.json').read_text())
        raw=next(c for c in deck['mainboard'] if c['name']=='Awaken the Woods')
        card=s.import_diagnostic_card(self.rules,raw,0,'awaken',{'Green'})
        self.assertEqual(card.kind,'x_spell')
        lands=[s.Card('forest'+str(i),'Forest','land',mask=16) for i in range(4)]
        sim=s.Simulator(self.rules,42,decks=(s.demo_deck(0)+[card]+lands,s.demo_deck(1)),diagnostic=True)
        p=sim.players[0]
        for c in [card]+lands: (p.hand if c in p.hand else p.library).remove(c)
        p.hand.append(card);p.battlefield.extend(s.Permanent(c) for c in lands);sim.phase='main'
        choice=next(a for a in sim.legal(0) if a.card_id==card.id and a.x_value==2)
        with patch.object(sim,'decide',return_value=choice): sim.step()
        return sim,[p for p in p.battlefield if p.card.is_token]

    def test_awaken_tokens_are_lands_and_creatures_but_not_basic(self):
        sim,tokens=self.fixture()
        self.assertEqual(len(tokens),2)
        for token in tokens:
            self.assertEqual(token.card.event_definition.types,frozenset({'Land','Creature'}))
            self.assertEqual(token.card.event_definition.subtypes,frozenset({'Forest','Dryad'}))
            self.assertFalse(token.card.basic_land)
            self.assertEqual(sim.effective_card(token).traits,'1;1;')
        self.assertFalse(sim.payment(s.Card('cost','Cost','spell',mana_cost='{G}'))['paid'])
        sim.phase='attack'
        self.assertFalse(any(a.kind=='attack' and a.card_id in {p.card.id for p in tokens} for a in sim.legal(0)))
        sim.invariant()

    def test_next_controller_turn_enables_mana_and_spending_taps_token(self):
        sim,tokens=self.fixture()
        sim.active=1;sim.phase='end';sim.step()  # Controller's next untap.
        self.assertTrue(all(not p.fresh for p in tokens))
        for p in sim.players[0].battlefield:
            if not p.card.is_token: p.tapped=True
        cost=s.Card('cost','Cost','spell',mana_cost='{G}{G}')
        self.assertEqual(set(sim.payment(cost)['sources']),{p.card.id for p in tokens})
        removed=sim.players[0].library.pop()
        cost=replace(cost,id=removed.id,draw=1)
        sim.players[0].hand.append(cost);sim.phase='main'
        with patch.object(sim,'decide',return_value=s.Candidate(cost.id,'cast',card_id=cost.id)): sim.step()
        self.assertTrue(all(p.tapped for p in tokens))
        self.assertFalse(sim.payment(cost)['paid'])
        sim.send_to_destination(sim.players[0],tokens[1])
        self.assertFalse(sim.payment(replace(cost,mana_cost='{G}'))['paid'])
        sim.invariant()

    def test_haste_and_basic_land_type_determine_available_mana(self):
        sim,tokens=self.fixture()
        first=tokens[0]
        first.card=replace(first.card,event_definition=replace(first.card.event_definition,abilities=frozenset({'haste'})))
        self.assertEqual(sim.payment(s.Card('cost','Cost','spell',mana_cost='{G}'))['sources'],[first.card.id])
        self.assertFalse(sim.payment(s.Card('cost','Cost','spell',mana_cost='{U}'))['paid'])
        first.card=replace(first.card,event_definition=replace(first.card.event_definition,subtypes=frozenset({'Island','Dryad'})))
        self.assertTrue(sim.payment(s.Card('cost','Cost','spell',mana_cost='{U}'))['paid'])
        self.assertFalse(sim.payment(s.Card('cost','Cost','spell',mana_cost='{G}'))['paid'])

    def test_token_grammar_preserves_land_type_and_keywords(self):
        token=parse_token_creation('Create two tapped 2/2 blue Island Spirit land creature tokens with flying.')
        self.assertTrue(token.land);self.assertTrue(token.tapped)
        self.assertEqual(token.keywords,frozenset({'flying'}))
        ordinary=parse_token_creation('Create a 1/1 green Dryad creature token.')
        self.assertFalse(ordinary.land)
