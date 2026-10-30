"""Strict Oracle keyword and pump mechanics; real cards and unseen equivalents."""
import sys,json,unittest
from pathlib import Path
from dataclasses import replace
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
from card_events import Game,Permanent,parse_card

class KeywordPumpChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rules=s.RulesBridge()
        deck=json.loads((Path(__file__).resolve().parents[1]/'decks/27521806-faeries.json').read_text())
        cls.cards={c['name']:c for c in deck['mainboard']}
    @classmethod
    def tearDownClass(cls):cls.rules.close()
    def test_conditional_keyword_tracks_board_and_controller(self):
        for subtype,keyword in (('Faerie','lifelink'),('Goblin','deathtouch')):
            raw=dict(name='Unseen Watcher',types=['Creature'],subTypes=[subtype],
                     manaCost='{U}',power='2',toughness='2',
                     oracleText=f'This creature has {keyword} as long as you control another {subtype}.')
            source=parse_card(raw)
            self.assertTrue(source.supported)
            g=Game();g.enter(Permanent('source',source,0))
            friend=replace(source,static_effects=())
            g.enter(Permanent('enemy',friend,1))
            self.assertFalse(g.has(g.battlefield['source'],keyword))
            g.enter(Permanent('friend',friend,0))
            self.assertTrue(g.has(g.battlefield['source'],keyword))
            g.leave('friend');self.assertFalse(g.has(g.battlefield['source'],keyword))
            self.assertFalse(parse_card(dict(raw,oracleText=raw['oracleText']+'\nWin the game.')).supported)
    def test_self_pump_real_renamed_and_paid_stack(self):
        real=self.cards['Barrow Naughty']
        self.assertEqual(parse_card(real).self_pump,('{2}{B}',1,0))
        raw=dict(real,name='Unseen Sentinel',oracleText='Flying\nThis creature has lifelink as long as you control another Goblin.\n{1}{B}: This creature gets +3/+2 until end of turn.')
        self.assertEqual(parse_card(raw).self_pump,('{1}{B}',3,2))
        self.assertFalse(parse_card(dict(raw,oracleText=raw['oracleText']+'\nUnknown rule.')).supported)
        card=s.import_diagnostic_card(self.rules,raw,0,'pump',{'Blue','Black'})
        sim=s.Simulator(self.rules,42,decks=(s.demo_deck(0)+[card],s.demo_deck(1)),diagnostic=True)
        p=sim.players[0]
        (p.hand if card in p.hand else p.library).remove(card)
        p.battlefield.append(s.Permanent(card,fresh=False))
        lands=[c for c in p.hand+p.library if c.kind=='land'][:2]
        for land in lands:
            (p.hand if land in p.hand else p.library).remove(land)
            p.battlefield.append(s.Permanent(replace(land,name='Swamp',mask=4),fresh=False))
        sim.active=0;sim.phase='main';sim.stack.priority=0;sim.manual_priority=True
        sim.activate_self_pump(0,card.id)
        source=next(x for x in p.battlefield if x.card.id==card.id)
        self.assertEqual(sim.effective_card(source).power,1)
        sim.manual_priority=False
        with patch.object(s.Policy,'choose',side_effect=lambda obs:next(x for x in obs.legal_actions if x.kind=='priority_pass')):
            sim.drain_priority()
        self.assertEqual((sim.effective_card(source).power,sim.effective_card(source).toughness),(4,5))
        sim.invariant()
    def test_team_keyword_static_and_tap_grammar(self):
        raw=self.cards['Sprite Noble']
        parsed=parse_card(raw)
        self.assertEqual(parsed.team_keyword_pump,('flying',1,0,True))
        g=Game();g.enter(Permanent('source',parsed,0))
        ally=parse_card(dict(name='Ally',types=['Creature'],subTypes=['Faerie'],manaCost='{U}',power='2',toughness='2',oracleText='Flying'))
        g.enter(Permanent('ally',ally,0));g.enter(Permanent('enemy',ally,1))
        self.assertEqual(g.stats(g.battlefield['ally']),(2,3))
        self.assertEqual(g.stats(g.battlefield['enemy']),(2,2))
        g.leave('source');self.assertEqual(g.stats(g.battlefield['ally']),(2,2))
        unseen=dict(raw,name='Unseen Wind Leader',oracleText='Vigilance\nOther creatures you control with vigilance get +2/+3.\n{T}: Other creatures you control with vigilance get +3/+2 until end of turn.')
        self.assertEqual(parse_card(unseen).team_keyword_pump,('vigilance',3,2,True))
        self.assertFalse(parse_card(dict(unseen,oracleText=unseen['oracleText']+'\nDraw an impossible card.')).supported)
if __name__=='__main__':unittest.main()
