package dev.casz.caszualmtg;

public final class CommanderSimpleCardsCheck {
 private static void check(boolean value,String reason){if(!value)throw new AssertionError(reason);}
 public static void main(String[] args){
  var bear=CommanderSimpleCards.creature("Creature — Bear","","2","2").orElseThrow();
  var eagle=CommanderSimpleCards.creature("Creature — Bird","Flying, vigilance","2","3").orElseThrow();
  var spider=CommanderSimpleCards.creature("Creature — Spider","Reach","1","4").orElseThrow();
  var hasty=CommanderSimpleCards.creature("Creature — Goblin","Haste","1","1").orElseThrow();
  check(CommanderSimpleCards.creature("Creature — Elf","When this enters, draw a card.","2","2").isEmpty(),
    "Triggers must not be silently ignored");
  check(CommanderSimpleCards.creature("Creature — Golem","{T}: Add {C}.","2","2").isEmpty(),
    "Activated ability unsupported");
  check(CommanderSimpleCards.creature("Creature — Golem","","*","2").isEmpty(),
    "Variable toughness/power unsupported");
  check(CommanderSimpleCards.creature("Sorcery","","2","2").isEmpty(),"Not a creature");
  check(!CommanderSimpleCards.canAttack(bear,true,false),"Summoning sickness");
  check(CommanderSimpleCards.canAttack(hasty,true,false),"Haste");
  check(!CommanderSimpleCards.canAttack(hasty,false,true),"Tapped attacker");
  check(!CommanderSimpleCards.canBlock(bear,eagle,false),"Land-bound bear can't block flying");
  check(CommanderSimpleCards.canBlock(spider,eagle,false),"Reach blocks flying");
  check(!CommanderSimpleCards.canBlock(spider,eagle,true),"Tapped creatures can't block");
  var blocked=CommanderSimpleCards.combat(bear,spider);
  check(blocked.playerDamage()==0&&!blocked.attackerDies()&&!blocked.blockerDies(),
    "Two-power attacker vs 1/4 spider should bounce");
  var equal=CommanderSimpleCards.combat(bear,bear);
  check(equal.attackerDies()&&equal.blockerDies()&&equal.playerDamage()==0,
    "Simultaneous lethal creature damage");
  var open=CommanderSimpleCards.combat(eagle,null);
  check(open.playerDamage()==2&&!open.tapAttacker(),"Vigilance should not tap to attack");
  var enemy=new CommanderRules.Turn();
  for(int t=0;t<20;t++){
   if(!enemy.combatDamageFromCommander("same-commander",2))continue;
   break;
  }
  check(enemy.lost()&&enemy.life()==18&&enemy.commanderDamage("same-commander")==22,
    "Simple full-game lethal commander-damage outcome");
  System.out.println("Simple creature and combat checks passed.");
 }
}
