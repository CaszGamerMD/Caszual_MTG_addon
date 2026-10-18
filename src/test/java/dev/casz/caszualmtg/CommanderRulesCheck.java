package dev.casz.caszualmtg;

import java.util.*;

/** Executable deterministic checks for the conservative Commander rules core. */
public final class CommanderRulesCheck {
 static void expect(boolean condition,String message){
  if(!condition)throw new AssertionError(message);
 }
 public static void main(String[] args){
  var leader=new CommanderRules.Card("Sample Commander","Legendary Creature — Wizard",3,true);
  var basic=new CommanderRules.Card("Island","Basic Land — Island",2,false);
  var pool=new ArrayList<CommanderRules.Card>();
  pool.add(leader);
  for(int i=0;i<99;i++)pool.add(basic);
  expect(CommanderRules.validateDeck(pool,List.of(leader)).isEmpty(),"Valid mono-basic deck rejected");
  pool.set(99,new CommanderRules.Card("Illegal Green Spell","Sorcery",16,false));
  expect(CommanderRules.validateDeck(pool,List.of(leader)).stream()
    .anyMatch(s->s.contains("color identity")),"Off-color card accepted");
  pool.set(99,new CommanderRules.Card("Unique Spell","Sorcery",1,false));
  pool.set(98,new CommanderRules.Card("Unique Spell","Sorcery",1,false));
  expect(CommanderRules.validateDeck(pool,List.of(leader)).stream()
    .anyMatch(s->s.contains("Duplicate")),"Duplicate nonbasic accepted");
  expect(!CommanderRules.validateDeck(pool.subList(0,99),List.of(leader)).isEmpty(),
    "Short deck accepted");

  var turn=new CommanderRules.Turn();
  expect(turn.life()==40,"Commander must start at 40 life");
  expect(!turn.canPlayLand(),"Land permitted in untap");
  turn.phase(CommanderRules.Phase.PRECOMBAT_MAIN);
  expect(turn.playLand()&&!turn.playLand(),"More than one land played");
  turn.begin();
  turn.phase(CommanderRules.Phase.POSTCOMBAT_MAIN);
  expect(turn.playLand(),"Land-play counter did not reset");
  expect(turn.commanderTax("first")==0,"Initial commander tax");
  turn.commanderCast("first");
  turn.commanderCast("first");
  expect(turn.commanderTax("first")==4,"Tax must be +2 per prior cast");
  expect(turn.commanderTax("second")==0,"Commander tax should be per commander");
  expect(!turn.combatDamageFromCommander("source1",20),"20 commander damage prematurely lethal");
  expect(turn.combatDamageFromCommander("source1",1),"21 commander damage must be lethal");
  expect(turn.commanderDamage("source1")==21&&turn.lost(),"Commander loss was not recorded");
  System.out.println("Commander rules pilot checks passed.");
 }
}
