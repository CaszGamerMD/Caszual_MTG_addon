import sys
from pathlib import Path
import unittest
from dataclasses import replace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from card_events import parse_card, Game, Permanent, Definition
from oracle_abilities import compile_abilities, parse_token_creation
import simulator as s

class CounterDependentKeywordChecks(unittest.TestCase):
    def test_real_bramblewood_paragon_grants_live_trample(self):
        import json
        deck=json.loads((Path(__file__).resolve().parents[1]/'decks'/
                         '14435337-lupitas-elves.json').read_text())
        raw=next(c for c in deck['mainboard'] if c['name']=='Bramblewood Paragon')
        definition=parse_card(raw)
        self.assertTrue(definition.supported,definition.reason)
        self.assertEqual(len(definition.entry_counter_grants),1)
        self.assertEqual(len(definition.static_effects),1)
        self.assertTrue(definition.static_effects[0].requires_plus_one_counter)
        with s.RulesBridge() as rules:
            card=s.import_diagnostic_card(rules,raw,0,'bramble',{'Green'})
            self.assertNotEqual(card.kind,'unsupported')
        warrior=Definition('Unknown Warrior',frozenset({'Creature'}),
                           frozenset({'Warrior'}),False,1,1,frozenset())
        elf=Definition('Unknown Elf',frozenset({'Creature'}),
                       frozenset({'Elf'}),False,1,1,frozenset())
        game=Game()
        source=Permanent('paragon',definition,0)
        game.enter(source)
        ally=Permanent('warrior',warrior,0)
        enemy=Permanent('enemy',warrior,1)
        other=Permanent('elf',elf,0)
        game.enter(ally)
        game.enter(enemy)
        game.enter(other)
        self.assertEqual(ally.counters,1)
        self.assertEqual(enemy.counters,0)
        self.assertEqual(other.counters,0)
        self.assertTrue(game.has(ally,'trample'))
        self.assertFalse(game.has(other,'trample'))
        self.assertFalse(game.has(enemy,'trample'))
        ally.counters=0
        self.assertFalse(game.has(ally,'trample'))
        other.counters=1
        self.assertTrue(game.has(other,'trample'))
        del game.battlefield['paragon']
        self.assertFalse(game.has(other,'trample'))

    def test_unknown_counter_keyword_and_remainder(self):
        raw=dict(name='Unseen Trainer',types=['Creature'],
                 power='2',toughness='2',
                 oracleText='Each creature you control with a +1/+1 counter on it has trample.')
        self.assertTrue(parse_card(raw).supported)
        self.assertFalse(parse_card(dict(raw,
            oracleText=raw['oracleText']+' You win the game.')).supported)


class SubtypeCountedLifeChecks(unittest.TestCase):
    def test_renamed_tribal_life_tap_and_unknown_remainder(self):
        for subtype,scope in [('Elf','all'),('Goblin','controller'),('Faerie','all')]:
            phrase='on the battlefield' if scope=='all' else 'you control'
            raw=dict(name='Unseen Healer',types=['Creature'],
                subTypes=[subtype],power='1',toughness='1',
                oracleText=f'{{T}}: You gain 2 life for each {subtype} {phrase}.')
            definition=parse_card(raw)
            self.assertTrue(definition.supported,definition.reason)
            self.assertEqual(definition.scaled_life_tap,(2,subtype,scope))
            self.assertFalse(parse_card(dict(raw,
                oracleText=raw['oracleText']+'\nCreate an unknown reward.')).supported)

    def test_real_wellwisher_counts_both_players_and_changelings(self):
        import json
        deck=json.loads((Path(__file__).resolve().parents[1]/'decks'/
                         '14435337-lupitas-elves.json').read_text())
        raw=next(c for c in deck['mainboard'] if c['name']=='Wellwisher')
        definition=parse_card(raw)
        self.assertTrue(definition.supported,definition.reason)
        self.assertEqual(definition.scaled_life_tap,(1,'Elf','all'))
        with s.RulesBridge() as rules:
            card=s.import_diagnostic_card(rules,raw,0,'wellwisher',{'Green'})
            self.assertNotEqual(card.kind,'unsupported')
            sim=s.Simulator(rules,42,decks=(s.demo_deck(0)+[card],
                s.demo_deck(1)),diagnostic=True)
            sim.manual_priority=True;sim.phase='main';sim.stack.priority=0
            owner=sim.players[0]
            (owner.hand if card in owner.hand else owner.library).remove(card)
            pending=sim.enter_creature(card,owner)
            sim.resolve_entry_triggers(pending,card)
            original=next(p for p in owner.battlefield if p.card.id==card.id)
            for index,(seat,subtypes,keywords) in enumerate([
                    (0,('Elf',),()),(1,('Elf',),()),
                    (0,('Shapeshifter',),('changeling',))]):
                creature=s.EventDefinition('Unknown Ally',frozenset({'Creature'}),
                    frozenset(subtypes),False,1,1,frozenset(keywords))
                unit=s.Card('ally'+str(index),'Unknown Ally','creature',
                    power=1,toughness=1,event_definition=creature,is_token=True)
                pending=sim.enter_creature(unit,sim.players[seat])
                sim.resolve_entry_triggers(pending,unit)
            before=owner.life
            with self.assertRaises(ValueError):sim.activate_scaled_life(0,card.id)
            original.fresh=False
            sim.activate_scaled_life(0,card.id)
            self.assertEqual(owner.life,before+4)
            self.assertTrue(original.tapped)
            with self.assertRaises(ValueError):sim.activate_scaled_life(0,card.id)
            sim.invariant()


class TribalSacrificeTokenChecks(unittest.TestCase):
    def test_unseen_death_trigger_and_paid_tribal_sacrifice_compose(self):
        text=("Whenever this creature or another Goblin you control dies, "
              "this creature deals 1 damage to any target.\n"
              "{3}{R}, Sacrifice a Goblin: Create two 1/1 red Goblin creature tokens.")
        raw=dict(name='Unseen Goblin Chief',types=['Creature'],
                 subTypes=['Goblin'],power='2',toughness='2',oracleText=text)
        definition=parse_card(raw)
        self.assertTrue(definition.supported,definition.reason)
        self.assertEqual(len(definition.triggers),1)
        self.assertEqual(definition.triggers[0].subject.self_or_controlled_subtype,'Goblin')
        self.assertEqual(definition.triggers[0].effect.operation,'damage_any_target')
        self.assertEqual(len(definition.sacrifice_token_activations),1)
        mana,subtype,spec=definition.sacrifice_token_activations[0]
        self.assertEqual((mana,subtype,spec.amount),('{3}{R}','Goblin',2))
        goblin=Definition('Other Goblin',frozenset({'Creature'}),
            frozenset({'Goblin'}),False,1,1,frozenset())
        game=Game()
        game.enter(Permanent('source',definition,0))
        game.enter(Permanent('friend',goblin,0))
        game.enter(Permanent('enemy',goblin,1))
        self.assertEqual(len(game.death_triggers(['friend'])),1)
        self.assertEqual(len(game.death_triggers(['enemy'])),0)
        self.assertEqual(len(game.death_triggers(['source'])),1)
        self.assertEqual(len(game.death_triggers(['source','friend'])),2)
        self.assertFalse(parse_card(dict(raw,oracleText=text+'\nWin the game.')).supported)

    def test_real_pashalik_pays_cost_and_pings_before_creating_two_tokens(self):
        import json
        deck=json.loads((Path(__file__).resolve().parents[1]/'decks'/
                         '14509839-mono-red-gobs.json').read_text())
        raw=next(c for c in deck['mainboard'] if c['name']=='Pashalik Mons')
        definition=parse_card(raw)
        self.assertTrue(definition.supported,definition.reason)
        with s.RulesBridge() as rules:
            card=s.import_diagnostic_card(rules,raw,0,'pashalik',{'Red'})
            self.assertNotEqual(card.kind,'unsupported')
            lands=[s.Card('mana'+str(i),'Mana','land',mask=63) for i in range(4)]
            sim=s.Simulator(rules,42,decks=(s.demo_deck(0)+[card]+lands,
                                            s.demo_deck(1)),diagnostic=True)
            sim.manual_priority=True;sim.phase='main';sim.stack.priority=0
            player=sim.players[0]
            (player.hand if card in player.hand else player.library).remove(card)
            for land in lands:
                (player.hand if land in player.hand else player.library).remove(land)
                player.battlefield.append(s.Permanent(land))
            pending=sim.enter_creature(card,player);sim.resolve_entry_triggers(pending,card)
            goblin=s.EventDefinition('Test Goblin',frozenset({'Creature'}),
                frozenset({'Goblin'}),False,1,1,frozenset())
            victim=s.Card('victim','Test Goblin','creature',power=1,toughness=1,
                          event_definition=goblin,is_token=True)
            pending=sim.enter_creature(victim,player);sim.resolve_entry_triggers(pending,victim)
            previous=sim.players[1].life
            sim.activate_sacrifice_tokens(0,card.id,victim.id)
            self.assertFalse(any(p.card.id==victim.id for p in player.battlefield))
            self.assertEqual(len(sim.stack.items),2)
            while sim.stack.items:sim.pass_priority(sim.stack.priority)
            created=[p for p in player.battlefield if p.card.is_token]
            self.assertEqual(len(created),2)
            self.assertEqual(sim.players[1].life,previous-1)
            self.assertEqual(sum(p.card.event_definition and
                                 'Goblin' in p.card.event_definition.subtypes
                                 for p in created),2)
            sim.invariant()


class CollectiveTribalAttackChecks(unittest.TestCase):
    def test_unseen_group_tribal_attack_program_composes_other_etb_trigger(self):
        raw=dict(name='Unseen Goblin Captain',types=['Creature'],subTypes=['Goblin'],
            power='2',toughness='2',
            oracleText=('Whenever one or more Goblins you control attack, '
                        "create a 1/1 red Goblin creature token that's tapped and attacking.\n"
                        'Whenever another creature you control enters, '
                        'Unseen Goblin Captain deals 1 damage to each opponent.'))
        definition=parse_card(raw)
        self.assertTrue(definition.supported,definition.reason)
        self.assertEqual(len(definition.group_attack_subtype_tokens),1)
        tribe,spec=definition.group_attack_subtype_tokens[0]
        self.assertEqual(tribe,'Goblin')
        self.assertTrue(spec.tapped and spec.attacking)
        self.assertEqual(len(definition.triggers),1)
        self.assertTrue(definition.triggers[0].subject.other)
        self.assertEqual(definition.triggers[0].effect.operation,'damage')
        self.assertEqual(definition.triggers[0].effect.amount,1)
        self.assertFalse(parse_card(dict(raw,oracleText=raw['oracleText']+'\nWin the game.')).supported)

    def test_real_general_kreat_creates_once_for_two_goblins(self):
        import json
        deck=json.loads((Path(__file__).resolve().parents[1]/'decks'/
                         '14509839-mono-red-gobs.json').read_text())
        raw=next(c for c in deck['mainboard'] if c['name']=='General Kreat, the Boltbringer')
        definition=parse_card(raw)
        self.assertTrue(definition.supported,definition.reason)
        with s.RulesBridge() as rules:
            card=s.import_diagnostic_card(rules,raw,0,'general',{'Red'})
            self.assertNotEqual(card.kind,'unsupported')
            sim=s.Simulator(rules,42,decks=(s.demo_deck(0)+[card],
                s.demo_deck(1)),diagnostic=True)
            sim.manual_priority=True;sim.phase='main'
            owner=sim.players[0]
            (owner.hand if card in owner.hand else owner.library).remove(card)
            pending=sim.enter_creature(card,owner)
            sim.resolve_entry_triggers(pending,card)
            for index in range(2):
                identifier='goblin'+str(index)
                goblin=s.EventDefinition('Unknown Goblin',frozenset({'Creature'}),
                    frozenset({'Goblin'}),False,1,1,frozenset())
                unit=s.Card(identifier,'Unknown Goblin','creature',power=1,toughness=1,
                    event_definition=goblin,is_token=True)
                pending=sim.enter_creature(unit,owner)
                sim.resolve_entry_triggers(pending,unit)
            while sim.stack.items:sim.pass_priority(sim.stack.priority)
            for creature in owner.battlefield:creature.fresh=False
            prior=sim.players[1].life
            sim.phase='attack';sim.stack.priority=sim.active
            sim.declare_attackers(['goblin0','goblin1'])
            while sim.stack.items:sim.pass_priority(sim.stack.priority)
            added=[p for p in owner.battlefield if p.card.id.startswith('token-')]
            self.assertEqual(len(added),1)
            self.assertTrue(added[0].tapped)
            self.assertIn(added[0].card.id,sim.group_combat['attackers'])
            self.assertEqual(sim.players[1].life,prior-1)


class TribalTapActivationChecks(unittest.TestCase):
    def test_unseen_tap_token_ability_composes_with_live_lord(self):
        raw=dict(name='Unseen Elf Lord',types=['Creature'],subTypes=['Elf'],
            power='2',toughness='2',manaCost='{2}{G}',
            oracleText=('Other Elves you control get +1/+1.\n'
                        '{G}, {T}: Create a 1/1 green Elf Warrior creature token.'))
        definition=parse_card(raw)
        self.assertTrue(definition.supported,definition.reason)
        self.assertEqual(len(definition.static_effects),1)
        self.assertEqual(len(definition.activations),1)
        cost,spec,tap=definition.activations[0]
        self.assertEqual(cost,'{G}')
        self.assertTrue(tap)
        self.assertEqual(spec.subtypes,('Elf','Warrior'))
        ally=Definition('Unknown Elf',frozenset({'Creature'}),frozenset({'Elf'}),
                        False,1,1,frozenset())
        game=Game()
        lord=Permanent('lord',definition,0)
        friend=Permanent('friend',ally,0)
        enemy=Permanent('enemy',ally,1)
        game.enter(lord);game.enter(friend);game.enter(enemy)
        self.assertEqual(game.stats(lord),(2,2))
        self.assertEqual(game.stats(friend),(2,2))
        self.assertEqual(game.stats(enemy),(1,1))

    def test_real_imperious_perfect_tap_cost_paid_before_token_resolves(self):
        import json
        deck=json.loads((Path(__file__).resolve().parents[1]/'decks'/
                         '14435337-lupitas-elves.json').read_text())
        raw=next(c for c in deck['mainboard'] if c['name']=='Imperious Perfect')
        definition=parse_card(raw)
        self.assertTrue(definition.supported,definition.reason)
        self.assertTrue(definition.activations[0][2])
        with s.RulesBridge() as rules:
            card=s.import_diagnostic_card(rules,raw,0,'perfect',{'Green'})
            self.assertNotEqual(card.kind,'unsupported')
            lands=[s.Card('mana'+str(i),'Mana','land',mask=63) for i in range(3)]
            sim=s.Simulator(rules,42,decks=(s.demo_deck(0)+[card]+lands,
                s.demo_deck(1)),diagnostic=True)
            sim.manual_priority=True;sim.phase='main';sim.stack.priority=0
            owner=sim.players[0]
            (owner.hand if card in owner.hand else owner.library).remove(card)
            for mana in lands:
                (owner.hand if mana in owner.hand else owner.library).remove(mana)
                owner.battlefield.append(s.Permanent(mana))
            pending=sim.enter_creature(card,owner)
            sim.resolve_entry_triggers(pending,card)
            source=next(p for p in owner.battlefield if p.card.id==card.id)
            with self.assertRaises(ValueError):sim.activate_tokens(0,card.id)
            source.fresh=False
            sim.activate_tokens(0,card.id)
            self.assertTrue(source.tapped)
            with self.assertRaises(ValueError):sim.activate_tokens(0,card.id)
            while sim.stack.items:sim.pass_priority(sim.stack.priority)
            tokens=[p for p in owner.battlefield if p.card.is_token]
            self.assertEqual(len(tokens),1)
            self.assertEqual(sim.effective_card(tokens[0]).power,2)
            self.assertFalse(any(p.card.is_token and p.card.id!=tokens[0].card.id
                                 for p in owner.battlefield))

    def test_unrecognized_extra_tap_instruction_rejected(self):
        raw=dict(name='Unknown Lord',types=['Creature'],subTypes=['Elf'],
            power='2',toughness='2',
            oracleText=('{G}, {T}: Create a 1/1 green Elf Warrior creature token. '
                        'Draw three cards.'))
        self.assertFalse(parse_card(raw).supported)


class TribalInterveningIfChecks(unittest.TestCase):
    @staticmethod
    def elite():
        return parse_card(dict(name='Unseen Elven Recruiter',types=['Creature'],
            subTypes=['Elf','Warrior'],power='2',toughness='2',
            oracleText=('When this creature enters, if you control another Elf, '
                        'create a 1/1 green Elf Warrior creature token.')))

    def test_conditional_etb_requires_another_ally_at_trigger_time(self):
        elite=self.elite()
        self.assertTrue(elite.supported,elite.reason)
        self.assertEqual(elite.triggers[0].requires_other_controlled_subtype,'Elf')
        ally=Definition('Unknown Ally',frozenset({'Creature'}),frozenset({'Elf'}),
                        False,1,1,frozenset())
        other=Definition('Unknown Opponent',frozenset({'Creature'}),frozenset({'Elf'}),
                         False,1,1,frozenset())
        game=Game()
        game.enter(Permanent('enemy',other,1))
        game.enter(Permanent('first',elite,0))
        self.assertFalse(any(e['kind']=='trigger' for e in game.events))
        game.enter(Permanent('ally',ally,0))
        game.events.clear()
        game.enter(Permanent('second',elite,0))
        triggers=[e for e in game.events if e['kind']=='trigger']
        self.assertEqual(len(triggers),1)
        self.assertEqual(triggers[0]['requiresOtherControlledSubtype'],'Elf')
        self.assertEqual(triggers[0]['operation'],'create_tokens')
        self.assertEqual(triggers[0]['tokenSpec']['subtypes'],('Elf','Warrior'))

    def test_changeling_satisfies_other_elf_condition(self):
        elite=self.elite()
        changeling=Definition('Unknown Shapeshifter',frozenset({'Creature'}),
            frozenset({'Shapeshifter'}),False,1,1,frozenset({'changeling'}))
        game=Game()
        game.enter(Permanent('changeling',changeling,0))
        game.events.clear()
        game.enter(Permanent('elite',elite,0))
        self.assertEqual(len([e for e in game.events if e['kind']=='trigger']),1)

    def test_real_dwynens_elite_and_fail_closed_extra_text(self):
        import json
        deck=json.loads((Path(__file__).resolve().parents[1]/'decks'/
                         '14435337-lupitas-elves.json').read_text())
        raw=next(c for c in deck['mainboard'] if c['name']=="Dwynen's Elite")
        parsed=parse_card(raw)
        self.assertTrue(parsed.supported,parsed.reason)
        with s.RulesBridge() as rules:
            card=s.import_diagnostic_card(rules,raw,0,'dwynen',{'Green'})
            self.assertNotEqual(card.kind,'unsupported')
        altered=dict(raw,oracleText=raw['oracleText']+' Draw seven cards.')
        self.assertFalse(parse_card(altered).supported)

    def test_condition_is_rechecked_at_token_resolution(self):
        elite=self.elite()
        with s.RulesBridge() as rules:
            raw=dict(name='Unseen Elven Recruiter',types=['Creature'],
                subTypes=['Elf'],power='2',toughness='2',manaCost='{1}{G}',
                oracleText=('When this creature enters, if you control another Elf, '
                            'create a 1/1 green Elf Warrior creature token.'))
            card=s.import_diagnostic_card(rules,raw,0,'elite',{'Green'})
            self.assertNotEqual(card.kind,'unsupported')
            sim=s.Simulator(rules,42,decks=(s.demo_deck(0)+[card],s.demo_deck(1)),diagnostic=True)
            sim.manual_priority=True
            sim.phase='main'
            owner=sim.players[0]
            (owner.hand if card in owner.hand else owner.library).remove(card)
            ally_def=s.EventDefinition('Ally',frozenset({'Creature'}),frozenset({'Elf'}),
                False,1,1,frozenset())
            ally=s.Card('ally','Ally','creature',event_definition=ally_def,
                        power=1,toughness=1,is_token=True)
            sim.enter_creature(ally,owner)
            pending=sim.enter_creature(card,owner)
            sim.resolve_entry_triggers(pending,card)
            self.assertTrue(sim.stack.items)
            ally_perm=next(p for p in owner.battlefield if p.card.id=='ally')
            sim.send_to_destination(owner,ally_perm)
            while sim.stack.items:sim.pass_priority(sim.stack.priority)
            self.assertFalse(any(p.card.is_token for p in owner.battlefield))
            self.assertTrue(any(e['kind']=='entry_condition_failed' for e in sim.events))


class GoblinAttackGrammarChecks(unittest.TestCase):
    def test_unseen_standalone_attack_trigger_compiles(self):
        raw=dict(name='Unseen Goblin Captain',types=['Creature'],subTypes=['Goblin'],
                 power='2',toughness='2',oracleText=(
                     "Whenever this creature attacks, put a +1/+1 counter on it, then create a number of 1/1 red Goblin creature tokens equal to this creature's power."))
        definition=parse_card(raw)
        self.assertTrue(definition.supported,definition.reason)
        self.assertEqual(definition.attack_effects[0][0],'counter_power_tokens')
        self.assertEqual(definition.attack_effects[0][1],1)
        self.assertEqual(definition.attack_effects[0][3].subtypes,('Goblin',))

    def test_real_krenko_attack_uses_generic_grammar(self):
        import json
        deck=json.loads((Path(__file__).resolve().parents[1]/'decks'/
                         '14509839-mono-red-gobs.json').read_text())
        raw=next(c for c in deck['mainboard'] if c['name']=='Krenko, Tin Street Kingpin')
        definition=parse_card(raw)
        self.assertTrue(definition.supported,definition.reason)
        self.assertEqual(definition.attack_effects[0][0],'counter_power_tokens')
        with s.RulesBridge() as rules:
            card=s.import_diagnostic_card(rules,raw,0,'krenko',{'Red'})
        self.assertNotEqual(card.kind,'unsupported')

    def test_standalone_attack_trigger_rejects_unrecognized_instruction(self):
        raw=dict(name='Unseen Goblin Captain',types=['Creature'],subTypes=['Goblin'],
                 power='2',toughness='2',oracleText=(
                     "Whenever this creature attacks, put a +1/+1 counter on it, then create a number of 1/1 red Goblin creature tokens equal to this creature's power. Draw seven cards."))
        self.assertFalse(parse_card(raw).supported)


class TribalSpellCastChecks(unittest.TestCase):
    def test_unseen_tribal_spell_cast_trigger_is_selective(self):
        from oracle_abilities import cast_matches
        from types import SimpleNamespace
        source=parse_card(dict(name='Unknown Elf Mentor',types=['Creature'],subTypes=['Elf'],
            power='2',toughness='2',oracleText=(
                'Whenever you cast an Elf spell, you may create a 1/1 green Elf Warrior creature token.')))
        self.assertTrue(source.supported)
        self.assertEqual(len(source.triggers),1)
        trigger=source.triggers[0]
        self.assertEqual(trigger.subject.subtype,'Elf')
        self.assertTrue(trigger.effect.optional)
        self.assertEqual(trigger.effect.operation,'create_tokens')
        watcher=Permanent('watcher',source,0)
        elf=SimpleNamespace(printed_types=('Creature',),
                            event_definition=SimpleNamespace(subtypes=frozenset({'Elf','Warrior'}),types=frozenset({'Creature'}),abilities=frozenset()))
        goblin=SimpleNamespace(printed_types=('Creature',),
                               event_definition=SimpleNamespace(subtypes=frozenset({'Goblin'}),types=frozenset({'Creature'}),abilities=frozenset()))
        self.assertTrue(cast_matches(trigger,watcher,elf,0))
        self.assertFalse(cast_matches(trigger,watcher,goblin,0))
        self.assertFalse(cast_matches(trigger,watcher,elf,1))
        changeling=SimpleNamespace(printed_types=('Creature',),
            event_definition=SimpleNamespace(subtypes=frozenset({'Shapeshifter'}),
                types=frozenset({'Creature'}),abilities=frozenset({'changeling'})))
        self.assertTrue(cast_matches(trigger,watcher,changeling,0))

    def test_real_lupitas_elves_huntmaster_compiles(self):
        import json
        deck=json.loads((Path(__file__).resolve().parents[1]/'decks'/
                         '14435337-lupitas-elves.json').read_text())
        raw=next(c for c in deck['mainboard'] if c['name']=='Lys Alana Huntmaster')
        parsed=parse_card(raw)
        self.assertTrue(parsed.supported,parsed.reason)
        self.assertEqual(parsed.triggers[0].subject.subtype,'Elf')
        self.assertEqual(parsed.triggers[0].effect.operation,'create_tokens')
        with s.RulesBridge() as rules:
            card=s.import_diagnostic_card(rules,raw,0,'huntmaster',{'Green'})
        self.assertNotEqual(card.kind,'unsupported')


    def test_unknown_tribal_trigger_remainder_rejected(self):
        raw=dict(name='Unknown Elf Mentor',types=['Creature'],subTypes=['Elf'],
                 power='2',toughness='2',oracleText=(
                     'Whenever you cast an Elf spell, you may create a 1/1 green Elf Warrior creature token. Draw four cards.'))
        self.assertFalse(parse_card(raw).supported)


class LinkedRemovalGrammarChecks(unittest.TestCase):
    def test_generic_destroy_and_controller_token_parsing(self):
        for target_order in ('artifact or creature','creature or artifact'):
            with self.subTest(target_order=target_order):
                raw=dict(name='Unseen Intervention',types=['Instant'],
                    manaCost='{1}{W}',oracleText=(
                        f'Destroy target {target_order}. Its controller creates a 2/2 white Ox creature token.'))
                with s.RulesBridge() as rules:
                    card=s.import_diagnostic_card(rules,raw,0,'intervention',{'White'})
                self.assertEqual(card.kind,'removal_spell')
                self.assertEqual(card.removal,'destroy_artifact_creature_token')
                self.assertEqual(card.token_count,1)
                self.assertEqual((card.token_definition.power,card.token_definition.toughness),(2,2))
                self.assertIn('Ox',card.token_definition.subtypes)
                self.assertIn('White',card.token_definition.colors)

    def test_linked_removal_fails_closed_on_unknown_remainder(self):
        raw=dict(name='Unseen Intervention',types=['Instant'],manaCost='{1}{W}',
            oracleText='Destroy target artifact or creature. Its controller creates a 2/2 white Ox creature token. Draw three cards.')
        with s.RulesBridge() as rules:
            card=s.import_diagnostic_card(rules,raw,0,'intervention',{'White'})
        self.assertEqual(card.kind,'unsupported')


class BudgetFaeriesChoiceRegression(unittest.TestCase):
    def test_entry_keyword_choice_is_generic_and_validated(self):
        from card_events import NeedsRules
        raw=dict(name='Unseen Counter Beast',types=['Creature'],
                 colors=['Black'],power='2',toughness='1',
                 oracleText='This creature enters with your choice of a deathtouch counter or a lifelink counter on it.')
        definition=parse_card(raw)
        self.assertTrue(definition.supported)
        self.assertEqual(set(definition.entry_keyword_choices),{'deathtouch','lifelink'})
        game=Game()
        chosen=Permanent('chosen',definition,0,keyword_counters=frozenset({'lifelink'}))
        game.enter(chosen)
        self.assertTrue(game.has(chosen,'lifelink'))
        self.assertFalse(game.has(chosen,'deathtouch'))
        with self.assertRaises(NeedsRules):
            Game().enter(Permanent('missing',definition,0))
        with self.assertRaises(NeedsRules):
            Game().enter(Permanent('invalid',definition,0,keyword_counters=frozenset({'flying'})))

    def test_targeted_keyword_choice_spell_compiles_without_card_name(self):
        from targeted_modifiers import parse
        oracle='Target creature gets +1/+1 and gains your choice of deathtouch or lifelink until end of turn.'
        self.assertEqual(parse(oracle,['Instant']),(1,1,('deathtouch','lifelink'),''))
        self.assertIsNone(parse(oracle+' Draw a card.',['Instant']))
        self.assertIsNone(parse(oracle,['Creature']))


class ColoredWitnessGrammarChecks(unittest.TestCase):
    def test_unseen_colored_witness_is_live_and_excludes_self(self):
        for color in ('white','blue','black','red','green'):
            with self.subTest(color=color):
                text=f'This creature gets +2/+3 as long as you control another {color} creature.'
                program=compile_abilities(text,'Unknown Sentinel')
                self.assertIsNotNone(program)
                self.assertEqual(len(program.static_effects),1)
                effect=program.static_effects[0]
                self.assertEqual((effect.power,effect.toughness),(2,3))
                self.assertTrue(effect.subject.self_only)
                self.assertTrue(effect.condition.other)
                self.assertEqual(effect.condition.relation,'controller')
                self.assertEqual(effect.condition.color,color.capitalize())

    def test_briarberry_style_bonus_reacts_to_board_changes(self):
        creature=parse_card(dict(name='Unseen Cohort',types=['Creature'],
            subTypes=['Faerie'],colors=['Blue'],power='1',toughness='1',
            oracleText='Flying\nThis creature gets +1/+1 as long as you control another blue creature.'))
        self.assertTrue(creature.supported)
        ally=parse_card(dict(name='Unseen Blue Ally',types=['Creature'],
            colors=['Blue'],power='1',toughness='1',oracleText=''))
        enemy=parse_card(dict(name='Unseen Blue Enemy',types=['Creature'],
            colors=['Blue'],power='1',toughness='1',oracleText=''))
        game=Game()
        cohort=Permanent('cohort',creature,0)
        game.enter(cohort)
        self.assertEqual(game.stats(cohort),(1,1))
        game.enter(Permanent('enemy',enemy,1))
        self.assertEqual(game.stats(cohort),(1,1))
        game.enter(Permanent('ally',ally,0))
        self.assertEqual(game.stats(cohort),(2,2))
        del game.battlefield['ally']
        self.assertEqual(game.stats(cohort),(1,1))

    def test_unknown_extra_instruction_rejects_entire_program(self):
        self.assertIsNone(compile_abilities(
            'This creature gets +2/+3 as long as you control another blue creature. Draw seven cards.',
            'Unknown Sentinel'))


class OracleGrammarChecks(unittest.TestCase):
    def test_unfamiliar_upkeep_uses_parsed_amounts_and_only_controller_turn(self):
        raw=dict(name='Unseen nursery',types=['Enchantment'],manaCost='{G}',
                 oracleText='At the beginning of your upkeep, you lose 3 life and create two tapped 2/3 blue Drake creature tokens with flying.')
        with s.RulesBridge() as rules:
            card=s.import_diagnostic_card(rules,raw,0,'nursery',{'Green'})
            self.assertEqual(card.kind,'enchantment')
            sim=s.Simulator(rules,42,decks=(s.demo_deck(0)+[card],s.demo_deck(1)),diagnostic=True)
            owner=sim.players[0]
            (owner.hand if card in owner.hand else owner.library).remove(card)
            sim.enter_creature(card,owner)
            sim.active=1;sim.phase='untap';sim.step()
            self.assertEqual(owner.life,40)
            self.assertFalse(any(p.card.is_token for p in owner.battlefield))
            for expected in (2,4):
                sim.active=0;sim.phase='untap';sim.step()
                tokens=[p for p in owner.battlefield if p.card.is_token]
                self.assertEqual(len(tokens),expected)
                self.assertTrue(all(p.tapped and p.card.traits=='2;3;flying' for p in tokens))
            self.assertEqual(owner.life,34)
            sim.invariant()

    def test_upkeep_grammar_composes_and_rejects_unimplemented_conditions(self):
        program=compile_abilities('At the beginning of your upkeep, create a 4/4 colorless Golem creature token.')
        self.assertEqual(program.triggers[0].effect.token.power,4)
        self.assertEqual(program.triggers[0].effect.controller_loss,0)
        self.assertIsNotNone(compile_abilities('At the beginning of your upkeep, scry 2.'))
        for text in [
            'At the beginning of each upkeep, create a 1/1 green Squirrel creature token.',
            'At the beginning of your upkeep, if you control a Faerie, create a 1/1 green Squirrel creature token.',
            'At the beginning of your upkeep, you may pay 1 life. If you do, create a 1/1 green Squirrel creature token.',
            'At the beginning of your upkeep, create a 1/1 green Squirrel creature token. Draw a card.']:
            self.assertIsNone(compile_abilities(text))

    def test_unfamiliar_entry_token_trigger_waits_for_resolution_and_uses_controller(self):
        raw=dict(name='Unseen summoner',types=['Creature'],power='2',toughness='2',manaCost='{G}',
                 oracleText='When this creature enters, create two tapped 3/4 blue Drake creature tokens with flying.')
        with s.RulesBridge() as rules:
            card=s.import_diagnostic_card(rules,raw,1,'summoner',{'Green'})
            sim=s.Simulator(rules,42,decks=(s.demo_deck(0),s.demo_deck(1)+[card]),diagnostic=True)
            owner=sim.players[1]
            (owner.hand if card in owner.hand else owner.library).remove(card)
            triggers=sim.enter_creature(card,owner)
            self.assertFalse(any(p.card.is_token for p in owner.battlefield))
            sim.resolve_entry_triggers(triggers,card)
            tokens=[p for p in owner.battlefield if p.card.is_token]
            self.assertEqual(len(tokens),2)
            self.assertTrue(all(p.tapped and p.card.traits=='3;4;flying' for p in tokens))
            self.assertFalse(sim.players[0].battlefield)
            sim.invariant()
        self.assertFalse(self.definition('Whenever a creature you control enters, create a 1/1 green Squirrel creature token.').supported)
        self.assertTrue(self.definition('When this creature dies, create a 1/1 green Squirrel creature token.').supported)

    def test_token_instruction_extracts_all_characteristics(self):
        spec=parse_token_creation('Create three tapped 2/3 blue and black Faerie Rogue creature tokens with flying and lifelink.')
        self.assertEqual((spec.amount,spec.power,spec.toughness,spec.tapped),(3,2,3,True))
        self.assertEqual(spec.colors,('Blue','Black'))
        self.assertEqual(spec.subtypes,('Faerie','Rogue'))
        self.assertEqual(spec.keywords,frozenset({'flying','lifelink'}))
        self.assertEqual(parse_token_creation('Create a 4/4 colorless Golem creature token.').colors,())
        for text in ['Create X 1/1 red Goblin creature tokens.',
                     'Create two 1/1 red Goblin creature tokens. Draw a card.',
                     'Create two 1/1 red Goblin creature tokens with ward {2}.',
                     'Create a 0/0 green Ooze creature token.']:
            self.assertIsNone(parse_token_creation(text))

    def test_unfamiliar_token_spell_executes_parsed_characteristics(self):
        raw=dict(name='Unseen token spell',types=['Sorcery'],manaCost='{G}',
                 oracleText='Create two tapped 2/3 blue and black Faerie Rogue creature tokens with flying.')
        with s.RulesBridge() as rules:
            card=s.import_diagnostic_card(rules,raw,0,'spell',{'Green'})
            land=s.Card('mana-land','Forest','land',mask=16)
            self.assertEqual(card.kind,'token_spell')
            sim=s.Simulator(rules,42,decks=(s.demo_deck(0)+[card,land],s.demo_deck(1)),diagnostic=True)
            player=sim.players[0]
            for item in [card,land]:
                (player.hand if item in player.hand else player.library).remove(item)
            player.hand.append(card);player.battlefield.append(s.Permanent(land))
            sim.phase='main'
            from unittest.mock import patch
            with patch.object(sim,'decide',return_value=s.Candidate('cast','cast',card_id=card.id)):
                sim.step()
            tokens=[p for p in player.battlefield if p.card.is_token]
            self.assertEqual(len(tokens),2)
            self.assertTrue(all(p.tapped and p.fresh for p in tokens))
            self.assertTrue(all(sim.effective_card(p).traits=='2;3;flying' for p in tokens))
            self.assertTrue(all(p.card.event_definition.colors==frozenset({'Blue','Black'}) for p in tokens))
            sim.invariant()

    def test_keyword_grant_uses_color_controller_and_source_presence(self):
        d=self.definition('Red creatures you control have first strike.','Unfamiliar teacher')
        self.assertTrue(d.supported)
        g=Game();g.enter(Permanent('teacher',d,0))
        for identifier,color,controller in [('ally','Red',0),('enemy','Red',1),('blue','Blue',0)]:
            g.enter(Permanent(identifier,replace(self.definition(''),colors=frozenset({color})),controller))
        self.assertTrue(g.has(g.battlefield['ally'],'first strike'))
        self.assertFalse(g.has(g.battlefield['enemy'],'first strike'))
        self.assertFalse(g.has(g.battlefield['blue'],'first strike'))
        g.leave('teacher');self.assertFalse(g.has(g.battlefield['ally'],'first strike'))
        self.assertFalse(self.definition('Red creatures you control have first strike and ward {2}.').supported)

    def test_other_keyword_grant_excludes_source(self):
        d=self.definition('Other creatures you control have flying.')
        g=Game();g.enter(Permanent('s',d,0));g.enter(Permanent('a',self.definition(''),0))
        self.assertFalse(g.has(g.battlefield['s'],'flying'))
        self.assertTrue(g.has(g.battlefield['a'],'flying'))

    def test_generic_counter_effect_resolves_for_current_controlled_creatures(self):
        import json
        root=Path(__file__).resolve().parents[1]
        lookup={c['name']:c for p in (root/'decks').glob('*.json') for c in json.loads(p.read_text())['mainboard']}
        with s.RulesBridge() as rules:
            raw=dict(lookup["Cathars' Crusade"],name='Unfamiliar crusade',
                     oracleText='Whenever a creature you control enters, put 2 +1/+1 counters on each creature you control.')
            source=s.import_diagnostic_card(rules,raw,0,'source',{'White'})
            creature=s.Card('subject','Subject','creature',mana_cost='{W}',traits='1;1;',power=1,toughness=1)
            sim=s.Simulator(rules,42,decks=(s.demo_deck(0)+[source,creature],s.demo_deck(1)),diagnostic=True)
            p=sim.players[0]
            for card in [source,creature]:
                (p.hand if card in p.hand else p.library).remove(card)
                triggers=sim.enter_creature(card,p)
                sim.resolve_entry_triggers(triggers,card)
            target=next(x for x in p.battlefield if x.card.id=='subject')
            self.assertEqual(target.counters,2)
            self.assertEqual(sim.effective_card(target).power,3)
            self.assertEqual(next(x for x in p.battlefield if x.card.id=='source').counters,0)
            sim.invariant()
            mentor=s.import_diagnostic_card(rules,lookup['Bloodmark Mentor'],0,'mentor',{'Red'})
            self.assertEqual(mentor.kind,'creature')
            self.assertTrue(mentor.event_definition.static_effects[0].grant=='first strike')

    def test_real_anthem_and_hybrid_liege_cast(self):
        import json
        root=Path(__file__).resolve().parents[1]
        lookup={c['name']:c for p in (root/'decks').glob('*.json') for c in json.loads(p.read_text())['mainboard']}
        with s.RulesBridge() as rules:
            anthem=s.import_diagnostic_card(rules,lookup['Glorious Anthem'],0,'anthem',{'White'})
            self.assertEqual(anthem.kind,'enchantment')
            self.assertTrue(parse_card(lookup['Glen Elendra Liege']).supported)
            liege=s.import_diagnostic_card(rules,lookup['Glen Elendra Liege'],0,'liege',{'Blue','Black'})
            self.assertEqual(liege.kind,'creature')
            lands=[s.Card('hybrid-land-'+str(i),'Test land','land',mask=mask) for i,mask in enumerate([2,4,2,32])]
            sim=s.Simulator(rules,42,decks=(s.demo_deck(0)+[liege]+lands,s.demo_deck(1)),diagnostic=True)
            player=sim.players[0]
            for card in [liege]+lands:
                (player.hand if card in player.hand else player.library).remove(card)
            player.hand.append(liege)
            player.battlefield.extend(s.Permanent(card) for card in lands)
            self.assertTrue(sim.payment(liege)['paid'])
            sim.phase='main'
            from unittest.mock import patch
            with patch.object(sim,'decide',return_value=s.Candidate('cast','cast',card_id=liege.id)):
                sim.step()
            self.assertTrue(all(p.tapped for p in player.battlefield if p.card.kind=='land'))
            self.assertTrue(any(p.card.id==liege.id for p in player.battlefield))
            self.assertFalse(sim.payment(liege)['paid'])
            sim.invariant()

    def test_color_anthems_stack_for_multicolored_creatures_and_cease(self):
        lord=self.definition('Flying\nOther blue creatures you control get +1/+1.\nOther black creatures you control get +1/+1.')
        g=Game();g.enter(Permanent('lord',lord,0))
        for identifier,colors,controller in [('both',{'Blue','Black'},0),('blue',{'Blue'},0),('red',{'Red'},0),('enemy',{'Blue','Black'},1)]:
            g.enter(Permanent(identifier,replace(self.definition(''),colors=frozenset(colors)),controller))
        self.assertEqual(g.stats(g.battlefield['both']),(4,4))
        self.assertEqual(g.stats(g.battlefield['blue']),(3,3))
        self.assertEqual(g.stats(g.battlefield['red']),(2,2))
        self.assertEqual(g.stats(g.battlefield['enemy']),(2,2))
        self.assertEqual(g.stats(g.battlefield['lord']),(2,2))
        g.leave('lord');self.assertEqual(g.stats(g.battlefield['both']),(2,2))

    def test_global_creature_bonus_includes_source_when_it_is_a_creature(self):
        g=Game();g.enter(Permanent('source',self.definition('Creatures you control get +2/+3.'),0))
        self.assertEqual(g.stats(g.battlefield['source']),(4,5))
        self.assertFalse(self.definition('Creatures you control get +2/+3.\nThey have ward {2}.').supported)

    def test_irregular_type_plurals_and_unknown_inflections(self):
        for plural,singular in [('Allies','Ally'),('Faeries','Faerie'),('Zombies','Zombie'),('Elves','Elf'),('Mice','Mouse')]:
            d=self.definition(f'Other {plural} you control get +1/+1.')
            self.assertTrue(d.supported)
            self.assertEqual(d.static_effects[0].subject.subtype,singular)
        self.assertFalse(self.definition('Other Mysteries you control get +1/+1.').supported)

    def definition(self,text,name='Unseen card'):
        return parse_card(dict(name=name,types=['Creature'],subTypes=['Wizard'],power='2',toughness='2',oracleText=text))

    def test_name_does_not_select_behavior(self):
        text='Whenever another Goblin you control enters, each opponent loses 3 life.'
        a=self.definition(text,'Brand new card'); b=self.definition(text,'Obyra, Dreaming Duelist')
        self.assertTrue(a.supported); self.assertEqual(a.triggers,b.triggers)
        self.assertEqual(a.triggers[0].effect.amount,3)
        self.assertEqual(a.triggers[0].subject.subtype,'Goblin')

    def test_subtype_controller_and_other_are_independent_filters(self):
        d=self.definition('Whenever another Goblin creature you control enters, each opponent loses 3 life.')
        g=Game();g.enter(Permanent('source',d,0))
        for i,(types,subtype,controller) in enumerate([
                ({'Creature'},{'Faerie'},0),({'Creature'},{'Goblin'},1),
                ({'Enchantment'},{'Goblin'},0),({'Creature'},{'Goblin'},0)]):
            token=Definition('Subject',frozenset(types),frozenset(subtype),False,1,1,frozenset())
            g.enter(Permanent(str(i),token,controller))
        triggers=[e for e in g.events if e['kind']=='trigger']
        self.assertEqual([e['entered'] for e in triggers],['3'])
        self.assertEqual(triggers[0]['amount'],3)

    def test_subtype_without_creature_restriction_counts_kindred(self):
        g=Game();g.enter(Permanent('s',self.definition('Whenever another Goblin you control enters, each opponent loses 2 life.'),0))
        g.enter(Permanent('k',Definition('Kindred',frozenset({'Enchantment'}),frozenset({'Goblin'}),False,0,0,frozenset()),0))
        self.assertEqual(len([e for e in g.events if e['kind']=='trigger']),1)

    def test_death_trigger_effect_amounts_and_self_reference(self):
        text='Whenever Unknown Sage or another creature you control dies, each opponent loses 2 life and you gain 3 life.'
        d=self.definition(text,'Unknown Sage'); self.assertTrue(d.supported)
        g=Game();g.enter(Permanent('s',d,0))
        e=g.death_triggers(['s'])[0]
        self.assertEqual((e['amount'],e['gain'],e['recipient']),(2,3,'each opponent'))

    def test_compound_keywords_and_multiple_abilities(self):
        d=self.definition('Flying, lifelink\nWhen this creature enters, scry 4.\nWhenever another Faerie you control enters, each opponent loses 2 life.')
        self.assertTrue(d.supported); self.assertEqual(len(d.triggers),2)
        self.assertEqual(d.abilities,frozenset({'flying','lifelink'}))

    def test_continuous_effects_generalize_types_amounts_and_names(self):
        lord=self.definition('Other Wizards you control get +2/+3.','Unseen lord')
        counted=self.definition('This creature gets +3/+1 for each other Wizard on the battlefield.','Unseen counter')
        self.assertTrue(lord.supported and counted.supported)
        g=Game();g.enter(Permanent('lord',lord,0));g.enter(Permanent('counted',counted,0))
        self.assertEqual(g.stats(g.battlefield['lord']),(2,2))
        self.assertEqual(g.stats(g.battlefield['counted']),(7,6))
        enemy=self.definition('','Enemy wizard');g.enter(Permanent('enemy',enemy,1))
        self.assertEqual(g.stats(g.battlefield['counted']),(10,7))
        self.assertEqual(g.stats(g.battlefield['enemy']),(2,2))
        g.leave('lord')
        self.assertEqual(g.stats(g.battlefield['counted']),(5,3))

    def test_color_condition_is_read_from_text(self):
        d=self.definition('This creature gets +2/+4 as long as you control another red creature.')
        g=Game();g.enter(Permanent('source',d,0))
        ally=replace(self.definition(''),colors=frozenset({'Red'}))
        g.enter(Permanent('ally',ally,0));self.assertEqual(g.stats(g.battlefield['source']),(4,6))
        g.leave('ally');self.assertEqual(g.stats(g.battlefield['source']),(2,2))

    def test_unknown_remainder_is_never_dropped(self):
        valid='Whenever another Goblin you control enters, each opponent loses 3 life.'
        for text in (valid+'\nDraw a card.',valid+' Draw a card.',
                     'Whenever another Goblin you control enters, if you control a Forest, each opponent loses 3 life.',
                     'Whenever one or more Goblins you control enter, each opponent loses 3 life.',
                     'Whenever another Goblin you control enters, you may have each opponent lose 3 life.'):
            self.assertFalse(self.definition(text).supported,text)

    def test_arbitrary_card_enters_real_diagnostic_import_and_resolution(self):
        raw=dict(name='Unknown test card',types=['Creature'],subTypes=['Goblin'],power='2',toughness='2',
                 manaCost='{1}{R}',oracleText='When this creature enters, each opponent loses 3 life and you gain 2 life.')
        with s.RulesBridge() as rules:
            card=s.import_diagnostic_card(rules,raw,0,'unknown',{'Red'})
            self.assertEqual(card.kind,'creature')
            sim=s.Simulator(rules,42,decks=(s.demo_deck(0)+[card],s.demo_deck(1)),diagnostic=True)
            p=sim.players[0]; (p.hand if card in p.hand else p.library).remove(card)
            sim.resolve_entry_triggers(sim.enter_creature(card,p),card)
            self.assertEqual([x.life for x in sim.players],[42,37]); sim.invariant()

if __name__=='__main__': unittest.main()
