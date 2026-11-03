"""Optional Equipment transfer when an equipped creature attacks or dies."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
from card_events import parse_card
import test_enchantment_abilities as fixtures


class TransferTests(unittest.TestCase):
    setUpClass=classmethod(fixtures.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.EnchantmentChecks.tearDownClass.__func__)
    put=fixtures.EnchantmentChecks.put
    token=fixtures.EnchantmentChecks.token
    drain=fixtures.EnchantmentChecks.drain
    ready=fixtures.EnchantmentChecks.ready

    def fixture(self,names):
        cards=[s.import_diagnostic_card(self.rules,self.lookup[name],0,
                'transfer-'+str(i),{'Red','Green','White'}) for i,name in enumerate(names)]
        self.assertTrue(all(card.kind!='unsupported' for card in cards))
        lands=[s.Card('mana'+str(i),'Mana','land',mask=63) for i in range(10)]
        sim=s.Simulator(self.rules,42,decks=(s.demo_deck(0)+cards+lands,s.demo_deck(1)),diagnostic=True)
        sim.manual_priority=True;sim.phase='main'
        player=sim.players[0]
        for card in cards+lands:
            (player.hand if card in player.hand else player.library).remove(card)
        player.hand.extend(cards)
        player.battlefield.extend(s.Permanent(card) for card in lands)
        return sim,{card.name:card for card in cards}

    def test_complete_oracle_and_unseen_names_reject_extra_text(self):
        raw=dict(self.lookup['Rhuk, Hexgold Nabber'])
        parsed=parse_card(raw)
        self.assertTrue(parsed.supported,parsed.reason)
        self.assertTrue(parsed.equipped_creature_transfer)
        self.assertEqual(parsed.abilities,frozenset({'trample','haste'}))
        renamed=dict(raw,name='Unfamiliar Gear Collector',
                     oracleText=raw['oracleText'].replace('Rhuk','Unfamiliar Gear Collector'))
        self.assertTrue(parse_card(renamed).supported)
        self.assertFalse(parse_card(dict(renamed,oracleText=
            renamed['oracleText']+'\nDraw a card.')).supported)
        self.assertFalse(parse_card(dict(renamed,oracleText=
            renamed['oracleText'].replace('all Equipment','one Equipment'))).supported)
        self.assertFalse(parse_card(dict(renamed,types=['Artifact'])).supported)

    def test_attack_uses_live_attachments_at_resolution(self):
        sim,cards=self.fixture(['Rhuk, Hexgold Nabber','Shadowspear','Umbral Mantle'])
        rhuk=self.put(sim,cards['Rhuk, Hexgold Nabber'])
        attacker=self.token(sim,'attacker')
        spear=self.put(sim,cards['Shadowspear'])
        mantle=self.put(sim,cards['Umbral Mantle'])
        spear.attached_to=attacker.card.id
        self.ready(sim)
        sim.declare_attackers([attacker.card.id])
        events=[f.payload[0] for f in sim.stack.items
                if f.payload[0].get('operation')=='transfer_equipment']
        self.assertEqual(len(events),1)
        self.assertEqual(events[0]['triggerKind'],'attacks')
        # The printed "all Equipment attached" is determined at resolution,
        # not locked to the list at the moment this creature attacked.
        spear.attached_to=None
        mantle.attached_to=attacker.card.id
        self.drain(sim)
        self.assertIsNone(spear.attached_to)
        self.assertEqual(mantle.attached_to,rhuk.card.id)
        sim.invariant()

    def test_death_snapshots_attachments_and_does_not_resurrect_equipment(self):
        sim,cards=self.fixture(['Rhuk, Hexgold Nabber','Shadowspear','Umbral Mantle'])
        rhuk=self.put(sim,cards['Rhuk, Hexgold Nabber'])
        victim=self.token(sim,'victim')
        spear=self.put(sim,cards['Shadowspear'])
        mantle=self.put(sim,cards['Umbral Mantle'])
        spear.attached_to=mantle.attached_to=victim.card.id
        sim.destroy_batch([(0,victim)],cards['Rhuk, Hexgold Nabber'])
        events=[f.payload[0] for f in sim.stack.items
                if f.payload[0].get('operation')=='transfer_equipment']
        self.assertEqual(len(events),1)
        self.assertEqual(events[0]['triggerKind'],'dies')
        self.assertEqual(len(events[0]['attachedEntries']),2)
        self.assertIsNone(spear.attached_to)
        sim.send_to_destination(sim.players[0],mantle)
        self.drain(sim)
        self.assertEqual(spear.attached_to,rhuk.card.id)
        self.assertNotIn(mantle,sim.players[0].battlefield)
        sim.invariant()

    def test_may_decline_and_departed_recipient(self):
        sim,cards=self.fixture(['Rhuk, Hexgold Nabber','Shadowspear'])
        rhuk=self.put(sim,cards['Rhuk, Hexgold Nabber'])
        victim=self.token(sim,'victim')
        spear=self.put(sim,cards['Shadowspear'])
        spear.attached_to=victim.card.id
        sim.choose_equipment_transfer=lambda event,available:False
        sim.destroy_batch([(0,victim)],cards['Rhuk, Hexgold Nabber'])
        self.drain(sim)
        self.assertIsNone(spear.attached_to)
        sim.invariant()

        sim2,cards2=self.fixture(['Rhuk, Hexgold Nabber','Shadowspear'])
        rhuk2=self.put(sim2,cards2['Rhuk, Hexgold Nabber'])
        victim2=self.token(sim2,'victim2')
        spear2=self.put(sim2,cards2['Shadowspear'])
        spear2.attached_to=victim2.card.id
        sim2.destroy_batch([(0,victim2)],cards2['Rhuk, Hexgold Nabber'])
        sim2.send_to_destination(sim2.players[0],rhuk2)
        self.drain(sim2)
        self.assertIsNone(spear2.attached_to)
        sim2.invariant()


if __name__=='__main__':
    unittest.main()
