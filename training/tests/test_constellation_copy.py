"""New-name constellation + real Calix: targeted ETB and once-per-turn stack copy."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
import test_enchantment_abilities as fixture


class ConstellationCopyChecks(unittest.TestCase):
    setUpClass=classmethod(fixture.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(fixture.EnchantmentChecks.tearDownClass.__func__)
    token=fixture.EnchantmentChecks.token
    drain=fixture.EnchantmentChecks.drain

    def prepare(self):
        raw=self.lookup['Calix, Guided by Fate']
        calix=s.import_diagnostic_card(self.rules,raw,0,'calix',{'White','Green'})
        self.assertEqual(calix.kind,'creature')
        self.assertTrue(calix.event_definition.constellation_counter)
        self.assertTrue(calix.event_definition.enchantment_combat_copy)
        sim=s.Simulator(self.rules,42,decks=(s.demo_deck(0)+[calix],s.demo_deck(1)),diagnostic=True)
        sim.manual_priority=True
        p=sim.players[0]
        (p.hand if calix in p.hand else p.library).remove(calix)
        sim.phase='main';sim.active=0;sim.stack.priority=0
        return sim,calix

    def test_new_name_full_program_and_unknown_remainder_fail_closed(self):
        raw=dict(self.lookup['Calix, Guided by Fate'],name='Unseen Enchantment Walker',
                 oracleText=self.lookup['Calix, Guided by Fate']['oracleText'].replace(
                     'Calix','Unseen Enchantment Walker'))
        card=s.import_diagnostic_card(self.rules,raw,0,'fresh',{'White','Green'})
        self.assertEqual(card.kind,'creature')
        raw['oracleText']+='\nAt end step, do an unknown thing.'
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'bad',{'White','Green'}).kind,
                         'unsupported')

    def test_constellation_queues_one_counter_trigger_per_enchantment_entry(self):
        sim,calix=self.prepare()
        p=sim.players[0]
        pending=sim.enter_creature(calix,p)
        self.assertEqual(len([e for e in pending if e['operation']=='constellation_counter']),1)
        self.assertEqual(pending[0]['target'],calix.id)
        self.assertEqual(next(item for item in p.battlefield if item.card.id==calix.id).counters,0)
        sim.resolve_entry_triggers(pending,calix)
        self.drain(sim)
        self.assertEqual(next(item for item in p.battlefield if item.card.id==calix.id).counters,1)
        bare=s.EventDefinition('Simple enchantment',frozenset({'Enchantment'}),
            frozenset(),False,0,0,frozenset())
        another=s.Card('enchant','Simple enchantment','enchantment',
                       event_definition=bare,printed_types=('Enchantment',),is_token=True)
        pending=sim.enter_creature(another,p)
        self.assertEqual(len([e for e in pending if e['operation']=='constellation_counter']),1)
        sim.resolve_entry_triggers(pending,another);self.drain(sim)
        self.assertEqual(next(item for item in p.battlefield if item.card.id==calix.id).counters,2)
        sim.invariant()

    def test_combat_copy_creates_distinct_nonlegendary_enchantment_token_once(self):
        sim,calix=self.prepare()
        p=sim.players[0]
        sim.enter_creature(calix,p)
        creature=next(item for item in p.battlefield if item.card.id==calix.id)
        creature.fresh=False
        bare=s.EventDefinition('Plain enchantment',frozenset({'Enchantment'}),
            frozenset(),False,0,0,frozenset())
        enchant=s.Card('enchant','Plain enchantment','enchantment',
                       event_definition=bare,printed_types=('Enchantment',),is_token=True)
        sim.enter_creature(enchant,p)
        original_count=sum(item.card.name=='Plain enchantment' for item in p.battlefield)
        sim.phase='attack';sim.declare_attackers([calix.id]);self.drain(sim)
        sim.declare_blockers({})
        sim.group_damage_step()
        self.assertTrue(any(f.payload[0].get('operation')=='enchantment_combat_copy'
                            for f in sim.stack.items))
        self.drain(sim)
        copied=[item for item in p.battlefield if item.card.name=='Plain enchantment']
        self.assertEqual(len(copied),original_count+1)
        self.assertEqual(len({item.card.id for item in copied}),len(copied))
        self.assertTrue(any(item.card.is_token for item in copied))
        # Another trigger from the same permanent this turn cannot create a second copy.
        played=next(e for e in sim.events if e['kind']=='enchantment_copied')
        event=dict(operation='enchantment_combat_copy',source=calix.id,
                   sourceEntry=creature.entered_at,controller=0,name=calix.name)
        sim._resolve_entry_effects([event],calix)
        self.assertEqual(len([item for item in p.battlefield if item.card.name=='Plain enchantment']),
                         original_count+1)
        sim.invariant()
