"""Creature mana activations are mana abilities (no stack), not free tap spells."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
import test_enchantment_abilities as fixtures

class CreatureManaChecks(unittest.TestCase):
    setUpClass=classmethod(fixtures.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.EnchantmentChecks.tearDownClass.__func__)
    fixture=fixtures.EnchantmentChecks.fixture
    put=fixtures.EnchantmentChecks.put

    def test_real_and_renamed_fixed_mana_with_parameterized_amount(self):
        for name,count in [('Elvish Mystic',1),('Llanowar Elves',1),('Llanowar Tribe',3)]:
            raw=self.lookup[name]
            card=s.import_diagnostic_card(self.rules,raw,0,'mana-'+name,{'Green'})
            self.assertEqual(card.kind,'creature',name)
            self.assertEqual(card.event_definition.scaled_mana_tap,'fixed:G:'+str(count))
            renamed=dict(raw,name='Unseen Ruby Mystic',oracleText=raw['oracleText'].replace('{G}','{R}'),colors=['Red'],colorIdentity=['Red'])
            other=s.import_diagnostic_card(self.rules,renamed,0,'unseen',{'Red'})
            self.assertEqual(other.event_definition.scaled_mana_tap,'fixed:R:'+str(count))
            bad=dict(renamed,oracleText=renamed['oracleText']+'\nWin the game.')
            self.assertEqual(s.import_diagnostic_card(self.rules,bad,0,'bad',{'Red'}).kind,'unsupported')

    def test_tapping_requires_control_and_summoning_sickness_and_produces_all_mana(self):
        sim,cards=self.fixture(['Llanowar Tribe'])
        tribe=self.put(sim,cards['Llanowar Tribe'])
        self.assertNotIn(tribe.card.id,dict(sim.mana_sources(0)))
        tribe.fresh=False
        self.assertEqual(dict(sim.mana_sources(0))[tribe.card.id],((0,0,0,0,3,0),))
        self.assertNotIn(tribe.card.id,dict(sim.mana_sources(1)))
        sim.stack.priority=0
        before=len(sim.stack.items)
        sim.activate_scaled_mana(0,tribe.card.id,4)
        self.assertEqual(sim.players[0].mana_pool[4],3)
        self.assertEqual(len(sim.stack.items),before)
        self.assertTrue(tribe.tapped)
        with self.assertRaises(ValueError):sim.activate_scaled_mana(0,tribe.card.id,4)
        sim.invariant()

    def test_fixed_mana_does_not_allow_off_color_activation(self):
        sim,cards=self.fixture(['Elvish Mystic'])
        elf=self.put(sim,cards['Elvish Mystic']);elf.fresh=False
        sim.stack.priority=0
        with self.assertRaises(ValueError):sim.activate_scaled_mana(0,elf.card.id,3)
        self.assertFalse(elf.tapped)
        self.assertEqual(sim.players[0].mana_pool[4],0)

    def test_real_counted_mana_programs_and_static_anthem_composition(self):
        cases=[('Priest of Titania','count:G:Elf:all'),
               ('Elvish Archdruid','count:G:Elf:controller'),
               ('Circle of Dreams Druid','count:G:Creature:controller')]
        for name,expected in cases:
            raw=self.lookup[name]
            card=s.import_diagnostic_card(self.rules,raw,0,'count-'+name,{'Green'})
            self.assertEqual(card.kind,'creature',name)
            self.assertEqual(card.event_definition.scaled_mana_tap,expected)
            if name=='Elvish Archdruid':self.assertEqual(len(card.event_definition.static_effects),1)
            unseen=dict(raw,name='Unseen Tribal Conductor',oracleText=raw['oracleText'].replace('Elf','Goblin').replace('{G}','{R}'),colors=['Red'],colorIdentity=['Red'])
            other=s.import_diagnostic_card(self.rules,unseen,0,'new',{'Red'})
            self.assertEqual(other.kind,'creature')
            self.assertEqual(other.event_definition.scaled_mana_tap,expected.replace('Elf','Goblin').replace(':G:',':R:'))
            bad=dict(unseen,oracleText=unseen['oracleText']+'\nDestroy all lands.')
            self.assertEqual(s.import_diagnostic_card(self.rules,bad,0,'bad',{'Red'}).kind,'unsupported')

    def test_counted_mana_updates_after_token_entry_and_opponent_removal(self):
        sim,cards=self.fixture(['Priest of Titania','Elvish Archdruid','Circle of Dreams Druid'])
        priest=self.put(sim,cards['Priest of Titania'])
        arch=self.put(sim,cards['Elvish Archdruid'])
        circle=self.put(sim,cards['Circle of Dreams Druid'])
        for permanent in (priest,arch,circle):permanent.fresh=False
        def amount(permanent):return dict(sim.mana_sources(0))[permanent.card.id][0][4]
        self.assertEqual((amount(priest),amount(arch),amount(circle)),(3,3,3))
        elf=s.EventDefinition('Enemy Elf',frozenset({'Creature'}),frozenset({'Elf'}),False,1,1,frozenset())
        token=s.Card('enemy-elf','Enemy Elf','creature',event_definition=elf,is_token=True)
        sim.enter_creature(token,sim.players[1]);sim.resolve_entry_triggers([],token)
        self.assertEqual((amount(priest),amount(arch),amount(circle)),(4,3,3))
        ally=s.Card('ally-elf','Ally Elf','creature',event_definition=elf,is_token=True)
        sim.enter_creature(ally,sim.players[0]);sim.resolve_entry_triggers([],ally)
        self.assertEqual((amount(priest),amount(arch),amount(circle)),(5,4,4))
        enemy=next(p for p in sim.players[1].battlefield if p.card.id==token.id)
        sim.send_to_destination(sim.players[1],enemy)
        self.assertEqual((amount(priest),amount(arch),amount(circle)),(4,4,4))
        sim.stack.priority=0
        sim.activate_scaled_mana(0,priest.card.id,4)
        self.assertEqual(sim.players[0].mana_pool[4],4)
        sim.invariant()

    def test_real_gaears_cradle_uses_land_mana_with_live_creature_count(self):
        from card_events import parse_card
        raw=self.lookup["Gaea's Cradle"]
        definition=parse_card(raw)
        self.assertTrue(definition.supported,definition.reason)
        self.assertEqual(definition.scaled_mana_tap,'count:G:Creature:controller')
        cradle=s.import_diagnostic_card(self.rules,raw,0,'cradle',{'Green'})
        self.assertEqual(cradle.kind,'land')
        self.assertEqual(cradle.event_definition.scaled_mana_tap,
                         'count:G:Creature:controller')
        renamed=dict(raw,name='Unseen Creature Grove',
            oracleText=raw['oracleText'].replace('{G}','{R}'),
            colorIdentity=['Red'])
        other=s.import_diagnostic_card(self.rules,renamed,0,'grove',{'Red'})
        self.assertEqual(other.kind,'land')
        self.assertEqual(other.event_definition.scaled_mana_tap,
                         'count:R:Creature:controller')
        bad=dict(raw,oracleText=raw['oracleText']+'\nWin the game.')
        self.assertEqual(s.import_diagnostic_card(self.rules,bad,0,'bad',{'Green'}).kind,
                         'unsupported')
        sim=s.Simulator(self.rules,42,decks=(s.demo_deck(0)+[cradle],
                                            s.demo_deck(1)),diagnostic=True)
        owner=sim.players[0]
        (owner.hand if cradle in owner.hand else owner.library).remove(cradle)
        owner.battlefield.append(s.Permanent(cradle))
        self.assertFalse(any(choice.card_id==cradle.id
                             for choice in sim.scaled_mana_choices(0)))
        definition=s.EventDefinition('Unknown Elf',frozenset({'Creature'}),
             frozenset({'Elf'}),False,1,1,frozenset())
        opponent=s.Card('enemy','Unknown Elf','creature',
                        event_definition=definition,is_token=True)
        sim.enter_creature(opponent,sim.players[1])
        sim.resolve_entry_triggers([],opponent)
        self.assertFalse(any(choice.card_id==cradle.id
                             for choice in sim.scaled_mana_choices(0)))
        for name in ('friendly','second'):
            ally=s.Card(name,'Unknown Elf','creature',
                        event_definition=definition,is_token=True)
            sim.enter_creature(ally,owner)
            sim.resolve_entry_triggers([],ally)
        self.assertEqual(dict(sim.mana_sources(0))[cradle.id],((0,0,0,0,2,0),))
        sim.stack.priority=0
        sim.activate_scaled_mana(0,cradle.id,4)
        self.assertEqual(owner.mana_pool[4],2)
        self.assertTrue(next(p.tapped for p in owner.battlefield
                             if p.card.id==cradle.id))
        sim.invariant()
