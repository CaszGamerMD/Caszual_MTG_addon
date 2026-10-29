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
        mountain=s.Card('mountain','Mountain','land',land_subtypes=('Mountain',),mask=8)
        plains=s.Card('plains','Plains','land',land_subtypes=('Plains',),mask=1)
        enemy=s.Card('enemy-mountain','Mountain','land',land_subtypes=('Mountain',),mask=8)
        sim.players[0].battlefield.extend([s.Permanent(mountain),s.Permanent(plains)])
        sim.players[1].battlefield.append(s.Permanent(enemy))
        self.assertEqual({p.card.id for _,p in sim.aura_targets(0,aura)},{'mountain'})
        with self.assertRaises(ValueError):sim.cast_spell(0,aura,target='plains')
        with self.assertRaises(ValueError):sim.cast_spell(0,aura,target='enemy-mountain')
        sim.cast_spell(0,aura,target='mountain');self.drain(sim)
        game=sim.event_game('main')
        self.assertTrue(game.has(game.battlefield['mountain'],'hexproof'))
        attached=next(p for p in sim.players[0].battlefield if p.card.id==aura.id)
        sim.send_to_destination(sim.players[0],attached)
        game=sim.event_game('main')
        self.assertFalse(game.has(game.battlefield['mountain'],'hexproof'))
        sim.invariant()

    def test_snow_restriction_is_rechecked(self):
        sim,cards=self.fixture(['Lifelink'])
        aura,_=self.aura('Enchant snow land you control\nEnchanted land has indestructible.')
        snow=s.Card('snow','Snow-Covered Plains','land',land_subtypes=('Plains',),mask=1,snow=True)
        plain=s.Card('plain','Plains','land',land_subtypes=('Plains',),mask=1)
        sim.players[0].battlefield.extend([s.Permanent(snow),s.Permanent(plain)])
        self.assertEqual({p.card.id for _,p in sim.aura_targets(0,aura)},{'snow'})
        sim.enter_creature(aura,sim.players[0],attached_to='snow')
        self.assertTrue(sim.event_game('main').has(sim.event_game('main').battlefield['snow'],'indestructible'))
        host=next(p for p in sim.players[0].battlefield if p.card.id=='snow')
        host.card=replace(host.card,snow=False)
        sim.state_based_actions()
        self.assertNotIn(aura.id,{p.card.id for p in sim.players[0].battlefield})
        self.assertIn(aura.id,{c.id for c in sim.players[0].graveyard})
        sim.invariant()
