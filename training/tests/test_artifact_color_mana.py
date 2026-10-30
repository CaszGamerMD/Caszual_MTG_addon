"""Full-program color mana artifact regression, including stack and negative tests."""
import unittest
import test_enchantment_abilities as fixtures
import simulator as s
import mana_pool

class ColorManaTests(unittest.TestCase):
    setUpClass=classmethod(fixtures.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.EnchantmentChecks.tearDownClass.__func__)
    fixture=fixtures.EnchantmentChecks.fixture

    def prepare(self):
        sim,_=self.fixture(['Lifelink'])
        raw=self.lookup['Chromatic Orrery']
        card=s.import_diagnostic_card(self.rules,raw,0,'orrery',set())
        self.assertEqual(card.kind,'mana_artifact')
        source=s.Permanent(card)
        sim.players[0].battlefield.append(source)
        return sim,card,source

    def test_real_renamed_and_extra_text_rejected(self):
        raw=dict(self.lookup['Chromatic Orrery'])
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'a',set()).kind,'mana_artifact')
        raw['name']='Unknown mana engine'
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'b',set()).kind,'mana_artifact')
        raw['oracleText']+='\nGain an extra turn.'
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'c',set()).kind,'unsupported')
        raw['oracleText']=self.lookup['Chromatic Orrery']['oracleText'].replace('{C}{C}{C}{C}{C}','{C}{C}{C}')
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'d',set()).mana_production[-1],3)

    def test_mana_permission_all_costs_and_true_colorless(self):
        sim,card,source=self.prepare()
        self.assertEqual(dict(sim.mana_sources(0))[card.id][0][-1],5)
        self.assertTrue(source.fresh) # Noncreature artifact taps immediately
        self.assertTrue(sim.payment(s.Card('spell','Spell','spell',mana_cost='{W}{U}{B}{R}{G}'))['paid'])
        sim.players[0].mana_pool=[0,0,0,0,0,2]
        self.assertTrue(sim.payment(s.Card('act','Ability','artifact',mana_cost='{W}{B}'),spell_cost=False)['paid'])
        sim.players[0].battlefield.remove(source)
        self.assertFalse(mana_pool.plan('{W}{B}',[0,0,0,0,0,2],[])['paid'])
        self.assertFalse(mana_pool.plan('{C}',[1,0,0,0,0,0],[],spend_as_any_color=True)['paid'])

    def test_tap_draw_stack_resolution_and_distinct_colors(self):
        sim,card,source=self.prepare()
        for item in sim.players[0].battlefield:
            if item.card.id.startswith('mana'):item.tapped=True
        self.assertFalse(sim.color_draw_payment(0,source)['paid'])
        sim.players[0].mana_pool=[0,0,0,0,0,5]
        before=len(sim.players[0].hand)
        sim.activate_color_draw(0,card.id)
        self.assertEqual(len(sim.players[0].hand),before)
        self.assertTrue(source.tapped)
        def add(name,colors,seat=0):
            d=s.EventDefinition(name,frozenset({'Enchantment'}),frozenset(),False,0,0,frozenset(),colors=frozenset(colors))
            sim.enter_creature(s.Card(name,name,'enchantment',event_definition=d,is_token=True),sim.players[seat])
        add('dual',('White','Black'));add('other',('Black','Green'));add('enemy',('Red',),1)
        sim.pass_priority(0);sim.pass_priority(1)
        self.assertEqual(len(sim.players[0].hand),before+3)
        self.assertEqual([e['details']['colorCount'] for e in sim.events if e['kind']=='color_draw_resolution'][-1],3)
        with self.assertRaises(ValueError):sim.activate_color_draw(0,card.id)
        sim.invariant()

    def test_colorless_permanents_not_a_color(self):
        sim,card,source=self.prepare()
        for item in sim.players[0].battlefield:
            if item.card.id.startswith('mana'):item.tapped=True
        sim.players[0].mana_pool=[0,0,0,0,0,5]
        sim.activate_color_draw(0,card.id)
        sim.pass_priority(0);sim.pass_priority(1)
        self.assertEqual([e['details']['colorCount'] for e in sim.events if e['kind']=='color_draw_resolution'][-1],0)
