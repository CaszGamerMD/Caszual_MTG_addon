"""Whole-card Liliana emblems: printed Oracle, costs, stack and delayed triggers."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
from planeswalker_loyalty import compile_card
from planeswalker_runtime import activate
from planeswalker_emblems import compile_emblem

LILIANA=(
    '+1: Up to one target creature gets -2/-1 until your next turn.\n'
    '−2: Mill two cards, then you may return a creature card from your graveyard to your hand.\n'
    '−7: You get an emblem with "At the beginning of your end step, create X '
    '2/2 black Zombie creature tokens, where X is two plus the number of Zombies you control."'
)

class EmblemIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rules=s.RulesBridge()
    @classmethod
    def tearDownClass(cls):
        cls.rules.close()

    @staticmethod
    def raw(name='Unseen Shadewalker',text=LILIANA):
        return dict(name=name,layout='normal',types=['Planeswalker'],
                    superTypes=['Legendary'],subTypes=['Shadewalker'],colors=['Black'],
                    manaCost='{1}{B}{B}',oracleText=text,loyalty='3')

    def fixture(self):
        raw=self.raw()
        card=s.import_diagnostic_card(self.rules,raw,0,'emblem-pw',{'Black'})
        self.assertEqual(card.kind,'planeswalker')
        mana=[s.Card('emblem-mana-'+str(i),'Mana','land',mask=63) for i in range(6)]
        sim=s.Simulator(self.rules,44,decks=(s.demo_deck(0)+[card]+mana,
                                             s.demo_deck(1)),diagnostic=True)
        self.assertFalse(sim.finished,sim.questions)
        sim.manual_priority=True
        sim.phase='main'
        p=sim.players[0]
        for c in [card]+mana:
            (p.hand if c in p.hand else p.library).remove(c)
        p.hand.append(card)
        p.battlefield.extend(s.Permanent(c) for c in mana)
        sim.cast_spell(0,card)
        self.drain(sim)
        original=next(x for x in p.battlefield if x.card.id==card.id)
        return sim,card,original

    @staticmethod
    def drain(sim):
        while sim.stack.items:
            sim.pass_priority(sim.stack.priority)

    @staticmethod
    def zombies(sim,seat=0):
        return [x for x in sim.players[seat].battlefield
                if x.card.is_token and x.card.event_definition
                and 'Zombie' in x.card.event_definition.subtypes]

    def ultimate(self,sim,card,source):
        source.loyalty=8  # Prior +1 activations; no costs are bypassed.
        ability=activate(sim,0,card.id,2)
        self.assertEqual(source.loyalty,1)
        self.assertEqual(len(sim.emblems[0]),0)
        self.drain(sim)
        self.assertEqual(len(sim.emblems[0]),1)
        self.assertEqual(len(self.zombies(sim)),0)

    def start_end_step(self,sim,seat=0):
        sim.active=seat
        sim.stack.active=seat
        sim.stack.priority=seat
        sim.phase='end_step'
        sim._end_step_triggers_queued=False
        sim._step()

    def test_full_printed_liliana_compiles_without_card_name_special_case(self):
        p=compile_card(self.raw())
        self.assertIsNotNone(p)
        self.assertEqual(p.starting_loyalty,3)
        self.assertEqual([x.effect_kind for x in p.abilities],
                         ['timed_modifier','mill_optional_creature_return','emblem'])
        self.assertEqual(p.abilities[2].delta,-7)
        self.assertEqual(p.abilities[2].program.base,2)
        self.assertEqual(p.abilities[2].program.counted_subtype,'Zombies')
        self.assertEqual(p.abilities[2].program.token.subtypes,('Zombie',))
        self.assertIsNotNone(compile_card(self.raw('Other Unknown Planeswalker')))
        for invalid in (
            LILIANA+' Additional ability.',
            LILIANA.replace('your end step','each end step'),
            LILIANA.replace('Zombies you control','Zombies any player controls'),
            LILIANA.replace('2/2 black Zombie creature','2/2 black Zombie artifact creature')
        ):
            with self.subTest(invalid=invalid[-100:]):
                self.assertIsNone(compile_card(self.raw(text=invalid)))
        self.assertIsNone(compile_emblem('You get an emblem with "Draw a card."'))

    def test_emblem_stays_after_source_dies_and_creates_zombies_on_end_step(self):
        sim,card,source=self.fixture()
        self.ultimate(sim,card,source)
        sim.players[0].battlefield.remove(source)
        sim.players[0].graveyard.append(card)
        self.start_end_step(sim)
        self.assertEqual(len(self.zombies(sim)),0,'Trigger must use stack')
        self.assertEqual(len(sim.stack.items),1)
        self.assertEqual(sim.stack.items[0].payload[0]['operation'],'emblem_end_step')
        self.drain(sim)
        self.assertEqual(len(self.zombies(sim)),2)
        self.assertTrue(all((z.card.power,z.card.toughness)==(2,2) for z in self.zombies(sim)))
        self.assertEqual(len(sim.emblems[0]),1)
        sim.invariant()

    def test_emblem_count_is_checked_when_trigger_resolves_not_when_triggered(self):
        sim,card,source=self.fixture()
        self.ultimate(sim,card,source)
        self.start_end_step(sim)
        self.assertEqual(len(sim.stack.items),1)
        # Another effect creates a Zombie while the triggered ability waits.
        sim._resolve_entry_effects([dict(operation='create_tokens',
            controller=0,source=card.id,name='Another source',
            tokenSpec=dict(amount=1,power=2,toughness=2,
                           colors=['Black'],subtypes=['Zombie'],
                           keywords=[],tapped=False,land=False,enchantment=False))],card)
        self.assertEqual(len(self.zombies(sim)),1)
        self.drain(sim)
        self.assertEqual(len(self.zombies(sim)),4) # 1 existing + (2+1)
        self.assertTrue(any(e['kind']=='emblem_trigger_count' and
                            e['details']['amount']==3 for e in sim.events))
        sim.invariant()

    def test_new_end_step_recalculates_count_and_does_not_duplicate_same_step(self):
        sim,card,source=self.fixture()
        self.ultimate(sim,card,source)
        self.start_end_step(sim)
        self.drain(sim)
        self.assertEqual(len(self.zombies(sim)),2)
        sim._step() # same end step: exit to cleanup, no second trigger
        self.assertEqual(sim.phase,'cleanup')
        self.assertEqual(len(sim.stack.items),0)
        self.start_end_step(sim)
        self.drain(sim)
        self.assertEqual(len(self.zombies(sim)),6) # original 2 + 2 + 2
        sim.invariant()

    def test_countered_emblem_trigger_does_not_delete_emblem(self):
        sim,card,source=self.fixture()
        self.ultimate(sim,card,source)
        self.start_end_step(sim)
        frame=sim.stack.items[-1]
        self.assertIsNotNone(sim.counter_stack_item(frame))
        self.assertEqual(len(self.zombies(sim)),0)
        self.assertEqual(len(sim.emblems[0]),1)
        self.start_end_step(sim)
        self.drain(sim)
        self.assertEqual(len(self.zombies(sim)),2)
        sim.invariant()

    def test_two_emblems_each_create_their_own_trigger(self):
        sim,card,source=self.fixture()
        self.ultimate(sim,card,source)
        from planeswalker_emblems import create
        create(sim,0,card.loyalty_program.abilities[2].program,card)
        self.start_end_step(sim)
        self.assertEqual(len(sim.stack.items),2)
        self.drain(sim)
        self.assertEqual(len(self.zombies(sim)),6) # first 2; second sees 2 -> 4
        sim.invariant()

if __name__=='__main__':
    unittest.main()
