"""Attacking nontoken triggers and self-sacrifice team-wide boosts."""
import unittest
import test_enchantment_abilities as fixtures
import simulator as s

class AttackEnchantmentChecks(unittest.TestCase):
    setUpClass=classmethod(fixtures.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.EnchantmentChecks.tearDownClass.__func__)
    fixture=fixtures.EnchantmentChecks.fixture
    put=fixtures.EnchantmentChecks.put
    token=fixtures.EnchantmentChecks.token
    ready=fixtures.EnchantmentChecks.ready
    drain=fixtures.EnchantmentChecks.drain

    def test_real_unseen_parameters_and_unknown_text_rejection(self):
        raw=dict(self.lookup['Mardu Ascendancy'],name='Unseen attacking enchantment')
        card=s.import_diagnostic_card(self.rules,raw,0,'a',{'Red','White','Black'})
        self.assertEqual(card.kind,'enchantment')
        raw['oracleText']=raw['oracleText'].replace('1/1 red Goblin','2/3 green Elf').replace('+0/+3','+2/+4')
        variant=s.import_diagnostic_card(self.rules,raw,0,'b',{'Green'})
        self.assertEqual(variant.event_definition.sacrifice_team_boost,(2,4))
        self.assertEqual(variant.event_definition.attack_nontoken_tokens[0].power,2)
        raw['oracleText']+='\nDraw an unknown card.'
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'bad',{'Green'}).kind,'unsupported')

    def test_each_nontoken_attacker_creates_tapped_attacking_token(self):
        sim,cards=self.fixture(['Mardu Ascendancy'])
        self.put(sim,cards['Mardu Ascendancy'])
        a=self.token(sim,'nontoken-placeholder')
        b=self.token(sim,'also-nontoken-placeholder')
        # These are physical creature stand-ins; token attackers must not trigger.
        a.card=s.Card('a-physical','A','creature',power=2,toughness=2,
                      traits='2;2;',event_definition=a.card.event_definition)
        b.card=s.Card('b-physical','B','creature',power=2,toughness=2,
                      traits='2;2;',event_definition=b.card.event_definition)
        sim.card_owners['a-physical']=0;sim.card_owners['b-physical']=0
        # Use a single real nontoken imported creature for invariant-safe testing instead.
        sim.players[0].battlefield.remove(a);sim.players[0].battlefield.remove(b)
        raw=self.lookup['Legion Warboss']
        physical=s.import_diagnostic_card(self.rules,raw,0,'physical',{'Red'})
        sim.players[0].hand.append(physical)
        source=self.put(sim,physical)
        goblin=self.token(sim,'token-attacker')
        self.ready(sim)
        sim.declare_attackers([source.card.id,goblin.card.id])
        self.assertEqual(len(sim.stack.items),1)
        self.drain(sim)
        created=[p for p in sim.players[0].battlefield if p.card.is_token and p.card.id!=goblin.card.id]
        self.assertEqual(len(created),1)
        self.assertTrue(created[0].tapped)
        self.assertIn(created[0].card.id,sim.group_combat['attackers'])
        self.assertNotIn(created[0].card.id,sim.group_combat['declared'])
        sim.invariant()

    def test_sacrifice_cost_then_team_boost_on_stack_including_late_creature(self):
        sim,cards=self.fixture(['Mardu Ascendancy'])
        source=self.put(sim,cards['Mardu Ascendancy'])
        ally=self.token(sim,'ally',power=2,toughness=2)
        enemy=self.token(sim,'enemy',seat=1,power=2,toughness=2)
        sim.activate_sacrifice_team_boost(0,source.card.id)
        self.assertNotIn(source,sim.players[0].battlefield)
        self.assertEqual(sim.effective_card(ally).toughness,2)
        late=self.token(sim,'late',power=1,toughness=1)
        self.drain(sim)
        self.assertEqual(sim.effective_card(ally).toughness,5)
        self.assertEqual(sim.effective_card(late).toughness,4)
        self.assertEqual(sim.effective_card(enemy).toughness,2)
        sim.invariant()

    def test_unavailable_source_cannot_be_sacrificed_twice(self):
        sim,cards=self.fixture(['Mardu Ascendancy'])
        source=self.put(sim,cards['Mardu Ascendancy'])
        sim.activate_sacrifice_team_boost(0,source.card.id)
        with self.assertRaises(ValueError):sim.activate_sacrifice_team_boost(0,source.card.id)
        self.drain(sim)
        sim.invariant()
