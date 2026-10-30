"""Equipment that scales with all known counters and turns attached planeswalkers into creatures."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
import test_enchantment_abilities as fixtures


class CounterEquipmentChecks(unittest.TestCase):
    setUpClass=classmethod(fixtures.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.EnchantmentChecks.tearDownClass.__func__)
    token=fixtures.EnchantmentChecks.token
    drain=fixtures.EnchantmentChecks.drain

    def prepare(self):
        card=s.import_diagnostic_card(self.rules,self.lookup["Luxior, Giada's Gift"],0,'luxior',{'White'})
        self.assertEqual(card.kind,'equipment')
        self.assertEqual(card.event_definition.attachment_counter_scale,(1,1))
        sim=s.Simulator(self.rules,42,decks=(s.demo_deck(0)+[card],s.demo_deck(1)),diagnostic=True)
        sim.manual_priority=True
        p=sim.players[0]
        (p.hand if card in p.hand else p.library).remove(card)
        sim.enter_creature(card,p)
        sim.phase='main';sim.active=0;sim.stack.priority=0;p.mana_pool[5]=15
        return sim,card

    def test_full_program_scales_unseen_multipliers_and_rejects_extra_lines(self):
        source=self.lookup["Luxior, Giada's Gift"]
        raw=dict(source,name='Unseen Gift',
            oracleText=source['oracleText'].replace('+1/+1 for each counter','+3/+2 for each counter'))
        card=s.import_diagnostic_card(self.rules,raw,0,'gift',{'White'})
        self.assertEqual(card.kind,'equipment')
        self.assertEqual(card.event_definition.attachment_counter_scale,(3,2))
        raw['oracleText']+='\nWhenever you blink, win the game.'
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'bad',{'White'}).kind,'unsupported')

    def test_equip_creature_counts_plus_one_and_charge_counters_once(self):
        sim,card=self.prepare()
        host=self.token(sim,'host')
        host.counters=2;host.charge_counters=1
        old=sim.effective_card(host).power
        sim.activate_equip(0,card.id,host.card.id)
        self.drain(sim)
        self.assertEqual(sim.effective_card(host).power,old+3)
        source=next(p for p in sim.players[0].battlefield if p.card.id==card.id)
        source.attached_to=None
        self.assertEqual(sim.effective_card(host).power,old)
        sim.invariant()

    def test_alternate_equip_to_planeswalker_changes_type_and_uses_loyalty_counters(self):
        sim,card=self.prepare()
        definition=s.EventDefinition('Unseen planeswalker',frozenset({'Planeswalker'}),
                                    frozenset(),False,0,0,frozenset(),loyalty=4)
        walker=s.Card('walker','Unseen planeswalker','planeswalker',
                      event_definition=definition,printed_types=('Planeswalker',),is_token=True)
        sim.players[0].battlefield.append(s.Permanent(walker,loyalty=4))
        choices=[x for x in sim.equip_choices(0) if x.kind=='equip_planeswalker']
        self.assertEqual(len(choices),1)
        sim.activate_equip(0,card.id,walker.id,planeswalker=True)
        self.drain(sim)
        source=next(p for p in sim.players[0].battlefield if p.card.id==card.id)
        game=sim.event_game('main');target=game.battlefield[walker.id]
        self.assertIn('Creature',target.definition.types)
        self.assertNotIn('Planeswalker',target.definition.types)
        self.assertEqual(game.stats(target),(4,4))
        source.attached_to=None
        restored=sim.event_game('main').battlefield[walker.id]
        self.assertIn('Planeswalker',restored.definition.types)
        self.assertNotIn('Creature',restored.definition.types)
        sim.invariant()
