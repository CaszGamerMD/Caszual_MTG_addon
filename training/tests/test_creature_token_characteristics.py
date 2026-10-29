"""Reusable creature-token characteristic replacements, never card-name dispatch."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
import test_enchantment_abilities as fixtures


class CreatureTokenReplacementTests(unittest.TestCase):
    setUpClass=classmethod(fixtures.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.EnchantmentChecks.tearDownClass.__func__)
    fixture=fixtures.EnchantmentChecks.fixture
    put=fixtures.EnchantmentChecks.put
    drain=fixtures.EnchantmentChecks.drain

    def create(self,sim,seat=0,amount=2):
        sim._resolve_entry_effects([dict(operation='create_tokens',effect='create tokens',
            source='test',name='Unseen token creator',controller=seat,
            tokenSpec=dict(amount=amount,power=1,toughness=1,colors=['Green'],
                           subtypes=['Squirrel'],keywords=[],tapped=False))],
            s.Card('external','External','spell'))

    def tokens(self,sim,seat):
        return [p for p in sim.players[seat].battlefield if p.card.is_token]

    def test_real_card_unseen_name_parameters_and_unknown_remainder(self):
        raw=dict(self.lookup['Divine Visitation'],name='Unseen token transformer')
        parsed=s.import_diagnostic_card(self.rules,raw,0,'unseen',{'White'})
        self.assertEqual(parsed.kind,'enchantment')
        self.assertEqual(parsed.event_definition.token_replacements[0][0],'creature_as')
        raw['oracleText']=raw['oracleText'].replace('4/4 white Angel','5/6 blue Dragon').replace(
            'flying and vigilance','flying and haste')
        variant=s.import_diagnostic_card(self.rules,raw,0,'variant',{'Blue'})
        self.assertEqual(variant.kind,'enchantment')
        self.assertEqual(variant.event_definition.token_replacements[0][1]['power'],5)
        raw['oracleText']+='\nDraw a random mystery card.'
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'bad',set()).kind,'unsupported')

    def test_replaces_own_tokens_only_and_uses_existing_doublers(self):
        sim,cards=self.fixture(['Divine Visitation','Doubling Season'])
        source=self.put(sim,cards['Divine Visitation'])
        self.put(sim,cards['Doubling Season'])
        self.create(sim,seat=0,amount=2)
        self.create(sim,seat=1,amount=2)
        own=self.tokens(sim,0);enemy=self.tokens(sim,1)
        self.assertEqual(len(own),4)
        self.assertEqual(len(enemy),2)
        for token in own:
            d=token.card.event_definition
            self.assertEqual((d.power,d.toughness),(4,4))
            self.assertEqual(d.subtypes,frozenset({'Angel'}))
            self.assertEqual(d.colors,frozenset({'White'}))
            self.assertEqual(d.abilities,frozenset({'flying','vigilance'}))
        self.assertTrue(all(t.card.name=='Squirrel' for t in enemy))
        sim.send_to_destination(sim.players[0],source)
        self.create(sim,seat=0,amount=1)
        self.assertEqual(self.tokens(sim,0)[-1].card.name,'Squirrel')
        sim.invariant()

    def test_noncreature_token_spec_unaffected(self):
        sim,cards=self.fixture(['Divine Visitation'])
        self.put(sim,cards['Divine Visitation'])
        game=sim.event_game('main')
        original=dict(creature=False,amount=3,power=0,toughness=0,
                      subtypes=['Treasure'],colors=[],keywords=[])
        self.assertEqual(game.replace_creature_token_spec(0,original),original)
        self.assertEqual(game.token_amount(0,3),3)
        sim.invariant()

    def test_token_spell_also_creates_replacement_tokens(self):
        sim,cards=self.fixture(['Divine Visitation'])
        self.put(sim,cards['Divine Visitation'])
        definition=s.EventDefinition('Elf',frozenset({'Creature'}),
            frozenset({'Elf'}),False,1,1,frozenset(),colors=frozenset({'Green'}))
        spell=s.Card('token-test-spell','Unseen Token Spell','token_spell',
            mana_cost='{0}',token_count=2,token_definition=definition,
            printed_types=('Sorcery',))
        player=sim.players[0]
        player.hand.append(spell)
        sim.card_owners[spell.id]=0
        sim.total_cards=tuple(n+(i==0) for i,n in enumerate(sim.total_cards))
        sim.cast_spell(0,spell)
        self.drain(sim)
        self.assertEqual(len(self.tokens(sim,0)),2)
        self.assertTrue(all(t.card.name=='Angel' for t in self.tokens(sim,0)))
        self.assertIn(spell,player.graveyard)
        sim.invariant()

    def test_direct_event_kernel_token_creation_is_also_replaced(self):
        from card_events import Game, Permanent, Definition
        raw=self.lookup['Divine Visitation']
        visitation=s.parse_event_card(raw)
        game=Game(turn_player=0,phase='combat')
        hero=Definition('Hero',frozenset({'Creature'}),frozenset({'Warrior'}),
                        True,2,2,frozenset())
        equipment=Definition('Andúril, Flame of the West',frozenset({'Artifact'}),
                             frozenset({'Equipment'}),False,0,0,frozenset())
        game.enter(Permanent('hero',hero,0,fresh=False))
        game.enter(Permanent('equipment',equipment,0,attached_to='hero'))
        game.enter(Permanent('replacement',visitation,0))
        game.attack('hero',1)
        tokens=[p for p in game.battlefield.values() if p.token]
        self.assertEqual(len(tokens),2)
        self.assertTrue(all(p.definition.name=='Angel' for p in tokens))
        self.assertTrue(all(p.attacking==1 and p.tapped for p in tokens))
        self.assertTrue(all(p.definition.abilities==frozenset({'flying','vigilance'})
                            for p in tokens))
