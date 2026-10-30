"""Actual enchantment programs, targeting, dynamic counts and draw ownership."""
import json
import sys
import unittest
from unittest.mock import patch
from dataclasses import replace
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
import test_final_seven as helpers

NAMES=['Ellivere of the Wild Court','Sixth Sense','All That Glitters','Ethereal Armor','Helm of the Gods']


class EnchantmentChecks(unittest.TestCase):
    token=helpers.FinalSevenChecks.token
    drain=helpers.FinalSevenChecks.drain
    ready=helpers.FinalSevenChecks.ready
    damage=helpers.FinalSevenChecks.damage

    @classmethod
    def setUpClass(cls):
        cls.rules=s.RulesBridge()
        cls.lookup={c['name']:c for p in (Path(__file__).resolve().parents[1]/'decks').glob('*.json')
                    for c in json.loads(p.read_text())['commanders']+json.loads(p.read_text())['mainboard']}

    @classmethod
    def tearDownClass(cls):cls.rules.close()

    def fixture(self,names):
        cards=[s.import_diagnostic_card(self.rules,self.lookup[n],0,'card'+str(i),{'Green','White'}) for i,n in enumerate(names)]
        self.assertTrue(all(c.kind!='unsupported' for c in cards))
        lands=[s.Card('mana'+str(i),'Mana','land',mask=63) for i in range(10)]
        sim=s.Simulator(self.rules,42,decks=(s.demo_deck(0)+cards+lands,s.demo_deck(1)),diagnostic=True)
        sim.manual_priority=True;sim.phase='main'
        p=sim.players[0]
        for c in cards+lands:(p.hand if c in p.hand else p.library).remove(c)
        p.hand.extend(cards);p.battlefield.extend(s.Permanent(c) for c in lands)
        return sim,{c.name:c for c in cards}

    def put(self,sim,card,target=None):
        sim.players[0].hand.remove(card)
        pending=sim.enter_creature(card,sim.players[0],attached_to=target)
        sim.resolve_entry_triggers(pending,card)
        return next(p for p in sim.players[0].battlefield if p.card.id==card.id)

    def roles(self,sim):
        return [p for player in sim.players for p in player.battlefield if p.card.event_definition and p.card.event_definition.role]

    def test_actual_programs_and_unfamiliar_names_reject_extra_instructions(self):
        for name in NAMES:
            raw=dict(self.lookup[name])
            raw['oracleText']=raw['oracleText'].replace('Ellivere','this creature')
            raw['name']='Unknown enchantment program'
            self.assertNotEqual(s.import_diagnostic_card(self.rules,raw,0,'x',set()).kind,'unsupported',name)
            raw['oracleText']+='\nDraw an extra card at random.'
            self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'x',set()).kind,'unsupported',name)

    def test_ellivere_entry_targets_other_creature_and_waits_for_stack(self):
        sim,cards=self.fixture([NAMES[0]])
        host=self.token(sim,'host')
        ellivere=self.put(sim,cards[NAMES[0]])
        self.assertEqual(len(self.roles(sim)),0)
        self.assertEqual(sim.stack.items[-1].payload[0]['target'],host.card.id)
        self.drain(sim)
        role=self.roles(sim)[0]
        self.assertEqual(role.attached_to,host.card.id)
        self.assertEqual(role.card.event_definition.types,frozenset({'Enchantment'}))
        self.assertFalse(sim.event_game('main').creature(sim.event_game('main').battlefield[role.card.id]))
        self.assertEqual(sim.effective_card(host).power,3)
        self.assertEqual(sim.effective_card(ellivere).power,4)
        sim.invariant()

    def test_no_self_target_and_protection_restricts_role_trigger(self):
        for protected in (False,True):
            sim,cards=self.fixture([NAMES[0]])
            if protected:self.token(sim,'host',keywords=('protection from green',))
            self.put(sim,cards[NAMES[0]])
            self.assertFalse(sim.stack.items)
            self.assertFalse(self.roles(sim))
            sim.invariant()

    def test_role_fizzles_if_target_leaves_or_gains_protection(self):
        for protection in (False,True):
            sim,cards=self.fixture([NAMES[0]])
            host=self.token(sim,'host');self.put(sim,cards[NAMES[0]])
            if protection:host.temporary_abilities=frozenset({'protection from white'})
            else:sim.send_to_destination(sim.players[0],host)
            self.drain(sim)
            self.assertFalse(self.roles(sim));sim.invariant()

    def test_role_trigger_survives_source_leaving(self):
        sim,cards=self.fixture([NAMES[0]])
        host=self.token(sim,'host');source=self.put(sim,cards[NAMES[0]])
        sim.send_to_destination(sim.players[0],source);self.drain(sim)
        self.assertEqual(self.roles(sim)[0].attached_to,host.card.id)
        sim.invariant()

    def test_attack_replaces_previous_role_after_resolution(self):
        sim,cards=self.fixture([NAMES[0]])
        host=self.token(sim,'host',power=6,toughness=6)
        source=self.put(sim,cards[NAMES[0]]);self.drain(sim)
        first=self.roles(sim)[0].card.id
        self.ready(sim);sim.declare_attackers([source.card.id])
        self.assertEqual(self.roles(sim)[0].card.id,first)
        self.drain(sim)
        self.assertEqual(len(self.roles(sim)),1)
        self.assertNotEqual(self.roles(sim)[0].card.id,first)
        self.assertEqual(sim.effective_card(host).power,7)
        self.assertEqual(host.counters,0)
        sim.invariant()

    def test_roles_of_different_controllers_coexist_and_blink_removes_roles(self):
        sim,cards=self.fixture([NAMES[0]])
        host=self.token(sim,'host');self.put(sim,cards[NAMES[0]]);self.drain(sim)
        role=self.roles(sim)[0]
        other=replace(role.card,id='enemy-role')
        sim.enter_creature(other,sim.players[1],attached_to=host.card.id)
        sim.resolve_entry_triggers([],other)
        self.assertEqual(len(self.roles(sim)),2)
        self.assertEqual(sim.effective_card(host).power,4)
        sim.blink_permanent(0,host)
        self.assertFalse(self.roles(sim));sim.invariant()

    def test_glitters_counts_artifact_enchantment_once_and_tracks_source_controller(self):
        sim,cards=self.fixture(['All That Glitters'])
        host=self.token(sim,'host');aura=self.put(sim,cards['All That Glitters'],host.card.id)
        d=s.EventDefinition('Both types',frozenset({'Artifact','Enchantment'}),frozenset(),False,0,0,frozenset())
        dual=s.Card('dual','Both types','artifact',event_definition=d,is_token=True)
        sim.enter_creature(dual,sim.players[0])
        sim.enter_creature(replace(dual,id='enemy'),sim.players[1])
        self.assertEqual(sim.effective_card(host).power,4) # Aura + dual, counted once.
        own=next(p for p in sim.players[0].battlefield if p.card.id=='dual')
        sim.send_to_destination(sim.players[0],own)
        self.assertEqual(sim.effective_card(host).power,3)
        # Aura controller's count, even when enchanting the opponent's creature.
        sim.players[0].battlefield.remove(host);sim.players[1].battlefield.append(host)
        self.assertEqual(sim.effective_card(host).power,3)
        sim.invariant()


    def test_unseen_aura_creature_enchantment_union_counts_each_permanent_once(self):
        raw=dict(self.lookup['All That Glitters'],
                 name='Unseen Grove Blessing',
                 oracleText='Enchant creature\nEnchanted creature gets +1/+1 for each creature and/or enchantment you control.')
        card=s.import_diagnostic_card(self.rules,raw,0,'counted-aura',{'Green','White'})
        self.assertEqual(card.kind,'aura')
        self.assertEqual(card.event_definition.attachment_scale,(1,1,('Creature','Enchantment')))
        sim=s.Simulator(self.rules,42,decks=(s.demo_deck(0)+[card],s.demo_deck(1)),diagnostic=True)
        sim.manual_priority=True;sim.phase='main'
        host=self.token(sim,'host')
        player=sim.players[0]
        (player.hand if card in player.hand else player.library).remove(card)
        sim.enter_creature(card,player,attached_to=host.card.id)
        self.assertEqual(sim.effective_card(host).power,4) # Host plus Aura.
        both=s.EventDefinition('Dual enchantment creature',
                 frozenset({'Creature','Enchantment'}),frozenset(),False,2,2,frozenset())
        double=s.Card('double','Dual enchantment creature','creature',
                      power=2,toughness=2,event_definition=both,is_token=True)
        sim.enter_creature(double,player)
        sim.enter_creature(replace(double,id='enemy-double'),sim.players[1])
        self.assertEqual(sim.effective_card(host).power,5) # Dual type counts once.
        item=next(x for x in player.battlefield if x.card.id=='double')
        sim.send_to_destination(player,item)
        self.assertEqual(sim.effective_card(host).power,4)
        self.assertNotIn('enemy-double',[p.card.id for p in player.battlefield])
        sim.invariant()

    def test_union_counterparts_and_unknown_instructions_fail_closed(self):
        source=self.lookup['All That Glitters']
        for types in ('artifact and/or creature','artifact and/or enchantment',
                      'creature and/or enchantment','creature'):
            raw=dict(source,name='Unseen Counted Aura',oracleText=
                     'Enchant creature\nEnchanted creature gets +2/+1 for each '+types+' you control.')
            card=s.import_diagnostic_card(self.rules,raw,0,'count',{'White'})
            self.assertEqual(card.kind,'aura',types)
            self.assertEqual(card.event_definition.attachment_scale[0:2],(2,1))
            raw['oracleText']+='\nWhenever an unknown event happens, win.'
            self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'bad',{'White'}).kind,
                             'unsupported')
        same=dict(source,name='Unseen Counted Aura',oracleText=
                  'Enchant creature\nEnchanted creature gets +1/+1 for each creature and/or creature you control.')
        self.assertEqual(s.import_diagnostic_card(self.rules,same,0,'bad-duplicate',{'White'}).kind,
                         'unsupported')

    def test_armor_counts_itself_and_helm_does_not_make_creature_enchanted(self):
        sim,cards=self.fixture(['Ethereal Armor','Helm of the Gods'])
        host=self.token(sim,'host');equipment=self.put(sim,cards['Helm of the Gods'])
        sim.activate_equip(0,equipment.card.id,host.card.id);self.drain(sim)
        self.assertEqual(sim.effective_card(host).power,2)
        self.assertFalse(sim.event_game('main').enchanted(sim.event_game('main').battlefield[host.card.id]))
        self.put(sim,cards['Ethereal Armor'],host.card.id)
        self.assertEqual(sim.effective_card(host).power,4)
        self.assertIn('first strike',sim.effective_card(host).traits)
        sim.invariant()

    def test_ellivere_draws_per_enchanted_damage_source_per_strike(self):
        sim,cards=self.fixture([NAMES[0],'Sixth Sense'])
        first=self.token(sim,'first',keywords=('double strike',))
        second=self.token(sim,'second')
        self.put(sim,cards['Sixth Sense'],first.card.id)
        source=self.put(sim,cards[NAMES[0]]);self.drain(sim)
        # Make both creatures enchanted, including the ordinary Aura host.
        role=self.roles(sim)[0];role.attached_to=second.card.id
        before=len(sim.players[0].hand)
        self.ready(sim);sim.declare_attackers([first.card.id,second.card.id]);self.drain(sim)
        sim.declare_blockers({});self.damage(sim)
        # Ellivere: first twice + second once. Sixth Sense: first twice.
        self.assertEqual(len(sim.players[0].hand),before+5)
        sim.invariant()

    def test_damage_trigger_uses_predeath_state_and_survives_aura_leaving(self):
        sim,cards=self.fixture(['Sixth Sense'])
        host=self.token(sim,'host');aura=self.put(sim,cards['Sixth Sense'],host.card.id)
        before=len(sim.players[0].hand)
        self.ready(sim);sim.declare_attackers([host.card.id]);sim.declare_blockers({})
        sim.group_damage_step()
        self.assertTrue(sim.stack.items)
        sim.send_to_destination(sim.players[0],aura)
        self.drain(sim)
        self.assertEqual(len(sim.players[0].hand),before+1)
        sim.invariant()

    def test_sixth_sense_trigger_belongs_to_enchanted_creature_controller(self):
        sim,cards=self.fixture(['Sixth Sense'])
        host=self.token(sim,'enemy-host',1)
        self.put(sim,cards['Sixth Sense'],host.card.id)
        sim.active=1;sim.stack.active=1;sim.stack.priority=1;sim.phase='attack'
        before=[len(p.hand) for p in sim.players]
        sim.declare_attackers([host.card.id]);sim.declare_blockers({});self.damage(sim)
        self.assertEqual([len(p.hand) for p in sim.players],[before[0],before[1]+1])
        sim.invariant()

    def test_legacy_single_attacker_path_also_dispatches_combat_draw(self):
        sim,cards=self.fixture(['Sixth Sense'])
        host=self.token(sim,'host')
        self.put(sim,cards['Sixth Sense'],host.card.id)
        before=len(sim.players[0].hand)
        sim.phase='block';sim.pending=host.card.id
        with patch.object(sim,'decide',return_value=s.Candidate('take','block')):sim.step()
        self.drain(sim)
        self.assertEqual(len(sim.players[0].hand),before+1)
        sim.invariant()

    def test_optional_draw_can_decline_empty_library_but_mandatory_draw_loses(self):
        for mandatory in (False,True):
            sim,cards=self.fixture([NAMES[0]] if mandatory else ['Sixth Sense'])
            host=self.token(sim,'host')
            self.put(sim,next(iter(cards.values())),None if mandatory else host.card.id)
            self.drain(sim)
            p=sim.players[0];p.graveyard.extend(p.library);p.library.clear()
            self.ready(sim);sim.declare_attackers([host.card.id]);sim.declare_blockers({});self.damage(sim)
            self.assertEqual(p.failed_draw,mandatory)
            self.assertEqual(sim.finished,mandatory)
            sim.invariant()
