"""Generic creature-combat-hit emblem: library search into battlefield."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
from planeswalker_loyalty import compile_card
from planeswalker_emblems import CombatCreatureSearchEmblem,combat_hit_events
from planeswalker_runtime import activate

EMBLEM=(
    '−7: You get an emblem with "Whenever a creature you control deals combat damage '
    'to a player, search your library for a blue or black creature card, '
    'put it onto the battlefield, then shuffle."'
)

class CombatEmblemTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.rules=s.RulesBridge()
    @classmethod
    def tearDownClass(cls):cls.rules.close()

    def raw(self,oracle=EMBLEM,name='Unnamed Nightwalker'):
        return dict(name=name,layout='normal',types=['Planeswalker'],
                    superTypes=['Legendary'],subTypes=['Nightwalker'],
                    colors=['Blue','Black'],manaCost='{1}{U}{B}',
                    loyalty='8',oracleText=oracle)

    def fixture(self,with_blue=True):
        pw=s.import_diagnostic_card(self.rules,self.raw(),0,'combat-pw',{'Blue','Black'})
        self.assertEqual(pw.kind,'planeswalker')
        lands=[s.Card('m-'+str(i),'Mana','land',mask=63) for i in range(6)]
        blue=s.Card('blue-find','Blue friend','creature',power=2,toughness=3,
             colors=('Blue',),event_definition=s.EventDefinition('Blue friend',
             frozenset({'Creature'}),frozenset(),False,2,3,frozenset(),
             colors=frozenset({'Blue'})))
        attacker=s.Card('attacker','Attacking human','creature',power=2,toughness=2,
             event_definition=s.EventDefinition('Attacking human',
             frozenset({'Creature'}),frozenset(),False,2,2,frozenset()))
        red=s.Card('red-not-eligible','Red friend','creature',power=4,toughness=4,
             colors=('Red',),event_definition=s.EventDefinition('Red friend',
             frozenset({'Creature'}),frozenset(),False,4,4,frozenset(),
             colors=frozenset({'Red'})))
        sim=s.Simulator(self.rules,79,
              decks=(s.demo_deck(0)+[pw]+lands+[attacker,red]+([blue] if with_blue else []),
                     s.demo_deck(1)),diagnostic=True)
        self.assertFalse(sim.finished,sim.questions)
        sim.phase='main';sim.manual_priority=True
        for card in [pw]+lands+[attacker]:
            (sim.players[0].hand if card in sim.players[0].hand else sim.players[0].library).remove(card)
        sim.players[0].hand.append(pw)
        sim.players[0].battlefield.extend(s.Permanent(c) for c in lands)
        attacking=s.Permanent(attacker,fresh=False)
        sim.players[0].battlefield.append(attacking)
        sim.cast_spell(0,pw)
        self.drain(sim)
        walker=next(p for p in sim.players[0].battlefield if p.card==pw)
        activate(sim,0,pw.id,0)
        self.drain(sim)
        self.assertEqual(len(sim.emblems[0]),1)
        return sim,pw,attacking,blue,red

    @staticmethod
    def drain(sim):
        while sim.stack.items:sim.pass_priority(sim.stack.priority)

    def damage(self,sim,attacker):
        sim.phase='group_damage_start'
        sim.group_combat=dict(attackers=[attacker.card.id],
            declared=[attacker.card.id],blocks={},blocked=set(),early=None,block_limit=None)
        starting=sim.players[1].life
        sim.group_damage_step()
        self.assertEqual(sim.players[1].life,starting-2)
        return tuple(sim.stack.items)

    def test_compile_full_oracle_search_emblem_by_color_not_card_name(self):
        p=compile_card(self.raw())
        self.assertIsNotNone(p)
        self.assertIsInstance(p.abilities[0].program,CombatCreatureSearchEmblem)
        self.assertEqual(p.abilities[0].program.colors,('Blue','Black'))
        self.assertIsNotNone(compile_card(self.raw(name='Completely unrelated name')))
        for text in (
            EMBLEM.replace('blue or black','blue and black'),
            EMBLEM.replace('creature card','permanent card'),
            EMBLEM.replace('combat damage','damage'),
            EMBLEM.replace('onto the battlefield','into your hand'),
            EMBLEM+'. Draw three cards.'
        ):
            with self.subTest(text=text):
                self.assertIsNone(compile_card(self.raw(oracle=text)))

    def test_combat_damage_creates_stack_trigger_and_tutors_color_match(self):
        sim,pw,attacker,blue,red=self.fixture()
        frames=self.damage(sim,attacker)
        self.assertEqual(len(frames),1)
        self.assertEqual(frames[0].payload[0]['operation'],'emblem_combat_search')
        self.assertIn(blue,sim.players[0].library)
        self.drain(sim)
        self.assertIn(blue,[p.card for p in sim.players[0].battlefield])
        self.assertIn(red,sim.players[0].library)
        self.assertTrue(any(e['kind']=='emblem_creature_search'
                            and e['details']['found'] for e in sim.events))
        sim.invariant()

    def test_countered_trigger_does_not_search_or_erase_emblem(self):
        sim,pw,attacker,blue,red=self.fixture()
        frames=self.damage(sim,attacker)
        self.assertIsNotNone(sim.counter_stack_item(frames[0]))
        self.assertIn(blue,sim.players[0].library)
        self.assertEqual(len(sim.emblems[0]),1)
        sim.invariant()

    def test_no_supported_match_still_shuffles_and_emblem_persists(self):
        sim,pw,attacker,_,red=self.fixture(with_blue=False)
        self.damage(sim,attacker)
        self.drain(sim)
        self.assertEqual(len(sim.emblems[0]),1)
        self.assertIn(red,sim.players[0].library)
        self.assertTrue(any(e['kind']=='emblem_creature_search'
                            and not e['details']['found'] for e in sim.events))
        sim.invariant()

    def test_damage_not_to_player_does_not_trigger_emblem(self):
        sim,pw,attacker,blue,red=self.fixture()
        self.assertEqual(combat_hit_events(sim,[],0),[])
        self.assertEqual(combat_hit_events(sim,[attacker.card.id],1),[])
        sim.invariant()

if __name__=='__main__':unittest.main()
