"""Resolve verified battlefield-counted effects via existing atomic handlers."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

from counted_effect_blocks import BattlefieldCount, parse
import simulator as s


class CountedEffectChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.rules=s.RulesBridge()

    @classmethod
    def tearDownClass(cls):cls.rules.close()

    def card(self,text,name='Unfamiliar counting spell',cost='{W}',types=('Sorcery',)):
        raw=dict(name=name,layout='normal',types=list(types),superTypes=[],subTypes=[],
                 manaCost=cost,oracleText=text,colors=['W'])
        return s.import_diagnostic_card(self.rules,raw,0,'count-spell',
                                        {'White','Black','Blue','Red','Green'})

    @staticmethod
    def creature(uid,subtype,seat):
        color='White' if seat==0 else 'Red'
        return s.Card(uid,subtype+' creature','creature',traits='2;3;',power=2,toughness=3,
            colors=(color,),event_definition=s.EventDefinition(
                subtype+' creature',frozenset({'Creature'}),frozenset({subtype}),
                False,2,3,frozenset(),colors=frozenset({color})))

    def fixture(self,spell):
        mana=[s.Card('count-land-'+str(i),'Counting mana','land',mask=63)
              for i in range(5)]
        allies=[self.creature('count-ally-'+str(i),'Elf',0) for i in range(3)]
        human=self.creature('count-human','Human',0)
        enemy=[self.creature('count-enemy-'+str(i),'Elf',1) for i in range(2)]
        sim=s.Simulator(self.rules,42,
            decks=(s.demo_deck(0)+[spell]+mana+allies+[human],
                   s.demo_deck(1)+enemy),diagnostic=True)
        self.assertFalse(sim.finished)
        sim.manual_priority=True;sim.phase='main'
        p=sim.players[0];other=sim.players[1]
        for c in [spell]+mana+allies+[human]:
            (p.hand if c in p.hand else p.library).remove(c)
        for c in enemy:
            (other.hand if c in other.hand else other.library).remove(c)
        p.hand.extend([spell,allies[2]])
        p.battlefield.extend(s.Permanent(c) for c in mana+allies[:2]+[human])
        other.battlefield.extend(s.Permanent(c) for c in enemy)
        return sim,allies,human,enemy

    @staticmethod
    def drain(sim):
        while sim.stack.items:sim.pass_priority(sim.stack.priority)

    def test_unfamiliar_names_and_changed_numbers_share_compiled_count_blocks(self):
        oracle='You gain 2 life for each Elf you control. Draw two cards.'
        a=self.card(oracle,name='Unknown canopy rite')
        b=self.card(oracle,name='Other unknown rite',types=('Instant',))
        self.assertEqual(a.kind,'counted_spell')
        self.assertEqual(a.counted_program,b.counted_program)
        self.assertEqual([step.base.operation for step in a.counted_program.steps],
                         ['gain_life','draw_cards'])
        self.assertEqual(self.card(oracle.replace('2 life','3 life')).counted_program
                         .steps[0].base.amount,3)
        self.assertEqual(self.card(oracle,types=('Creature',)).kind,'unsupported')

    def test_count_is_bound_at_resolution_after_new_creature_enters(self):
        spell=self.card('Draw a card for each creature you control.')
        sim,allies,_,_=self.fixture(spell)
        p=sim.players[0];initial=len(p.library)
        sim.cast_spell(0,spell)
        self.assertEqual(len(p.library),initial)
        p.hand.remove(allies[2]);p.battlefield.append(s.Permanent(allies[2]))
        self.drain(sim)
        self.assertEqual(len(p.library),initial-4)
        bindings=[e for e in sim.events if e['kind']=='counted_binding']
        self.assertEqual(bindings[-1]['details']['quantity'],4)
        self.assertEqual(bindings[-1]['details']['amount'],4)
        self.assertEqual(p.graveyard.count(spell),1)
        sim.invariant()

    def test_life_multiplier_uses_live_subtype_and_lost_creature(self):
        spell=self.card('You gain 2 life for each Elf you control.')
        sim,allies,_,_=self.fixture(spell)
        sim.cast_spell(0,spell)
        victim=next(x for x in sim.players[0].battlefield if x.card==allies[1])
        sim.players[0].battlefield.remove(victim)
        sim.players[0].graveyard.append(victim.card)
        self.drain(sim)
        self.assertEqual(sim.players[0].life,42)
        sim.invariant()

    def test_each_step_recounts_after_earlier_token_creation(self):
        spell=self.card('Create a 1/1 green Saproling creature token for each creature '
                        'you control. Draw a card for each creature you control.')
        sim,_,_,_=self.fixture(spell)
        before=len(sim.players[0].library)
        sim.cast_spell(0,spell)
        self.drain(sim)
        tokens=[p for p in sim.players[0].battlefield if p.card.is_token]
        self.assertEqual(len(tokens),3)
        self.assertTrue(all(p.card.event_definition.subtypes==frozenset({'Saproling'})
                            and p.card.event_definition.colors==frozenset({'Green'})
                            for p in tokens))
        self.assertEqual(len(sim.players[0].library),before-6)
        bindings=[e['details']['quantity'] for e in sim.events
                  if e['kind']=='counted_binding']
        self.assertEqual(bindings,[3,6])
        sim.invariant()

    def test_zero_count_skips_atom_but_runs_next_fixed_instruction(self):
        spell=self.card('Draw a card for each creature you control. You gain 3 life.')
        sim,_,_,_=self.fixture(spell)
        p=sim.players[0]
        for target in list(p.battlefield):
            if target.card.kind=='creature':
                p.battlefield.remove(target);p.graveyard.append(target.card)
        before=len(p.library)
        sim.cast_spell(0,spell)
        self.drain(sim)
        self.assertEqual(len(p.library),before)
        self.assertEqual(p.life,43)
        self.assertEqual([e['details']['amount'] for e in sim.events
                          if e['kind']=='counted_binding'],[0,3])
        sim.invariant()

    def test_tapped_opponent_filter_and_noncreature_permanents(self):
        spell=self.card('Draw a card for each tapped creature your opponents control.')
        sim,_,_,enemies=self.fixture(spell)
        target=next(p for p in sim.players[1].battlefield if p.card==enemies[0])
        target.tapped=True
        before=len(sim.players[0].library)
        sim.cast_spell(0,spell)
        self.drain(sim)
        self.assertEqual(len(sim.players[0].library),before-1)
        sim.invariant()
        count=BattlefieldCount('any',card_type='Land')
        self.assertEqual(count.evaluate(sim.event_game('main'),0),5)

    def test_complete_text_and_unimplemented_scopes_reject(self):
        oracle='Draw a card for each creature you control.'
        for bad in (oracle+' Exile target land.',
                    'Draw a card for each life you control.',
                    'Draw a card for each creature an opponent controls.',
                    'Draw a card for each creature you control unless you pay {2}.',
                    'Whenever a creature enters, draw a card for each creature you control.',
                    'Scry 1 for each creature you control.'):
            with self.subTest(bad=bad):
                self.assertIsNone(parse(bad,('Instant',)))
                self.assertEqual(self.card(bad).kind,'unsupported')

    def test_excessive_bound_amount_pauses_diagnostic_without_partial_draw(self):
        spell=self.card('Draw 1000 cards for each creature you control.')
        self.assertEqual(spell.kind,'counted_spell')
        sim,_,_,_=self.fixture(spell)
        original=len(sim.players[0].library)
        sim.cast_spell(0,spell)
        self.drain(sim)
        self.assertTrue(sim.finished)
        self.assertTrue(any(q['reason'].startswith('Bound battlefield quantity')
                            for q in sim.questions))
        self.assertEqual(len(sim.players[0].library),original)


if __name__=='__main__':unittest.main()
