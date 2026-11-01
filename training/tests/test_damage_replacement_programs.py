"""Typed, continuously applied damage replacements rather than life-loss hooks."""
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from damage_replacement_programs import parse
import simulator as s


FLOOR=('Damage that would reduce your life total to less than 1 '
       'reduces it to 1 instead.')
CREATURE_DOUBLE=('If a creature you control would deal damage to a permanent '
                 'or player, it deals double that damage instead.')
RED_ARTIFACT_BONUS=('If a red or artifact source you control would deal damage '
                    'to an opponent or a permanent an opponent controls, '
                    'it deals that much damage plus 1 instead.')
GLOBAL_DOUBLE=('Flash\nIf a source would deal damage to a permanent or player, '
               'it deals double that damage to that permanent or player instead.')


class DamageReplacementChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.rules=s.RulesBridge()
    @classmethod
    def tearDownClass(cls):cls.rules.close()

    def source(self,text=FLOOR,name='New life shield'):
        raw=dict(name=name,layout='normal',types=['Creature'],subTypes=[],
            superTypes=[],manaCost='{2}{R}',colors=['Red'],power='1',toughness='1',
            oracleText=text)
        return s.import_diagnostic_card(self.rules,raw,0,'damage-replacement',{'Red'})

    def enchantment(self,text,name='Unfamiliar violence'):
        raw=dict(name=name,layout='normal',types=['Enchantment'],subTypes=[],
            superTypes=[],manaCost='{3}{R}{R}',colors=['Red'],oracleText=text)
        return s.import_diagnostic_card(self.rules,raw,1,
            'damage-'+name.lower().replace(' ','-'),{'Red'})

    def fixture(self,source,owner=0,attacker_colors=(),extra_sources=()):
        attacker=s.Card('heavy-attacker','Heavy attacker','creature',power=10,toughness=3,
            traits='10;3;lifelink',mana_cost='{1}',colors=frozenset(attacker_colors),
            event_definition=s.EventDefinition('Heavy attacker',frozenset({'Creature'}),
                frozenset(),False,10,3,frozenset({'lifelink'}),
                colors=frozenset(attacker_colors)))
        sim=s.Simulator(self.rules,77,
            decks=(s.demo_deck(0)+([source] if owner==0 else []),
                   s.demo_deck(1)+[attacker]+([source] if owner==1 else [])+
                   list(extra_sources)),diagnostic=True)
        self.assertFalse(sim.finished,sim.questions)
        for seat,cards in ((0,[source] if owner==0 else []),
                           (1,[attacker]+([source] if owner==1 else [])+
                            list(extra_sources))):
            p=sim.players[seat]
            for card in cards:(p.hand if card in p.hand else p.library).remove(card)
            p.battlefield.extend(s.Permanent(card) for card in cards)
        sim.players[0].life=3
        sim.active=1;sim.manual_priority=True;sim.phase='main'
        return sim,attacker

    def test_real_ali_and_renamed_creature_compile_same_floor(self):
        deck=json.loads((Path(__file__).resolve().parents[1]/'decks/14509839-mono-red-gobs.json').read_text())
        raw=next(c for c in deck['mainboard'] if c['name']=='Ali from Cairo')
        real=s.import_diagnostic_card(self.rules,raw,0,'real-ali',{'Red'})
        self.assertEqual(real.kind,'creature')
        self.assertEqual(real.event_definition.damage_replacement,
                         self.source().event_definition.damage_replacement)

    def test_damage_event_caps_at_one_life_with_no_stack_trigger(self):
        source=self.source();sim,attacker=self.fixture(source)
        self.assertEqual(sim.replaced_damage(10,attacker,1,0),2)
        self.assertEqual(sim.replaced_damage(10,source,0,1),10)
        sim._resolve_entry_effects([dict(operation='damage',controller=1,
            source=attacker.id,name=attacker.name,amount=10)],attacker)
        self.assertEqual(sim.players[0].life,1)
        self.assertFalse(any(e['kind']=='life_replacement' for e in sim.events))
        sim.invariant()

    def test_combat_preview_and_first_strike_pipeline_use_actual_damage(self):
        source=self.source();sim,attacker=self.fixture(source)
        result=sim.damage(attacker,None)
        self.assertEqual(result['damage'],2)
        self.assertEqual(result['gainA'],2)  # lifelink uses dealt damage, not original power
        sim.combat_context=dict(attacker=attacker.id,blocker=None,
                                early=set(),blocked=False)
        sim.strike_damage_step(False)
        self.assertEqual(sim.players[0].life,1)
        self.assertEqual(sim.players[1].life,42)
        sim.invariant()

    def test_floor_expires_when_source_leaves_and_does_not_rewrite_life_loss(self):
        source=self.source();sim,attacker=self.fixture(source)
        self.assertEqual(sim.replaced_damage(8,attacker,1,0),2)
        sim.players[0].battlefield.remove(next(p for p in sim.players[0].battlefield
                                                if p.card==source))
        sim.players[0].graveyard.append(source)
        self.assertEqual(sim.replaced_damage(8,attacker,1,0),8)
        sim.players[0].life-=2  # life loss is an independent rule action, not damage
        self.assertEqual(sim.players[0].life,1)
        sim.invariant()

    def test_unknown_extra_text_and_wrong_types_rejected(self):
        for text in (FLOOR+' Draw a card.',
                     FLOOR.replace('less than 1','less than 2'),
                     FLOOR.replace('Damage','Life loss')):
            with self.subTest(text=text):
                self.assertIsNone(parse(text,['Creature']))
                self.assertEqual(self.source(text).kind,'unsupported')
        self.assertIsNone(parse(FLOOR,['Enchantment']))

    def test_changed_life_floor_amount_remains_parameterized(self):
        oracle=FLOOR.replace('less than 1','less than 2').replace('to 1 instead','to 2 instead')
        source=self.source(oracle,name='Unfamiliar life safeguard')
        self.assertEqual(source.kind,'creature')
        sim,attacker=self.fixture(source)
        self.assertEqual(sim.replaced_damage(10,attacker,1,0),1)
        sim.invariant()

    def test_real_violence_and_unfamiliar_enchantment_share_program(self):
        deck=json.loads((Path(__file__).resolve().parents[1]/'decks/14509839-mono-red-gobs.json').read_text())
        real=next(c for c in deck['mainboard'] if c['name']=='Gratuitous Violence')
        actual=s.import_diagnostic_card(self.rules,real,1,'real-violence',{'Red'})
        self.assertEqual(actual.kind,'enchantment')
        self.assertEqual(actual.event_definition.damage_replacement,
                         self.enchantment(CREATURE_DOUBLE).event_definition.damage_replacement)

    def test_controlled_creature_doubles_player_and_permanent_damage(self):
        source=self.enchantment(CREATURE_DOUBLE)
        sim,attacker=self.fixture(source,owner=1)
        sim.players[0].life=40
        self.assertEqual(sim.replaced_damage(3,attacker,1,0),6)
        self.assertEqual(sim.replaced_damage(3,attacker,1,0,target_permanent='creature-x'),6)
        self.assertEqual(sim.replaced_damage(3,attacker,0,0),3)
        noncreature=s.Card('burn-spell','Burn spell','spell')
        self.assertEqual(sim.replaced_damage(3,noncreature,1,0),3)
        self.assertEqual(sim.damage(attacker,None)['damage'],20)
        self.assertEqual(sim.damage(attacker,None)['gainA'],20)
        sim.invariant()

    def test_group_combat_uses_replaced_damage_and_lifelink(self):
        source=self.enchantment(CREATURE_DOUBLE)
        sim,attacker=self.fixture(source,owner=1)
        sim.players[0].life=40
        sim.group_combat=dict(attackers=[attacker.id],blocks={},blocked=set(),early=None)
        sim.phase='group_damage_start'
        sim.group_damage_step()
        self.assertEqual(sim.players[0].life,20)
        self.assertEqual(sim.players[1].life,60)
        sim.invariant()

    def test_damage_trigger_to_creature_is_doubled_before_lethal_check(self):
        source=self.enchantment(CREATURE_DOUBLE)
        sim,attacker=self.fixture(source,owner=1)
        defender=sim.players[0]
        target=next(c for c in defender.library if c.kind=='creature')
        defender.library.remove(target)
        defender.battlefield.append(s.Permanent(target))
        sim._resolve_entry_effects([dict(operation='damage_any_target',
            source=attacker.id,name=attacker.name,controller=1,amount=1,
            targetKind='permanent',target=target.id,sourceColors=[])],attacker)
        self.assertTrue(any(e['kind']=='damage_any_target' and e['details']['amount']==2
                            for e in sim.events))
        sim.invariant()

    def test_violence_expires_off_battlefield_and_unknown_text_fails(self):
        source=self.enchantment(CREATURE_DOUBLE)
        sim,attacker=self.fixture(source,owner=1)
        self.assertEqual(sim.replaced_damage(2,attacker,1,0),4)
        sim.players[1].battlefield.remove(next(p for p in sim.players[1].battlefield
                                                if p.card==source))
        sim.players[1].graveyard.append(source)
        self.assertEqual(sim.replaced_damage(2,attacker,1,0),2)
        self.assertEqual(self.enchantment(CREATURE_DOUBLE+' Draw a card.').kind,'unsupported')
        sim.invariant()

    def test_mechanized_warfare_and_unknown_named_source_share_bonus_program(self):
        deck=json.loads((Path(__file__).resolve().parents[1]/'decks/14509839-mono-red-gobs.json').read_text())
        raw=next(c for c in deck['mainboard'] if c['name']=='Mechanized Warfare')
        real=s.import_diagnostic_card(self.rules,raw,1,'real-mechanized',{'Red'})
        self.assertEqual(real.kind,'enchantment')
        self.assertEqual(real.event_definition.damage_replacement,
                         self.enchantment(RED_ARTIFACT_BONUS).event_definition.damage_replacement)

    def test_red_and_artifact_sources_gain_one_only_against_opponents(self):
        source=self.enchantment(RED_ARTIFACT_BONUS)
        sim,attacker=self.fixture(source,owner=1,attacker_colors=('Red',))
        artifact=s.Card('art-source','Unseen machinery','artifact',
            event_definition=s.EventDefinition('Unseen machinery',frozenset({'Artifact'}),
                frozenset(),False,0,0,frozenset()))
        spell=s.Card('red-spell','Unseen flame','spell',colors=frozenset({'Red'}))
        plain=s.Card('plain','Colorless spell','spell')
        for card in (attacker,artifact,spell):
            self.assertEqual(sim.replaced_damage(2,card,1,0),3)
            self.assertEqual(sim.replaced_damage(2,card,1,0,target_permanent='opponent-creature'),3)
            self.assertEqual(sim.replaced_damage(2,card,1,1,target_permanent='own-creature'),2)
            self.assertEqual(sim.replaced_damage(2,card,0,0),2)
        self.assertEqual(sim.replaced_damage(2,plain,1,0),2)
        sim.invariant()

    def test_changed_damage_bonus_amount_and_flashless_global_double(self):
        bonus=self.enchantment(RED_ARTIFACT_BONUS.replace('plus 1','plus 3'))
        self.assertEqual(bonus.kind,'enchantment')
        sim,attacker=self.fixture(bonus,owner=1,attacker_colors=('Red',))
        self.assertEqual(sim.replaced_damage(2,attacker,1,0),5)
        no_flash=self.enchantment(GLOBAL_DOUBLE.removeprefix('Flash\n'))
        self.assertEqual(no_flash.kind,'enchantment')
        self.assertFalse(no_flash.instant)
        sim.invariant()

    def test_damage_event_applies_bonus_and_loses_it_when_source_leaves(self):
        source=self.enchantment(RED_ARTIFACT_BONUS)
        sim,attacker=self.fixture(source,owner=1,attacker_colors=('Red',))
        sim.players[0].life=20
        sim._resolve_entry_effects([dict(operation='damage',controller=1,
            source=attacker.id,name=attacker.name,amount=2)],attacker)
        self.assertEqual(sim.players[0].life,17)
        sim.players[1].battlefield.remove(next(p for p in sim.players[1].battlefield
                                                if p.card==source))
        sim.players[1].graveyard.append(source)
        sim._resolve_entry_effects([dict(operation='damage',controller=1,
            source=attacker.id,name=attacker.name,amount=2)],attacker)
        self.assertEqual(sim.players[0].life,15)
        self.assertEqual(self.enchantment(RED_ARTIFACT_BONUS+' Draw a card.').kind,'unsupported')
        sim.invariant()

    def test_dictate_of_twin_gods_and_renamed_flash_enchantment(self):
        deck=json.loads((Path(__file__).resolve().parents[1]/'decks/14509839-mono-red-gobs.json').read_text())
        raw=next(c for c in deck['mainboard'] if c['name']=='Dictate of the Twin Gods')
        real=s.import_diagnostic_card(self.rules,raw,1,'real-dictate',{'Red'})
        other=self.enchantment(GLOBAL_DOUBLE,name='New global damage echo')
        self.assertEqual(real.kind,'enchantment')
        self.assertEqual(real.event_definition.damage_replacement,
                         other.event_definition.damage_replacement)
        self.assertTrue(other.instant)  # whole-text Flash actually grants instant-speed casting
        self.assertIn('flash',other.event_definition.abilities)

    def test_global_double_applies_to_any_source_and_both_players(self):
        source=self.enchantment(GLOBAL_DOUBLE)
        sim,attacker=self.fixture(source,owner=1)
        spell=s.Card('unseen-spell','Unseen neutral damage','spell')
        for controller,target in ((0,1),(1,0)):
            self.assertEqual(sim.replaced_damage(3,spell,controller,target),6)
            self.assertEqual(sim.replaced_damage(3,attacker,controller,target,
                                                target_permanent='creature-target'),6)
        self.assertEqual(sim.damage(attacker,None)['damage'],20)
        self.assertEqual(sim.damage(attacker,None)['gainA'],20)
        sim.invariant()

    def test_deterministic_ordering_of_two_applicable_replacements(self):
        bonus=self.enchantment(RED_ARTIFACT_BONUS,name='A bonus replacement')
        doubling=self.enchantment(GLOBAL_DOUBLE,name='Z global replacement')
        sim,attacker=self.fixture(bonus,owner=1,attacker_colors=('Red',),
                                  extra_sources=(doubling,))
        # The affected player may choose either order in Magic. This
        # diagnostic uses stable physical-id order as its legal policy.
        self.assertEqual(sim.replaced_damage(3,attacker,1,0),8)
        self.assertEqual(sim.replaced_damage(3,attacker,1,0,
                                             target_permanent='enemy-creature'),8)
        sim.invariant()

    def test_life_floor_is_applied_after_global_double(self):
        shield=self.source()
        doubling=self.enchantment(GLOBAL_DOUBLE)
        sim,attacker=self.fixture(shield,owner=0,extra_sources=(doubling,))
        self.assertEqual(sim.replaced_damage(10,attacker,1,0),2)
        sim._resolve_entry_effects([dict(operation='damage',controller=1,
            source=attacker.id,name=attacker.name,amount=10)],attacker)
        self.assertEqual(sim.players[0].life,1)
        sim.invariant()

    def test_global_double_fails_closed_on_extra_text(self):
        source=self.enchantment(GLOBAL_DOUBLE+' Gain 2 life.')
        self.assertEqual(source.kind,'unsupported')
        self.assertIsNone(parse(GLOBAL_DOUBLE,['Instant']))


if __name__=='__main__':unittest.main()
