import sys,json,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
import x_spells

class XSpellChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.rules=s.RulesBridge()
    @classmethod
    def tearDownClass(cls): cls.rules.close()

    def fixture(self,raw):
        card=s.import_diagnostic_card(self.rules,raw,0,'variable',{'Red','Blue','Green'})
        self.assertEqual(card.kind,'x_spell')
        lands=[s.Card('land'+str(i),'Test land','land',mask=mask) for i,mask in enumerate((8,8,32,32,32))]
        sim=s.Simulator(self.rules,42,decks=(s.demo_deck(0)+[card]+lands,s.demo_deck(1)),diagnostic=True)
        p=sim.players[0]
        for c in [card]+lands: (p.hand if c in p.hand else p.library).remove(c)
        p.hand.append(card);p.battlefield.extend(s.Permanent(c) for c in lands);sim.phase='main'
        return sim,card

    def cast(self,sim,card,x):
        action=next(a for a in sim.legal(0) if a.card_id==card.id and a.x_value==x)
        with patch.object(sim,'decide',return_value=action): sim.step()
        sim.invariant()

    def test_real_goblin_offensive_fixed_cost_and_chosen_tokens(self):
        deck=json.loads((Path(__file__).resolve().parents[1]/'decks/5254666-garbo-gobbos.json').read_text())
        raw=next(c for c in deck['mainboard'] if c['name']=='Goblin Offensive')
        sim,card=self.fixture(raw)
        self.assertEqual([a.x_value for a in sim.legal(0) if a.card_id==card.id],[0,1,2])
        self.assertFalse(sim.payment(card,x=3)['paid'])
        self.cast(sim,card,2)
        tokens=[p for p in sim.players[0].battlefield if p.card.is_token]
        self.assertEqual(len(tokens),2)
        self.assertTrue(all(p.card.traits=='1;1;' for p in tokens))
        self.assertIn(card,sim.players[0].graveyard)
        event=next(e for e in sim.events if e['kind']=='cast')
        self.assertEqual(event['details']['xValue'],2)
        self.assertEqual(len(event['details']['manaSources']),5)

    def test_x_cast_uses_ring_and_keeps_surplus(self):
        sim,card=self.fixture(dict(name='Unknown brood',types=['Sorcery'],manaCost='{X}{1}{R}{R}',
                                   oracleText='Create X 1/1 red Goblin creature tokens.'))
        p=sim.players[0]
        original=p.battlefield[-1].card
        ring=s.import_diagnostic_card(self.rules,dict(name='Sol Ring',types=['Artifact'],manaCost='{1}',
              oracleText='{T}: Add {C}{C}.'),0,original.id,{'Red'})
        p.battlefield[-1].card=ring
        self.assertEqual([a.x_value for a in sim.legal(0) if a.card_id==card.id],[0,1,2,3])
        self.cast(sim,card,2)
        self.assertEqual(p.mana_pool,[0,0,0,0,0,1])
        self.assertTrue(p.battlefield[4].tapped)

    def test_zero_creates_no_tokens_but_pays_fixed_cost(self):
        sim,card=self.fixture(dict(name='Unknown brood',types=['Sorcery'],manaCost='{X}{R}',oracleText='Create X 2/3 blue Drake creature tokens with flying.'))
        self.cast(sim,card,0)
        self.assertFalse(any(p.card.is_token for p in sim.players[0].battlefield))
        self.assertEqual(sum(p.tapped for p in sim.players[0].battlefield),1)

    def test_repeated_x_and_unfamiliar_token_characteristics(self):
        sim,card=self.fixture(dict(name='Unknown brood',types=['Sorcery'],manaCost='{X}{X}{R}',oracleText='Create X tapped 2/3 blue Drake creature tokens with flying.'))
        self.assertEqual([a.x_value for a in sim.legal(0) if a.card_id==card.id],[0,1,2])
        self.cast(sim,card,2)
        tokens=[p for p in sim.players[0].battlefield if p.card.is_token]
        self.assertEqual(len(tokens),2)
        self.assertTrue(all(p.tapped and p.card.traits=='2;3;flying' for p in tokens))
        self.assertEqual(sum(p.tapped for p in sim.players[0].battlefield if p.card.kind=='land'),5)

    def test_variable_draw_and_life_use_chosen_value(self):
        for text,effect in [('Draw X cards.','draw'),('You gain X life.','life')]:
            sim,card=self.fixture(dict(name='Unknown variable spell',types=['Sorcery'],manaCost='{X}',oracleText=text))
            hand=len(sim.players[0].hand);life=sim.players[0].life
            self.cast(sim,card,3)
            self.assertEqual(len(sim.players[0].hand),hand-1+(3 if effect=='draw' else 0))
            self.assertEqual(sim.players[0].life,life+(3 if effect=='life' else 0))

    def test_unsupported_remaining_abilities_reject_whole_card(self):
        for text in ['Create X 1/1 red Goblin creature tokens. Draw a card.',
                     'Draw X cards. X is the number of creatures you control.',
                     'You gain twice X life.']:
            self.assertIsNone(x_spells.parse('{X}',text,['Sorcery']))
        self.assertIsNone(x_spells.parse('{X}','Draw X cards.',['Instant']))
