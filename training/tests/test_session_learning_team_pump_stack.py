"""Team keyword pump is a tap-cost stack ability, not an unconditional buff."""
import json,sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s

class TeamPumpStackChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rules=s.RulesBridge()
        data=json.loads((Path(__file__).resolve().parents[1]/'decks/27521806-faeries.json').read_text())
        cls.real=next(x for x in data['mainboard'] if x['name']=='Sprite Noble')
    @classmethod
    def tearDownClass(cls):cls.rules.close()
    def test_summoning_sickness_tap_cost_stack_and_keyword_filter(self):
        noble=s.import_diagnostic_card(self.rules,self.real,0,'noble',{'Blue'})
        def creature(uid,name,text,seat):
            raw=dict(name=name,types=['Creature'],subTypes=['Faerie'],manaCost='{U}',
                     power='2',toughness='2',oracleText=text)
            return s.import_diagnostic_card(self.rules,raw,seat,uid,{'Blue'})
        ally=creature('ally','Ally','Flying',0)
        ground=creature('ground','Ground','',0)
        enemy=creature('enemy','Enemy','Flying',1)
        sim=s.Simulator(self.rules,42,decks=(s.demo_deck(0)+[noble,ally,ground],
                                              s.demo_deck(1)+[enemy]),diagnostic=True)
        for seat,cards in ((0,(noble,ally,ground)),(1,(enemy,))):
            p=sim.players[seat]
            for c in cards:
                (p.hand if c in p.hand else p.library).remove(c)
                p.battlefield.append(s.Permanent(c,fresh=(c.id==noble.id)))
        sim.active=0;sim.phase='main';sim.stack.priority=0;sim.manual_priority=True
        self.assertFalse(any(x.kind=='activate_team_keyword_pump' for x in sim.legal(0)))
        source=next(x for x in sim.players[0].battlefield if x.card.id==noble.id)
        source.fresh=False
        self.assertTrue(any(x.kind=='activate_team_keyword_pump' for x in sim.legal(0)))
        sim.activate_team_keyword_pump(0,noble.id)
        self.assertTrue(source.tapped)
        with self.assertRaisesRegex(ValueError,'Illegal team pump'):
            sim.activate_team_keyword_pump(0,noble.id)
        target=next(x for x in sim.players[0].battlefield if x.card.id=='ally')
        self.assertEqual(sim.effective_card(target).power,2)
        sim.manual_priority=False
        with patch.object(s.Policy,'choose',side_effect=lambda obs:next(x for x in obs.legal_actions if x.kind=='priority_pass')):
            sim.drain_priority()
        self.assertEqual(sim.effective_card(target).power,3)
        self.assertEqual(sim.effective_card(next(x for x in sim.players[0].battlefield if x.card.id=='ground')).power,2)
        self.assertEqual(sim.effective_card(next(x for x in sim.players[1].battlefield if x.card.id=='enemy')).power,2)
        self.assertEqual(sim.effective_card(source).power,2)
        sim.invariant()
if __name__=='__main__':unittest.main()
