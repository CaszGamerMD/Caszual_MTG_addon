"""Real and unseen tribal death/exile/cast programs."""
import unittest
import test_enchantment_abilities as f
import simulator as s

class DeathExileCastChecks(unittest.TestCase):
    setUpClass=classmethod(f.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(f.EnchantmentChecks.tearDownClass.__func__)
    fixture=f.EnchantmentChecks.fixture
    put=f.EnchantmentChecks.put
    token=f.EnchantmentChecks.token
    drain=f.EnchantmentChecks.drain

    def prepare(self):
        sim,cards=self.fixture(['Lifelink'])
        raw=self.lookup['Rundvelt Hordemaster']
        lord=s.import_diagnostic_card(self.rules,raw,0,'lord',{'Red'})
        self.assertEqual(lord.kind,'creature')
        sim.players[0].hand.remove(cards['Lifelink']);sim.players[0].hand.append(lord)
        self.put(sim,lord)
        return sim,lord

    def test_real_renamed_and_extra_unknown(self):
        raw=dict(self.lookup['Rundvelt Hordemaster'])
        self.assertNotEqual(s.import_diagnostic_card(self.rules,raw,0,'a',set()).kind,'unsupported')
        raw['name']='Unknown tribal commander'
        self.assertNotEqual(s.import_diagnostic_card(self.rules,raw,0,'b',set()).kind,'unsupported')
        raw['oracleText']+='\nTake an extra turn.'
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'c',set()).kind,'unsupported')

    def test_other_goblins_and_simultaneous_deaths(self):
        sim,lord=self.prepare()
        source=next(p for p in sim.players[0].battlefield if p.card.id==lord.id)
        gob=self.token(sim,'gob',subtypes=('Goblin',))
        enemy=self.token(sim,'enemy',seat=1,subtypes=('Goblin',))
        self.assertEqual(sim.effective_card(source).power,1)
        self.assertEqual(sim.effective_card(gob).power,3)
        self.assertEqual(sim.effective_card(enemy).power,2)
        game=sim.event_game('main')
        triggers=game.death_triggers([lord.id,gob.card.id])
        self.assertEqual(len([t for t in triggers if t['operation']=='exile_top_cast_permission']),2)
        sim.send_to_destination(sim.players[0],source,snapshot=game)
        sim.send_to_destination(sim.players[0],gob,snapshot=game)
        self.assertNotIn(gob.card,sim.players[0].graveyard)
        sim.resolve_entry_triggers(triggers,lord);self.drain(sim)
        self.assertEqual(len([t for t in sim.events if t['kind']=='exile_top']),2)
        sim.invariant()

    def test_top_card_cost_and_permission(self):
        sim,lord=self.prepare()
        top=s.Card('top-gob','Unknown Goblin','creature',mana_cost='{2}',power=2,toughness=2,
                   traits='2;2;',printed_types=('Creature',),land_subtypes=('Goblin',))
        sim.players[0].library.append(top);sim.card_owners[top.id]=0
        sim.total_cards=(sim.total_cards[0]+1,sim.total_cards[1])
        gob=self.token(sim,'gob',subtypes=('Goblin',))
        game=sim.event_game('main');triggers=game.death_triggers([gob.card.id])
        sim.send_to_destination(sim.players[0],gob,snapshot=game)
        sim.resolve_entry_triggers(triggers,lord);self.drain(sim)
        self.assertIn(top,sim.players[0].exile)
        sim.players[0].mana_pool=[0]*6
        for p in sim.players[0].battlefield:
            if p.card.kind=='land':p.tapped=True
        with self.assertRaises(ValueError):sim.cast_spell(0,top,exile_permission=True)
        sim.players[0].mana_pool=[0,0,0,0,0,2]
        sim.cast_spell(0,top,exile_permission=True);self.drain(sim)
        self.assertTrue(any(p.card.id==top.id for p in sim.players[0].battlefield))
        self.assertNotIn(top.id,sim.exile_cast_permissions)
        sim.invariant()

    def test_nonmatching_top_exiles_without_cast_permission(self):
        sim,lord=self.prepare()
        top=s.Card('top-elf','Unknown Elf','creature',mana_cost='{1}',printed_types=('Creature',),land_subtypes=('Elf',))
        sim.players[0].library.append(top);sim.card_owners[top.id]=0
        sim.total_cards=(sim.total_cards[0]+1,sim.total_cards[1])
        gob=self.token(sim,'gob',subtypes=('Goblin',))
        game=sim.event_game('main');triggers=game.death_triggers([gob.card.id])
        sim.send_to_destination(sim.players[0],gob,snapshot=game)
        sim.resolve_entry_triggers(triggers,lord)
        self.assertFalse(any(top.name in str(e['details']) for e in sim.events if e['kind']=='stack_push'))
        self.drain(sim)
        self.assertIn(top,sim.players[0].exile)
        self.assertNotIn(top.id,sim.exile_cast_permissions)
        revealed=next(e['details'] for e in sim.events if e['kind']=='exile_top' and e['details']['cardId']==top.id)
        self.assertEqual((revealed['cardOwner'],revealed['controller'],revealed['eligible']),(0,0,False))
        sim.invariant()

    def test_permission_expires_at_end_of_next_own_turn(self):
        sim,lord=self.prepare()
        top=s.Card('expiring-gob','Unknown Goblin','creature',mana_cost='{1}',power=1,toughness=1,
                   traits='1;1;',printed_types=('Creature',),land_subtypes=('Goblin',))
        sim.players[0].library.append(top);sim.card_owners[top.id]=0
        sim.total_cards=(sim.total_cards[0]+1,sim.total_cards[1])
        gob=self.token(sim,'gob',subtypes=('Goblin',))
        game=sim.event_game('main');triggers=game.death_triggers([gob.card.id])
        sim.send_to_destination(sim.players[0],gob,snapshot=game)
        sim.resolve_entry_triggers(triggers,lord);self.drain(sim)
        expiry=sim.exile_cast_permissions[top.id][1]
        self.assertEqual(expiry,sim.turn+2)
        sim.turn=expiry;sim.active=0;sim.phase='cleanup';sim._step()
        self.assertNotIn(top.id,sim.exile_cast_permissions)
        self.assertIn(top,sim.players[0].exile)
        self.assertNotIn(top,sim.permitted_exile_cards(0))
        sim.invariant()

    def test_unseen_other_subtype_and_cast_subtype_are_parameters(self):
        raw=dict(self.lookup['Rundvelt Hordemaster'],name='Unknown Elf captain')
        raw['oracleText']=raw['oracleText'].replace('Goblins','Elves').replace('Goblin','Elf')
        parsed=s.import_diagnostic_card(self.rules,raw,0,'unseen',{'Red'})
        self.assertNotEqual(parsed.kind,'unsupported')
        self.assertEqual(parsed.event_definition.triggers[0].subject.self_or_controlled_subtype,'Elf')
        self.assertEqual(parsed.event_definition.triggers[0].effect.library_filter,('subtype','Elf','creature'))
