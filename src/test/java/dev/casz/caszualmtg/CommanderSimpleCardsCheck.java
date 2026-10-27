package dev.casz.caszualmtg;

public final class CommanderSimpleCardsCheck {
 private static void check(boolean value,String reason){if(!value)throw new AssertionError(reason);}
 public static void main(String[] args){
  check(CommanderSimpleCards.creature("Creature — Bird","Flying (This creature can't be blocked except by creatures with flying or reach.)","2","2").isPresent(),"reminder text does not hide supported keyword");
  check(CommanderSimpleCards.creature("Creature — Bird","Flying (Reminder.)\nWhen this creature enters, draw a card.","2","2").isEmpty(),"actual ETB clause cannot be stripped");
  check(CommanderSimpleSpells.parse("Sorcery","Draw two cards.").orElseThrow().draw()==2,"draw two");
  check(CommanderSimpleSpells.parse("Instant","You gain 3 life.").orElseThrow().life()==3,"gain life");
  check(CommanderSimpleSpells.parse("Sorcery","Draw two cards. You lose 2 life.").isEmpty(),"do not ignore drawback");
  check(CommanderSimpleSpells.parse("Sorcery","Target player draws two cards.").isEmpty(),"targeting not inferred");
  check(CommanderSimpleSpells.parse("Sorcery","Draw X cards.").isEmpty(),"variable draw not guessed");
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
  var snake=CommanderSimpleCards.creature("Creature — Snake","Deathtouch (Any amount of damage this deals to a creature is enough to destroy it.)","1","1").orElseThrow();
  var giant=CommanderSimpleCards.creature("Creature — Giant","","6","6").orElseThrow();
  var immortal=CommanderSimpleCards.creature("Creature — Golem","Indestructible","2","2").orElseThrow();
  var trampler=CommanderSimpleCards.creature("Creature — Beast","Trample, lifelink","5","5").orElseThrow();
  check(CommanderSimpleCards.combat(snake,giant).blockerDies(),"Positive deathtouch damage kills large blocker");
  check(CommanderSimpleCards.combat(giant,snake).attackerDies(),"Blocking deathtouch kills attacker simultaneously");
  check(!CommanderSimpleCards.combat(snake,immortal).blockerDies(),"Indestructible survives deathtouch");
  check(!CommanderSimpleCards.combat(immortal,giant).attackerDies(),"Indestructible survives lethal damage");
  var zero=CommanderSimpleCards.creature("Creature — Snake","Deathtouch, lifelink","0","1").orElseThrow();
  check(!CommanderSimpleCards.combat(zero,bear).blockerDies(),"Zero damage does not trigger deathtouch");
  check(CommanderSimpleCards.combat(zero,bear).attackerLifeGain()==0,"Zero damage gains no life");
  var trample=CommanderSimpleCards.combat(trampler,bear);
  check(trample.playerDamage()==3&&trample.blockerDies(),"Trample assigns lethal before excess to player");
  check(trample.attackerLifeGain()==5,"Lifelink counts damage to blocker and player");
  check(CommanderSimpleCards.combat(trampler,immortal).playerDamage()==3,"Indestructible still requires lethal trample assignment");
  var venom=CommanderSimpleCards.creature("Creature — Beast","Deathtouch, trample","5","5").orElseThrow();
  check(CommanderSimpleCards.combat(venom,giant).playerDamage()==4,"Deathtouch plus trample assigns one lethal damage");
  var venomWall=CommanderSimpleCards.combat(venom,immortal);
  check(venomWall.playerDamage()==4&&!venomWall.blockerDies(),"Deathtouch tramples over indestructible without destroying it");
  var healer=CommanderSimpleCards.creature("Creature — Cleric","Lifelink","2","2").orElseThrow();
  check(CommanderSimpleCards.combat(bear,healer).blockerLifeGain()==2,"Dying blocker still gains lifelink life");
  check(CommanderSimpleCards.combat(healer,null).attackerLifeGain()==2,"Unblocked lifelink");
  check(CommanderSimpleCards.creature("Creature — Knight","First strike","2","2").isEmpty(),"First strike remains unsupported until damage steps exist");
  check(CommanderSimpleCards.creature("Creature — Knight","Double strike","2","2").isEmpty(),"Double strike cannot be approximated");
  check(CommanderSimpleCards.creature("Creature — Beast","Trample\nWhenever this creature attacks, draw a card.","5","5").isEmpty(),"Keyword must not hide an unsupported trigger");
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
