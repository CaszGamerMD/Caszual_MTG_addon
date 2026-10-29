"""Land Aura restrictions and continuous keyword grants from unseen Oracle text."""
import unittest
import test_enchantment_abilities as fixtures
import simulator as s
from dataclasses import replace

class LandAuraRestrictionChecks(unittest.TestCase):
    setUpClass=classmethod(fixtures.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.EnchantmentChecks.tearDownClass.__func__)
    fixture=fixtures.EnchantmentChecks.fixture
    drain=fixtures.EnchantmentChecks.drain

    def aura(self,text):
        raw=dict(self.lookup['Lifelink'],name='Unseen land blessing',oracleText=text)
        return s.import_diagnostic_card(self.rules,raw,0,'land-aura',{'White'}),raw

    def test_unseen_grammar_and_unknown_clauses(self):
        for rule,expected in [('Enchant land you control','land:controller'),
                              ('Enchant Mountain you control','land:mountain:controller'),
                              ('Enchant snow land you control','land:snow:controller')]:
            card,raw=self.aura(rule+'\nEnchanted land has hexproof.')
            self.assertEqual(card.kind,'aura')
            self.assertEqual(card.event_definition.attachment[5],expected)
            raw['oracleText']+='\nIf the moon is full, draw two cards.'
            self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'bad',{'White'}).kind,'unsupported')
        card,_=self.aura('Enchant Mountain you control\nEnchanted land gets +3/+3.')
        self.assertEqual(card.kind,'unsupported')

    def test_mountain_target_and_keyword_end_on_aura_departure(self):
        sim,cards=self.fixture(['Lifelink'])
        aura,_=self.aura('Enchant Mountain you control\nEnchanted land has hexproof.')
        sim.players[0].hand.remove(cards['Lifelink']);sim.players[0].hand.append(aura)
        mountain,plains=[x for x in sim.players[0].battlefield if x.card.kind=='land'][:2]
        mountain.card=replace(mountain.card,land_subtypes=('Mountain',),mask=8)
        plains.card=replace(plains.card,land_subtypes=('Plains',),mask=1)
        enemy=next(c for c in sim.players[1].library if c.kind=='land')
        sim.players[1].library.remove(enemy)
        enemy=replace(enemy,land_subtypes=('Mountain',),mask=8)
        sim.players[1].battlefield.append(s.Permanent(enemy))
        self.assertEqual({p.card.id for _,p in sim.aura_targets(0,aura)},{mountain.card.id})
        with self.assertRaises(ValueError):sim.cast_spell(0,aura,target=plains.card.id)
        with self.assertRaises(ValueError):sim.cast_spell(0,aura,target=enemy.id)
        sim.cast_spell(0,aura,target=mountain.card.id);self.drain(sim)
        game=sim.event_game('main')
        self.assertTrue(game.has(game.battlefield[mountain.card.id],'hexproof'))
        attached=next(p for p in sim.players[0].battlefield if p.card.id==aura.id)
        sim.send_to_destination(sim.players[0],attached)
        game=sim.event_game('main')
        self.assertFalse(game.has(game.battlefield[mountain.card.id],'hexproof'))
        sim.invariant()

    def test_snow_restriction_is_rechecked(self):
        sim,cards=self.fixture(['Lifelink'])
        aura,_=self.aura('Enchant snow land you control\nEnchanted land has indestructible.')
        sim.players[0].hand.remove(cards['Lifelink'])
        snow,plain=[x for x in sim.players[0].battlefield if x.card.kind=='land'][:2]
        snow.card=replace(snow.card,land_subtypes=('Plains',),mask=1,snow=True)
        plain.card=replace(plain.card,land_subtypes=('Plains',),mask=1,snow=False)
        self.assertEqual({p.card.id for _,p in sim.aura_targets(0,aura)},{snow.card.id})
        sim.enter_creature(aura,sim.players[0],attached_to=snow.card.id)
        self.assertTrue(sim.event_game('main').has(sim.event_game('main').battlefield[snow.card.id],'indestructible'))
        host=snow
        host.card=replace(host.card,snow=False)
        sim.state_based_actions()
        self.assertNotIn(aura.id,{p.card.id for p in sim.players[0].battlefield})
        self.assertIn(aura.id,{c.id for c in sim.players[0].graveyard})
        sim.invariant()
