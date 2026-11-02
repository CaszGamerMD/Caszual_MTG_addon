"""Goaded Aura doubles enchanted creature combat damage; paid graveyard return."""
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
from goad_damage_aura import parse


TEXT=('Enchant creature\nEnchanted creature is goaded.\n'
      'If enchanted creature would deal combat damage to a permanent or player, '
      'it deals double that damage instead.\n'
      '{2}{R}: Return this card from your graveyard to your hand.')


class GoadDamageAuraChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.rules=s.RulesBridge()
    @classmethod
    def tearDownClass(cls):cls.rules.close()

    def source(self,text=TEXT,name='Unfamiliar battle music'):
        raw=dict(name=name,layout='normal',types=['Enchantment'],subTypes=['Aura'],
                 superTypes=[],manaCost='{2}{R}',colors=['Red'],oracleText=text)
        return s.import_diagnostic_card(self.rules,raw,0,'goad-'+name,{'Red'})

    def creature(self):
        definition=s.EventDefinition('New bandit',frozenset({'Creature'}),
            frozenset({'Warrior'}),False,2,3,frozenset())
        return s.Card('new-bandit','New bandit','creature',power=2,toughness=3,
                      traits='2;3;',event_definition=definition,is_token=True)

    def fixture(self):
        aura=self.source();creature=self.creature()
        sim=s.Simulator(self.rules,67,decks=(s.demo_deck(0)+[aura],s.demo_deck(1)),
                        diagnostic=True)
        self.assertFalse(sim.finished,sim.questions)
        owner=sim.players[0]
        (owner.hand if aura in owner.hand else owner.library).remove(aura)
        owner.battlefield.append(s.Permanent(aura,attached_to=creature.id))
        sim.players[1].battlefield.append(s.Permanent(creature,fresh=False))
        sim.manual_priority=True;sim.active=1;sim.phase='main'
        sim.stack.active=1;sim.stack.priority=1
        return sim,aura,creature

    def test_real_sound_of_drums_and_renamed_aura_share_program(self):
        deck=json.loads((Path(__file__).resolve().parents[1]/'decks/14509839-mono-red-gobs.json').read_text())
        raw=next(c for c in deck['mainboard'] if c['name']=='The Sound of Drums')
        real=s.import_diagnostic_card(self.rules,raw,0,'real-drums',{'Red'})
        self.assertEqual(real.kind,'aura')
        self.assertEqual(real.event_definition.goad_damage_aura,
                         self.source().event_definition.goad_damage_aura)

    def test_enchanted_creature_must_attack_and_combat_damage_doubles_only(self):
        sim,aura,creature=self.fixture()
        game=sim.event_game('combat')
        self.assertTrue(game.must_attack(game.battlefield[creature.id]))
        self.assertEqual(sim.replaced_damage(2,creature,1,0,combat=True),4)
        self.assertEqual(sim.replaced_damage(2,creature,1,0,
                                            target_permanent='creature-target',combat=True),4)
        self.assertEqual(sim.replaced_damage(2,creature,1,0,combat=False),2)
        sim.players[0].battlefield[0].attached_to=None
        game=sim.event_game('combat')
        self.assertFalse(game.must_attack(game.battlefield[creature.id]))
        self.assertEqual(sim.replaced_damage(2,creature,1,0,combat=True),2)
        sim.invariant()

    def test_group_combat_uses_double_damage_to_opponent(self):
        sim,aura,creature=self.fixture()
        sim.group_combat=dict(attackers=[creature.id],blocks={},blocked=set(),early=None)
        sim.phase='group_damage_start'
        sim.group_damage_step()
        self.assertEqual(sim.players[0].life,36)
        sim.invariant()

    def test_graveyard_return_pays_mana_and_resolves_on_stack(self):
        sim,aura,creature=self.fixture()
        sim.send_to_destination(sim.players[0],sim.players[0].battlefield[0])
        sim.players[0].mana_pool=[0,0,0,1,0,2]
        sim.stack.priority=0
        self.assertTrue(sim.aura_graveyard_return_choices(0))
        sim.activate_aura_graveyard_return(0,aura.id)
        self.assertEqual(sim.players[0].mana_pool,[0]*6)
        self.assertIn(aura,sim.players[0].graveyard)
        sim.pass_priority(0);sim.pass_priority(1)
        self.assertNotIn(aura,sim.players[0].graveyard)
        self.assertIn(aura,sim.players[0].hand)
        sim.invariant()

    def test_parameterized_cost_and_unknown_extra_clause_fail_closed(self):
        altered=self.source(TEXT.replace('{2}{R}: Return','{1}{G}: Return'),
                            name='New green soundtrack')
        self.assertEqual(altered.kind,'aura')
        self.assertEqual(altered.event_definition.goad_damage_aura.return_cost,'{1}{G}')
        self.assertEqual(self.source(TEXT+' Draw a card.').kind,'unsupported')
        self.assertEqual(self.source(TEXT.replace('combat damage','damage')).kind,'unsupported')
        self.assertIsNone(parse(TEXT,['Creature'],['Aura']))


if __name__=='__main__':unittest.main()
