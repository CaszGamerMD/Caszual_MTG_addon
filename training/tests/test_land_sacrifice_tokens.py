"""Whole-text land-sacrifice token activation composed with a static anthem."""
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
from land_sacrifice_tokens import parse


TEXT=('Creatures you control have haste.\n'
      '{2}{R}, {T}, Sacrifice a land: Create a 3/3 colorless Golem enchantment artifact creature token.')


class LandSacrificeTokenChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.rules=s.RulesBridge()
    @classmethod
    def tearDownClass(cls):cls.rules.close()

    def source(self,text=TEXT,name='Unfamiliar forging engine'):
        raw=dict(name=name,layout='normal',types=['Artifact'],superTypes=['Legendary'],
                 subTypes=[],manaCost='{1}{R}{R}',colors=['Red'],oracleText=text)
        return s.import_diagnostic_card(self.rules,raw,0,'forge-'+name,{'Red'})

    def fixture(self,source=None):
        source=source or self.source()
        land=s.Card('sacrificial-terrain','Sacrificial terrain','land',mask=16,
                    basic_land=True,printed_types=frozenset({'Land'}))
        creature=s.Card('own-no-haste','Unfamiliar foot soldier','creature',
                        traits='1;1;',power=1,toughness=1,
                        event_definition=s.EventDefinition('Unfamiliar foot soldier',
                            frozenset({'Creature'}),frozenset(),False,1,1,frozenset()))
        enemy=s.Card('opponent-no-haste','Opposing foot soldier','creature',
                     traits='1;1;',power=1,toughness=1,
                     event_definition=s.EventDefinition('Opposing foot soldier',
                         frozenset({'Creature'}),frozenset(),False,1,1,frozenset()))
        sim=s.Simulator(self.rules,61,decks=(s.demo_deck(0)+[source,land,creature],
                                              s.demo_deck(1)+[enemy]),diagnostic=True)
        self.assertFalse(sim.finished,sim.questions)
        for seat,cards in ((0,(source,land,creature)),(1,(enemy,))):
            owner=sim.players[seat]
            for card in cards:
                (owner.hand if card in owner.hand else owner.library).remove(card)
                owner.battlefield.append(s.Permanent(card))
        sim.active=0;sim.phase='main';sim.manual_priority=True
        sim.stack.active=0;sim.stack.priority=0
        sim.players[0].mana_pool=[0,0,0,1,0,2]
        return sim,source,land,creature,enemy

    def test_real_hammer_and_unfamiliar_name_share_compiler(self):
        deck=json.loads((Path(__file__).resolve().parents[1]/'decks/14509839-mono-red-gobs.json').read_text())
        raw=next(c for c in deck['mainboard'] if c['name']=='Hammer of Purphoros')
        real=s.import_diagnostic_card(self.rules,raw,0,'real-hammer',{'Red'})
        self.assertEqual(real.kind,'artifact')
        self.assertEqual(real.event_definition.land_sacrifice_tokens,
                         self.source().event_definition.land_sacrifice_tokens)

    def test_static_haste_only_for_own_creatures_and_expires(self):
        sim,source,land,creature,enemy=self.fixture()
        game=sim.event_game('main')
        self.assertTrue(game.has(game.battlefield[creature.id],'haste'))
        self.assertFalse(game.has(game.battlefield[enemy.id],'haste'))
        hammer=next(p for p in sim.players[0].battlefield if p.card.id==source.id)
        sim.send_to_destination(sim.players[0],hammer)
        game=sim.event_game('main')
        self.assertFalse(game.has(game.battlefield[creature.id],'haste'))
        sim.invariant()

    def test_activation_costs_land_tap_and_mana_before_stack_resolution(self):
        sim,source,land,creature,enemy=self.fixture()
        choices=sim.token_ability_choices(0)
        self.assertTrue(any(c.kind=='activate_land_sacrifice_tokens' and
                            c.target_permanent==land.id for c in choices))
        sim.activate_land_sacrifice_tokens(0,source.id,land.id)
        self.assertNotIn(land.id,[p.card.id for p in sim.players[0].battlefield])
        self.assertTrue(next(p for p in sim.players[0].battlefield if p.card.id==source.id).tapped)
        self.assertEqual(sim.players[0].mana_pool,[0]*6)
        self.assertTrue(sim.stack.items)
        self.assertFalse(any(p.card.is_token for p in sim.players[0].battlefield))
        sim.pass_priority(0);sim.pass_priority(1)
        created=[p for p in sim.players[0].battlefield if p.card.is_token]
        self.assertEqual(len(created),1)
        definition=created[0].card.event_definition
        self.assertEqual((definition.power,definition.toughness),(3,3))
        self.assertEqual(definition.types,frozenset({'Creature','Enchantment','Artifact'}))
        self.assertEqual(definition.subtypes,frozenset({'Golem'}))
        self.assertTrue(sim.event_game('main').has(sim.event_game('main').battlefield[created[0].card.id],'haste'))
        sim.invariant()

    def test_unavailable_land_or_tapped_source_cannot_activate(self):
        sim,source,land,_,_=self.fixture()
        sim.send_to_destination(sim.players[0],next(p for p in sim.players[0].battlefield
                                                    if p.card.id==land.id))
        self.assertFalse(any(c.kind=='activate_land_sacrifice_tokens'
                             for c in sim.token_ability_choices(0)))
        with self.assertRaises(ValueError):sim.activate_land_sacrifice_tokens(0,source.id,land.id)
        sim.invariant()

    def test_parameterized_cost_and_token_size_and_fails_closed(self):
        changed=TEXT.replace('{2}{R}','{1}{G}').replace('3/3','4/2')
        altered=self.source(changed,name='Unknown alternate forge')
        self.assertEqual(altered.kind,'artifact')
        self.assertEqual(altered.event_definition.land_sacrifice_tokens.token.power,4)
        self.assertEqual(altered.event_definition.land_sacrifice_tokens.token.toughness,2)
        self.assertEqual(altered.event_definition.land_sacrifice_tokens.cost,'{1}{G}')
        self.assertEqual(self.source(TEXT+' Draw a card.').kind,'unsupported')
        self.assertEqual(self.source(TEXT.replace('Sacrifice a land','Discard a card')).kind,'unsupported')
        self.assertIsNone(parse(TEXT,['Instant']))


if __name__=='__main__':unittest.main()
