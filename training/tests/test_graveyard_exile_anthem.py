"""Ethereal-style graveyard exile and continuous anthem interactions."""
import unittest
import test_enchantment_abilities as f
import simulator as s

class GraveyardExileChecks(unittest.TestCase):
    setUpClass=classmethod(f.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(f.EnchantmentChecks.tearDownClass.__func__)
    fixture=f.EnchantmentChecks.fixture
    put=f.EnchantmentChecks.put
    token=f.EnchantmentChecks.token

    def prepare(self):
        sim,cards=self.fixture(['Lifelink'])
        raw=self.lookup['Ethereal Absolution']
        source=s.import_diagnostic_card(self.rules,raw,0,'absolution',{'White','Black'})
        self.assertEqual(source.kind,'enchantment')
        sim.players[0].hand.remove(cards['Lifelink'])
        sim.players[0].hand.append(source)
        self.put(sim,source)
        return sim,source

    def test_actual_renamed_and_unknown_text(self):
        raw=dict(self.lookup['Ethereal Absolution'])
        self.assertNotEqual(s.import_diagnostic_card(self.rules,raw,0,'a',set()).kind,'unsupported')
        raw['name']='Unfamiliar graveyard anthem'
        self.assertNotEqual(s.import_diagnostic_card(self.rules,raw,0,'b',set()).kind,'unsupported')
        raw['oracleText']+='\nDo something unknown.'
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'c',set()).kind,'unsupported')

    def test_both_static_effects_are_continuous(self):
        sim,source=self.prepare()
        ally=self.token(sim,'ally')
        enemy=self.token(sim,'enemy',seat=1)
        self.assertEqual((sim.effective_card(ally).power,sim.effective_card(ally).toughness),(3,3))
        self.assertEqual((sim.effective_card(enemy).power,sim.effective_card(enemy).toughness),(1,1))
        sim.send_to_destination(sim.players[0],next(p for p in sim.players[0].battlefield if p.card.id==source.id))
        self.assertEqual(sim.effective_card(ally).power,2)
        self.assertEqual(sim.effective_card(enemy).power,2)

    def test_target_exile_stack_token_and_fizzle(self):
        sim,source=self.prepare()
        victim=s.Card('victim','Unknown creature','creature',printed_types=('Creature',))
        sim.players[1].graveyard.append(victim);sim.card_owners[victim.id]=1
        sim.total_cards=(sim.total_cards[0],sim.total_cards[1]+1)
        sim.players[0].mana_pool=[0,0,0,0,0,4]
        sim.activate_graveyard_exile(0,source.id,victim.id)
        self.assertIn(victim,sim.players[1].graveyard)
        sim.pass_priority(0);sim.pass_priority(1)
        self.assertIn(victim,sim.players[1].exile)
        spirits=[p for p in sim.players[0].battlefield if p.card.is_token and 'Spirit' in p.card.event_definition.subtypes]
        self.assertEqual(len(spirits),1)
        self.assertEqual(spirits[0].card.event_definition.colors,frozenset({'White','Black'}))
        self.assertIn('flying',spirits[0].card.event_definition.abilities)
        with self.assertRaises(ValueError):sim.activate_graveyard_exile(0,source.id,victim.id)
        sim.invariant()

    def test_noncreature_target_does_not_make_token(self):
        sim,source=self.prepare()
        card=s.Card('dead-land','Dead Land','land',printed_types=('Land',))
        sim.players[1].graveyard.append(card);sim.card_owners[card.id]=1
        sim.total_cards=(sim.total_cards[0],sim.total_cards[1]+1)
        sim.players[0].mana_pool=[0,0,0,0,0,4]
        sim.activate_graveyard_exile(0,source.id,card.id)
        sim.pass_priority(0);sim.pass_priority(1)
        self.assertIn(card,sim.players[1].exile)
        self.assertFalse([p for p in sim.players[0].battlefield if p.card.is_token])
        sim.invariant()
