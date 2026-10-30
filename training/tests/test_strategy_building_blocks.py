"""Mechanic-composition regression, not hard-coded Goblin/Elf deck scripting."""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import simulator as s
from deck_adaptive_strategy import analyze_deck, AdaptiveDeckPolicy
from strategy_building_blocks import parse_card_blocks, map_mechanics, compose_routes

DECKS=Path(__file__).resolve().parents[1] / 'decks'


def raw(name, types=('Creature',), subtypes=(), text='', count=1):
    return dict(name=name, types=list(types),subTypes=list(subtypes),
                manaCost='{2}',quantity=count,oracleText=text)


def sample_decks():
    """Invented fixtures: concept shared, setup paths distinct, no card-name rule."""
    goblin=dict(name='red-example',commanders=[
        raw('Brash Foreman',subtypes=('Goblin',),
            text='Other Goblins you control get +1/+1.')],
        mainboard=[
            raw('Rabble',subtypes=('Goblin',),count=14),
            raw('Nest Factory',types=('Enchantment',),
                text='At the beginning of your upkeep, create two 1/1 red Goblin creature tokens.',count=5),
            raw('Battle Standard',types=('Enchantment',),
                text='Creatures you control get +1/+1.',count=4),
            raw('Wild Charge',types=('Sorcery',),text='Draw two cards.',count=3),
            raw('Mountain',types=('Land',),count=36)])
    elf=dict(name='green-example',commanders=[
        raw('Forest Guide',subtypes=('Elf',),
            text='Elves you control get +1/+1.')],
        mainboard=[
            raw('Mana Scout',subtypes=('Elf',),
                text='{T}: Add {G}.',count=17),
            raw('Trailcaller',subtypes=('Elf',),
                text='Whenever another creature enters the battlefield under your control, draw a card.',
                count=6),
            raw('Overrun Signal',types=('Enchantment',),
                text='Creatures you control get +2/+2 and have trample.',count=4),
            raw('Forest',types=('Land',),count=36)])
    return goblin,elf


class MechanicsTests(unittest.TestCase):
    def test_token_producers_and_elf_mana_engine_are_different_building_blocks(self):
        goblin,elf=sample_decks()
        gm=map_mechanics(goblin)
        em=map_mechanics(elf)
        g_factory=next(c for c in gm if c.name=='Nest Factory')
        e_scout=next(c for c in em if c.name=='Mana Scout')
        self.assertIn('token_supply',g_factory.blocks)
        self.assertIn('creature_board',g_factory.produces)
        self.assertNotIn('token_supply',e_scout.blocks)
        self.assertIn('mana_engine',e_scout.blocks)
        self.assertIn('mana',e_scout.produces)

    def test_same_combat_goal_different_journey_for_goblins_and_elves(self):
        goblin,elf=sample_decks()
        gr=compose_routes(map_mechanics(goblin))
        er=compose_routes(map_mechanics(elf))
        g=next(r for r in gr if r.goal=='combat_damage')
        e=next(r for r in er if r.goal=='combat_damage')
        self.assertEqual(g.goal,e.goal)
        self.assertIn('token_supply',g.steps)
        self.assertIn('mana_engine',e.steps)
        self.assertIn('card_engine',e.steps)
        self.assertNotEqual(g.steps,e.steps)
        self.assertEqual(g.steps[-1],e.steps[-1])
        # Renaming any cards/decks changes no mechanical path.
        goblin2=json.loads(json.dumps(goblin))
        for i,c in enumerate(goblin2['mainboard']):c['name']=f'Anonymized-{i}'
        goblin2['commanders'][0]['name']='Unknown'
        self.assertEqual([r.steps for r in compose_routes(map_mechanics(goblin2))],
                         [r.steps for r in gr])

    def test_rules-text_facts_do_not_assert_executability(self):
        # Treasure is not a creature token.
        treasury=parse_card_blocks(raw('Untitled',types=('Sorcery',),
                    text='Create two Treasure tokens.'))
        self.assertIn('mana_engine',treasury.blocks)
        self.assertNotIn('token_supply',treasury.blocks)
        self.assertNotIn('creature_board',treasury.produces)
        # A buff needs a creature board. It doesn't produce creatures.
        buff=parse_card_blocks(raw('Untitled 2',types=('Enchantment',),
                    text='Creatures you control get +1/+1.'))
        self.assertIn('creature_board',buff.needs)
        self.assertNotIn('creature_board',buff.produces)
        # A draw trigger can be part of the chain from creature entry to cards.
        engine=parse_card_blocks(raw('Untitled 3',text='Whenever a creature enters, draw a card.'))
        self.assertIn('card_engine',engine.blocks)
        self.assertIn('creature_entry',engine.needs)

    def test_real_garbo_and_wilds_have_distinct_composable_routes(self):
        garbo=json.loads((DECKS/'5254666-garbo-gobbos.json').read_text())
        wilds=json.loads((DECKS/'5189995-enchantments.json').read_text())
        gp,wp=analyze_deck(garbo),analyze_deck(wilds)
        self.assertTrue(gp.routes)
        self.assertTrue(wp.routes)
        self.assertTrue(all(r.score>=0 for r in gp.routes+wp.routes))
        self.assertIn('strategyRoutes',gp.describe())
        self.assertGreater(len(gp.card_roles),20)
        self.assertGreater(len(wp.card_roles),20)
        self.assertIn('tribal_swarm',(gp.primary,gp.secondary))
        self.assertIn('enchantment_value',(wp.primary,wp.secondary))

    def test_mechanic_bonus_responds_to_board_not_card_names(self):
        g,_=sample_decks()
        plan=analyze_deck(g)
        token=s.Card('token','Nest Factory','enchantment','{2}')
        buff=s.Card('buff','Battle Standard','enchantment','{2}')
        actions=(s.Candidate('token','cast','token',s.features()),
                 s.Candidate('buff','cast','buff',s.features()))
        def obs(creatures):
            own=[dict(id=f'land{i}',name='Land',kind='land',isCreature=False,
                       tapped=False,fresh=False,power=0,toughness=0,traits='')
                 for i in range(4)]
            own += [dict(id=f'cr{i}',name='1/1',kind='creature',isCreature=True,
                         tapped=False,fresh=False,power=1,toughness=1,traits='')
                    for i in range(creatures)]
            players=[dict(life=40,battlefield=own),dict(life=40,battlefield=[])]
            return s.Observation(0,5,'main',(token,buff),
                   json.dumps({'players':players}),actions)
        p=AdaptiveDeckPolicy(plan=plan)
        self.assertEqual(p.choose(obs(0)).card_id,'token')
        self.assertEqual(p.choose(obs(5)).card_id,'buff')


if __name__=='__main__':
    unittest.main()
