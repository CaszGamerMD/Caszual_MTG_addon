"""Generic cast events, type filters and ordered Oracle effect regression."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
import test_enchantment_abilities as existing
from oracle_abilities import compile_abilities, cast_matches

SYTHIS="Sythis, Harvest's Hand"

class CastTriggerChecks(unittest.TestCase):
    setUpClass=classmethod(existing.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(existing.EnchantmentChecks.tearDownClass.__func__)
    fixture=existing.EnchantmentChecks.fixture
    put=existing.EnchantmentChecks.put

    def setup_sythis(self):
        sim,cards=self.fixture([SYTHIS])
        source=self.put(sim,cards[SYTHIS])
        self.assertTrue(source.card.event_definition.triggers)
        self.assertTrue(any(t.event=='cast' for t in source.card.event_definition.triggers))
        return sim,source

    def spell(self,identifier,kind='enchantment',printed=('Enchantment',)):
        return s.Card(identifier,'Unseen '+identifier,kind,mana_cost='{0}',
                      printed_types=printed)

    def test_whole_oracle_text_not_name_based_and_rejects_unknown_clause(self):
        raw=dict(self.lookup[SYTHIS])
        raw['name']='Unseen Nymph'
        card=s.import_diagnostic_card(self.rules,raw,0,'unseen',{'White','Green'})
        self.assertEqual(card.kind,'creature')
        self.assertEqual(card.event_definition.triggers[0].event,'cast')
        raw['oracleText']+='\nWhenever you blink, make a mystery card.'
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'bad',{'White','Green'}).kind,'unsupported')
        self.assertIsNone(compile_abilities('Whenever you cast an enchantment spell, you gain 1 life and exile a permanent.'))

    def test_trigger_waits_on_stack_and_executes_both_effects_in_order(self):
        sim,source=self.setup_sythis()
        spell=self.spell('glow')
        sim.players[0].hand.append(spell)
        before=len(sim.players[0].hand)
        sim.cast_spell(0,spell)
        self.assertEqual([f.payload[0]['operation'] for f in sim.stack.items],['spell','ordered_effects'])
        self.assertEqual(sim.players[0].life,40)
        self.assertEqual(len(sim.players[0].hand),before-1)
        sim.pass_priority(0);sim.pass_priority(1)
        self.assertEqual(sim.players[0].life,41)
        self.assertEqual(len(sim.players[0].hand),before)
        self.assertEqual(len(sim.stack.items),1)
        sim.pass_priority(0);sim.pass_priority(1)
        self.assertTrue(any(p.card.id==spell.id for p in sim.players[0].battlefield))
        sim.invariant()

    def test_cast_trigger_still_resolves_after_spell_countered(self):
        sim,_=self.setup_sythis()
        spell=self.spell('aura')
        counter=s.Card('counter','Unseen counter','counter_spell',mana_cost='{0}',instant=True,
                       counter_filter='any',printed_types=('Instant',))
        sim.players[0].hand.append(spell)
        sim.players[1].hand.append(counter)
        sim.cast_spell(0,spell)
        target=sim.stack.items[0].id
        before=len(sim.players[0].hand)
        sim.pass_priority(0)
        sim.cast_spell(1,counter,target=target)
        sim.pass_priority(1);sim.pass_priority(0)
        self.assertIn(spell,sim.players[0].graveyard)
        self.assertEqual(sim.players[0].life,40)
        sim.pass_priority(0);sim.pass_priority(1)
        self.assertEqual(sim.players[0].life,41)
        self.assertEqual(len(sim.players[0].hand),before+1)
        self.assertFalse(sim.stack.items)
        sim.invariant()

    def test_trigger_survives_source_leaving_before_resolution(self):
        sim,source=self.setup_sythis()
        spell=self.spell('artifact',kind='artifact',printed=('Artifact','Enchantment'))
        sim.players[0].hand.append(spell)
        sim.cast_spell(0,spell)
        before=len(sim.players[0].hand)
        sim.send_to_destination(sim.players[0],source)
        sim.pass_priority(0);sim.pass_priority(1)
        self.assertEqual(sim.players[0].life,41)
        self.assertEqual(len(sim.players[0].hand),before+1)
        sim.invariant()

    def test_type_and_controller_filter_enchantment_creatures_count(self):
        sim,_=self.setup_sythis()
        creature=self.spell('bear',kind='creature',printed=('Creature',))
        sim.players[0].hand.append(creature)
        sim.cast_spell(0,creature)
        self.assertEqual(len(sim.stack.items),1)
        sim.pass_priority(0);sim.pass_priority(1)
        self.assertEqual(sim.players[0].life,40)
        mixed=self.spell('nymph',kind='creature',printed=('Creature','Enchantment'))
        sim.players[0].hand.append(mixed)
        sim.cast_spell(0,mixed)
        self.assertEqual(len(sim.stack.items),2)
        # Opponent's enchantment is not our cast.
        sim.active=1;sim.stack.active=1;sim.stack.priority=1
        rival=self.spell('rival')
        sim.players[1].hand.append(rival)
        sim.cast_spell(1,rival)
        self.assertEqual(sum(f.payload[0]['operation']=='ordered_effects' for f in sim.stack.items),1)

    def test_generic_spell_subtypes_and_sequence_parse(self):
        for phrase in ('a spell','a creature spell','a noncreature spell',
                       'an enchantment spell','an instant spell','a sorcery spell',
                       'an artifact spell','a planeswalker spell'):
            program=compile_abilities('Whenever you cast '+phrase+', you gain 1 life and draw a card.')
            self.assertIsNotNone(program,phrase)
            trigger=program.triggers[0]
            self.assertEqual(trigger.effect.operation,'ordered_effects')
            self.assertEqual([part.operation for part in trigger.effect.steps],['gain_life','draw_cards'])
        self.assertIsNone(compile_abilities('Whenever you cast an enchantment spell, draw a card and do something unknown.'))
