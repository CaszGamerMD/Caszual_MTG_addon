"""Equipment grants activation and death-untap; tribal entry can move attachment."""
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
from granted_equipment_abilities import parse


TEXT=('Equipped creature has "{2}, {T}: This creature deals 1 damage to any target" '
      'and "Whenever a creature dies, untap this creature."\n'
      'Whenever a Shaman creature enters, you may attach this Equipment to it.\n'
      'Equip {4}')


class GrantedEquipmentChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.rules=s.RulesBridge()
    @classmethod
    def tearDownClass(cls):cls.rules.close()

    def source(self,text=TEXT,name='Unfamiliar staff'):
        raw=dict(name=name,layout='normal',types=['Artifact'],subTypes=['Equipment'],
                 superTypes=[],manaCost='{2}',colors=[],oracleText=text)
        return s.import_diagnostic_card(self.rules,raw,0,'grant-'+name,set())

    def creature(self,identifier,subtypes=('Shaman',),seat=0):
        definition=s.EventDefinition(identifier,frozenset({'Creature'}),frozenset(subtypes),
            False,2,3,frozenset())
        return s.Card(identifier,identifier,'creature',power=2,toughness=3,
                      traits='2;3;',event_definition=definition,is_token=True)

    def fixture(self):
        source=self.source()
        creature=self.creature('new-shaman')
        sim=s.Simulator(self.rules,97,decks=(s.demo_deck(0)+[source],s.demo_deck(1)),
                        diagnostic=True)
        self.assertFalse(sim.finished,sim.questions)
        owner=sim.players[0]
        (owner.hand if source in owner.hand else owner.library).remove(source)
        owner.battlefield.append(s.Permanent(source,attached_to=creature.id))
        owner.battlefield.append(s.Permanent(creature,fresh=False))
        sim.manual_priority=True;sim.active=0;sim.phase='main'
        sim.stack.active=0;sim.stack.priority=0
        sim.players[0].mana_pool[5]=2
        return sim,source,creature

    def test_real_thornbite_and_renamed_equipment_compile_same_program(self):
        deck=json.loads((Path(__file__).resolve().parents[1]/'decks/14509839-mono-red-gobs.json').read_text())
        raw=next(c for c in deck['mainboard'] if c['name']=='Thornbite Staff')
        real=s.import_diagnostic_card(self.rules,raw,0,'real-staff',set())
        self.assertEqual(real.kind,'equipment')
        self.assertEqual(real.event_definition.granted_equipment,
                         self.source().event_definition.granted_equipment)

    def test_equipped_creature_pays_mana_taps_and_deals_target_damage(self):
        sim,staff,creature=self.fixture()
        choices=sim.tap_damage_choices(0)
        self.assertTrue(any(c.kind=='activate_tap_damage' and c.card_id==creature.id
                            and c.tap_ids==(staff.id,) for c in choices))
        sim.activate_tap_damage(0,creature.id,'player:1',staff.id)
        self.assertEqual(sim.players[0].mana_pool[5],0)
        self.assertTrue(next(p for p in sim.players[0].battlefield if p.card.id==creature.id).tapped)
        sim.pass_priority(0);sim.pass_priority(1)
        self.assertEqual(sim.players[1].life,39)
        sim.invariant()

    def test_death_of_any_creature_untaps_equipped_creature_via_stack(self):
        sim,staff,creature=self.fixture()
        equipped=next(p for p in sim.players[0].battlefield if p.card.id==creature.id)
        equipped.tapped=True
        victim=self.creature('opponent-victim',('Elf',),seat=1)
        sim.players[1].battlefield.append(s.Permanent(victim))
        game=sim.event_game('main')
        pending=[e for e in game.death_triggers([victim.id])
                 if e.get('operation')=='untap_self']
        self.assertEqual(len(pending),1)
        sim.send_to_destination(sim.players[1],sim.players[1].battlefield[-1],snapshot=game)
        # Trigger survives even if the Equipment is removed before resolution.
        sim.send_to_destination(sim.players[0],sim.players[0].battlefield[0])
        sim._resolve_entry_effects(pending,creature)
        self.assertFalse(equipped.tapped)
        sim.invariant()

    def test_shaman_entry_autoattaches_even_to_opposing_creature(self):
        sim,staff,creature=self.fixture()
        arriving=self.creature('opponent-shaman')
        pending=sim.enter_creature(arriving,sim.players[1])
        triggers=[e for e in pending if e.get('operation')=='tribal_equipment_attach']
        self.assertEqual(len(triggers),1)
        sim._resolve_entry_effects(triggers,staff)
        equipped=next(p for p in sim.players[0].battlefield if p.card.id==staff.id)
        self.assertEqual(equipped.attached_to,arriving.id)
        sim.invariant()

    def test_parameterized_cost_damage_subtype_and_fail_closed_unknown(self):
        changed=(TEXT.replace('{2}, {T}','{3}, {T}').replace('deals 1 damage','deals 3 damage')
                 .replace('a Shaman creature','a Goblin creature').replace('Equip {4}','Equip {1}{R}'))
        other=self.source(changed,'Unseen staff of Goblins')
        self.assertEqual(other.kind,'equipment')
        self.assertEqual(other.event_definition.granted_equipment.damage,3)
        self.assertEqual(other.event_definition.granted_equipment.activation_cost,'{3}')
        self.assertEqual(other.event_definition.granted_equipment.entry_subtype,'Goblin')
        self.assertEqual(other.event_definition.attachment[1],'{1}{R}')
        self.assertEqual(self.source(TEXT+' Draw a card.').kind,'unsupported')
        self.assertIsNone(parse(TEXT,['Instant'],['Equipment']))


if __name__=='__main__':unittest.main()
