"""Regression: cumulative extra land drops and all five basic land types."""
import unittest
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from dataclasses import replace
import simulator as s
import test_enchantment_abilities as fixtures


class SessionLearningAdditionalLands(unittest.TestCase):
    setUpClass=classmethod(fixtures.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.EnchantmentChecks.tearDownClass.__func__)
    fixture=fixtures.EnchantmentChecks.fixture
    put=fixtures.EnchantmentChecks.put

    def raw(self,name='Unknown five-color grove',count='an'):
        return dict(name=name,types=['Creature','Enchantment'],subTypes=['Dryad'],
                    superTypes=[],colors=['Green'],colorIdentity=['Green'],manaCost='{2}{G}',
                    power='2',toughness='4',quantity=1,layout='normal',
                    oracleText=('You may play '+count+' additional '+('land' if count in ('an','one') else 'lands')+' on each of your turns.\n'
                                'Lands you control are every basic land type in addition to their other types.'))

    def test_real_dryad_entire_oracle_and_unknown_strict_variants(self):
        card=s.import_diagnostic_card(self.rules,self.lookup['Dryad of the Ilysian Grove'],0,'real',{'Green'})
        self.assertNotEqual(card.kind,'unsupported')
        self.assertEqual(card.event_definition.additional_land_plays,1)
        self.assertEqual(set(card.event_definition.land_type_effect[2]),
                         {'Plains','Island','Swamp','Mountain','Forest'})
        for count,n in [('an',1),('two',2),('three',3)]:
            other=s.import_diagnostic_card(self.rules,self.raw(count=count),0,'new'+count,{'Green'})
            self.assertNotEqual(other.kind,'unsupported')
            self.assertEqual(other.event_definition.additional_land_plays,n)
        raw=self.raw()
        raw['oracleText']+='\nCast a mystery spell for free.'
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'invalid',{'Green'}).kind,'unsupported')

    def test_types_grant_all_mana_colors_to_owned_lands_only(self):
        sim,cards=self.fixture(['Dryad of the Ilysian Grove'])
        mine=next(p for p in sim.players[0].battlefield if p.card.kind=='land')
        enemy_card=next(card for card in sim.players[1].library if card.kind=='land')
        sim.players[1].library.remove(enemy_card)
        enemy=s.Permanent(enemy_card)
        sim.players[1].battlefield.append(enemy)
        original_enemy=set(sim.event_game('main').battlefield[enemy.card.id].definition.subtypes)
        self.put(sim,cards['Dryad of the Ilysian Grove'])
        game=sim.event_game('main')
        self.assertTrue({'Plains','Island','Swamp','Mountain','Forest'}<=set(game.battlefield[mine.card.id].definition.subtypes))
        self.assertEqual(set(game.battlefield[enemy.card.id].definition.subtypes),original_enemy)
        self.assertTrue(set(range(5)) <= {i for options in dict(sim.mana_sources(0))[mine.card.id] for i,amount in enumerate(options) if amount})
        sim.invariant()

    def test_additional_land_works_then_expires_when_source_leaves(self):
        sim,cards=self.fixture(['Dryad of the Ilysian Grove'])
        player=sim.players[0]
        # Move existing cards, do not create new cards; conserve physical identities.
        lands=[p for p in player.battlefield if p.card.kind=='land'][:3]
        for land in lands:
            player.battlefield.remove(land)
            player.hand.append(land.card)
        sim.phase='main'
        sim.land_plays_this_turn=1
        sim.land_played=True
        self.assertFalse(any(c.kind=='land' for c in sim.legal(0)))
        dryad=self.put(sim,cards['Dryad of the Ilysian Grove'])
        self.assertEqual(sim.land_play_limit(0),2)
        self.assertGreaterEqual(len([c for c in sim.legal(0) if c.kind=='land']),3)
        sim.decide=lambda seat: next(c for c in sim.legal(seat) if c.kind=='land')
        sim.step()
        self.assertEqual(sim.land_plays_this_turn,2)
        self.assertFalse(any(c.kind=='land' for c in sim.legal(0)))
        sim.send_to_destination(player,dryad)
        self.assertEqual(sim.land_play_limit(0),1)
        self.assertFalse(any(c.kind=='land' for c in sim.legal(0)))
        sim.invariant()

    def test_basic_type_addition_and_replacement_follow_timestamps(self):
        for moon_last in (False,True):
            sim,cards=self.fixture(['Dryad of the Ilysian Grove','Blood Moon'])
            player=sim.players[0]
            land=next(p for p in player.battlefield if p.card.kind=='land')
            if moon_last:
                self.put(sim,cards['Dryad of the Ilysian Grove'])
            player.hand.remove(cards['Blood Moon'])
            sim.enter_creature(cards['Blood Moon'],sim.players[1])
            if not moon_last:
                self.put(sim,cards['Dryad of the Ilysian Grove'])
            game=sim.event_game('main')
            observed=set(game.battlefield[land.card.id].definition.subtypes)
            self.assertEqual(observed,{'Mountain'} if moon_last else
                             {'Plains','Island','Swamp','Mountain','Forest'})
            sim.invariant()

    def test_extra_land_permission_cumulative_for_multiple_sources(self):
        sim,cards=self.fixture(['Dryad of the Ilysian Grove'])
        source=self.put(sim,cards['Dryad of the Ilysian Grove'])
        self.assertEqual(sim.land_play_limit(0),2)
        # Re-use a card already in the simulated deck rather than inventing a physical card.
        spare=next(c for c in sim.players[0].library if c.kind=='creature')
        # A second source is a separately owned card with the same reusable definition.
        original=spare
        sim.players[0].library.remove(original)
        second=replace(original,kind='creature',event_definition=source.card.event_definition)
        sim.enter_creature(second,sim.players[0])
        self.assertEqual(sim.land_play_limit(0),3)
        sim.send_to_destination(sim.players[0],source)
        self.assertEqual(sim.land_play_limit(0),2)
        sim.invariant()
