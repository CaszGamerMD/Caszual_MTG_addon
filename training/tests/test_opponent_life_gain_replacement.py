"""Strict, controller-scoped replacement of an opponent's life gain with loss."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
from oracle_abilities import compile_abilities
import test_enchantment_abilities as fixtures

class OpponentLifeGainReplacementChecks(unittest.TestCase):
    setUpClass=classmethod(fixtures.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.EnchantmentChecks.tearDownClass.__func__)

    def raw(self):return dict(self.lookup['Tainted Remedy'])

    def test_real_and_unseen_complete_oracle_and_unknown_clause(self):
        raw=self.raw()
        for name in ('Tainted Remedy','Unseen Antidote Curse'):
            raw['name']=name
            parsed=s.import_diagnostic_card(self.rules,raw,0,'remedy',{'Black'})
            self.assertEqual(parsed.kind,'enchantment')
            self.assertTrue(parsed.event_definition.opponent_life_gain_becomes_loss)
        raw['oracleText']+='\nIf you would win the game, draw an extra card.'
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'bad',{'Black'}).kind,'unsupported')
        self.assertIsNone(compile_abilities('If an opponent would gain life, that player loses that much life instead.\nWhenever you blink, win the game.'))
        self.assertIsNone(compile_abilities('If an opponent would gain life, that player loses twice that much life instead.'))

    def prepare(self,controller=0,other=()):
        raw=self.raw()
        card=s.import_diagnostic_card(self.rules,raw,controller,'remedy',{'Black'})
        extras=[s.import_diagnostic_card(self.rules,self.lookup[name],1-controller,'extra'+str(i),{'White'}) for i,name in enumerate(other)]
        decks=[s.demo_deck(0),s.demo_deck(1)]
        decks[controller].append(card)
        decks[1-controller].extend(extras)
        sim=s.Simulator(self.rules,42,decks=tuple(decks),diagnostic=True)
        for seat,cards in ((controller,[card]),(1-controller,extras)):
            for c in cards:
                player=sim.players[seat]
                (player.hand if c in player.hand else player.library).remove(c)
                pending=sim.enter_creature(c,player)
                sim.resolve_entry_triggers(pending,c)
        return sim,card,extras

    def test_opponent_loss_is_not_gain_and_controller_still_gains(self):
        sim,card,_=self.prepare()
        sim.gain_life(1,3)
        self.assertEqual([p.life for p in sim.players],[40,37])
        self.assertEqual(sim.life_gained_turn,[0,0])
        self.assertEqual(sim._waiting_triggers,[])
        sim.gain_life(0,2)
        self.assertEqual([p.life for p in sim.players],[42,37])
        self.assertEqual(sim.life_gained_turn,[2,0])
        sim.gain_life(1,0)
        self.assertEqual(sim.players[1].life,37)
        sim.invariant()

    def test_boon_reflection_opponent_prefers_replacement_before_doubling(self):
        sim,card,extras=self.prepare(other=('Boon Reflection',))
        sim.gain_life(1,4)
        self.assertEqual(sim.players[1].life,36)
        self.assertEqual(sim.life_gained_turn[1],0)
        source=next(p for p in sim.players[0].battlefield if p.card.id==card.id)
        sim.send_to_destination(sim.players[0],source)
        sim.gain_life(1,4)
        self.assertEqual(sim.players[1].life,44)
        self.assertEqual(sim.life_gained_turn[1],8)
        sim.invariant()

    def test_opposing_controller_direction_is_symmetric(self):
        sim,_,_=self.prepare(controller=1)
        sim.gain_life(0,5)
        self.assertEqual([p.life for p in sim.players],[35,40])
        sim.gain_life(1,5)
        self.assertEqual([p.life for p in sim.players],[35,45])
        sim.invariant()

if __name__=='__main__':unittest.main()
