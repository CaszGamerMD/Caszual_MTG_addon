"""Squee's attack token and exile-other graveyard alternative are composable."""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s


class SqueeChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rules=s.RulesBridge()
        deck=Path(__file__).resolve().parents[1]/'decks'/'14509839-mono-red-gobs.json'
        data=json.loads(deck.read_text())
        cls.lookup={card['name']:card for card in data.get('mainboard',[])}

    @classmethod
    def tearDownClass(cls):
        cls.rules.close()

    def imported_squee(self,raw=None):
        raw=dict(raw or self.lookup['Squee, Dubious Monarch'])
        return s.import_diagnostic_card(self.rules,raw,0,'squee',{'Red'})

    def fixture(self):
        card=self.imported_squee()
        lands=[s.Card('squee-mana-'+str(i),'Mana','land',mask=63) for i in range(10)]
        sim=s.Simulator(self.rules,42,decks=(s.demo_deck(0)+[card]+lands,s.demo_deck(1)),
                        diagnostic=True)
        sim.manual_priority=True
        sim.phase='main'
        sim.stack.priority=0
        player=sim.players[0]
        for item in [card]+lands:
            (player.hand if item in player.hand else player.library).remove(item)
        player.graveyard.append(card)
        for item in list(player.library[:4]):
            player.library.remove(item)
            player.graveyard.append(item)
        player.battlefield.extend(s.Permanent(item) for item in lands)
        return sim,card

    def test_real_and_renamed_card_compose_attack_and_graveyard_text(self):
        raw=dict(self.lookup['Squee, Dubious Monarch'])
        card=self.imported_squee(raw)
        self.assertEqual(card.kind,'creature')
        self.assertIn('haste',card.event_definition.abilities)
        self.assertEqual(card.event_definition.graveyard_cast_alternate,('{3}{R}',4))
        self.assertEqual(card.event_definition.attack_effects[0][0],'attack_tokens')
        token_spec=card.event_definition.attack_effects[0][3]
        self.assertEqual((token_spec.amount,token_spec.power,token_spec.toughness,
                          token_spec.colors,token_spec.subtypes,token_spec.tapped,
                          token_spec.attacking),
                         (1,1,1,('Red',),('Goblin',),True,True))

        raw['name']='Unfamiliar Goblin Monarch'
        raw['oracleText']=raw['oracleText'].replace(
            'Whenever Squee attacks','Whenever this creature attacks')
        renamed=self.imported_squee(raw)
        self.assertEqual(renamed.kind,'creature')
        self.assertEqual(renamed.event_definition.graveyard_cast_alternate,('{3}{R}',4))
        raw['oracleText']+='\nYou win the game.'
        self.assertEqual(self.imported_squee(raw).kind,'unsupported')

    def test_legal_action_exiles_exactly_four_other_cards_and_casts_normally(self):
        sim,card=self.fixture()
        player=sim.players[0]
        others=[item for item in player.graveyard if item.id!=card.id]
        self.assertEqual(len(others),4)
        choice=next(action for action in sim.legal(0)
                    if action.kind=='cast_graveyard_alternate' and action.card_id==card.id)
        self.assertEqual(set(choice.tap_ids),{item.id for item in others})
        sim.cast_spell(0,card,graveyard_alternate=True,
                       graveyard_exile_ids=choice.tap_ids)
        self.assertNotIn(card,player.graveyard)
        self.assertTrue(all(any(item.id==identifier for item in player.exile)
                            for identifier in choice.tap_ids))
        self.assertEqual(len(sim.stack.items),1)
        sim.manual_priority=False
        sim.drain_priority()
        creature=next(item for item in player.battlefield if item.card.id==card.id)
        game=sim.event_game('main')
        self.assertTrue(game.creature(game.battlefield[creature.card.id]))
        sim.invariant()

    def test_cast_rejects_incomplete_or_repeated_exile_cost(self):
        sim,card=self.fixture()
        player=sim.players[0]
        others=[item for item in player.graveyard if item.id!=card.id]
        with self.assertRaises(ValueError):
            sim.cast_spell(0,card,graveyard_alternate=True,
                           graveyard_exile_ids=tuple(item.id for item in others[:3]))
        with self.assertRaises(ValueError):
            sim.cast_spell(0,card,graveyard_alternate=True,
                           graveyard_exile_ids=(others[0].id,)*4)
        self.assertIn(card,player.graveyard)
        self.assertEqual(len(sim.stack.items),0)

    def test_attack_trigger_creates_a_tapped_attacking_goblin(self):
        sim,card=self.fixture()
        player=sim.players[0]
        player.graveyard.remove(card)
        player.hand.append(card)
        sim.manual_priority=False
        pending=sim.enter_creature(card,player)
        sim.resolve_entry_triggers(pending,card)
        attacker=next(item for item in player.battlefield if item.card.id==card.id)
        attacker.fresh=False

        sim.group_combat={'attackers':[card.id]}
        game=sim.event_game('combat')
        game.attack(card.id,1,defer=True)
        sim.sync_events(game)
        attack_tokens=[event for event in game.events
                       if event.get('operation')=='create_tokens']
        self.assertEqual(len(attack_tokens),1)
        self.assertEqual(attack_tokens[0]['tokenSpec']['attacking'],1)
        sim.resolve_entry_triggers(attack_tokens,card)

        goblin=next(item for item in player.battlefield
                    if item.card.is_token and item.card.event_definition.subtypes==frozenset({'Goblin'}))
        self.assertTrue(goblin.tapped)
        self.assertIn(goblin.card.id,sim.group_combat['attackers'])
        self.assertEqual(goblin.card.power,1)
        sim.invariant()


if __name__=='__main__':
    unittest.main()
