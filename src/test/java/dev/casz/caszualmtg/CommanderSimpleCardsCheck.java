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
  check(CommanderSimpleCards.creature("Creature — Knight","First strike","2","2").isPresent(),"First strike recognized");
  check(CommanderSimpleCards.creature("Creature — Knight","Double strike","2","2").isPresent(),"Double strike recognized");
  check(CommanderSimpleCards.creature("Creature — Beast","Trample\nWhenever this creature attacks, draw a card.","5","5").isEmpty(),"Keyword must not hide an unsupported trigger");
  var knight=CommanderSimpleCards.creature("Creature — Knight","First strike","2","2").orElseThrow();
  var duelist=CommanderSimpleCards.creature("Creature — Warrior","Double strike","2","2").orElseThrow();
  var quick=CommanderSimpleCards.combat(knight,bear);
  check(!quick.attackerDies()&&quick.blockerDies(),"First strike kills blocker before retaliation");
  var defended=CommanderSimpleCards.combat(bear,knight);
  check(defended.attackerDies()&&!defended.blockerDies(),"First strike blocker kills before normal attacker damage");
  var both=CommanderSimpleCards.combat(knight,knight);
  check(both.attackerDies()&&both.blockerDies(),"Opposing first strikers deal simultaneously");
  check(CommanderSimpleCards.combat(duelist,null).playerDamage()==4,"Unblocked double strike deals twice");
  var stopped=CommanderSimpleCards.combat(duelist,bear);
  check(stopped.blockerDies()&&!stopped.attackerDies()&&stopped.playerDamage()==0,"Double strike without trample stays blocked after blocker dies");
  var crush=CommanderSimpleCards.creature("Creature — Beast","Double strike, trample, lifelink","3","3").orElseThrow();
  var crushResult=CommanderSimpleCards.combat(crush,bear);
  check(crushResult.playerDamage()==4&&crushResult.attackerLifeGain()==6,"Double strike trample spills in both damage steps");
  var four=CommanderSimpleCards.creature("Creature — Beast","","1","4").orElseThrow();
  check(CommanderSimpleCards.combat(duelist,four).blockerDies(),"Marked first-strike damage counts toward lethal in normal step");
  var lethalFirst=CommanderSimpleCards.creature("Creature — Snake","First strike, deathtouch","1","1").orElseThrow();
  check(CommanderSimpleCards.combat(lethalFirst,giant).blockerDies()&&!CommanderSimpleCards.combat(lethalFirst,giant).attackerDies(),"First strike deathtouch removes large blocker before retaliation");
  var survivor=CommanderSimpleCards.combat(duelist,immortal);
  check(!survivor.blockerDies()&&survivor.attackerDies(),"Indestructible blocker survives both steps and retaliates normally");
  check(CommanderSimpleCards.combat(duelist,null,40,1).playerDamage()==2,"First-strike lethal player damage stops later step");
  var drainWall=CommanderSimpleCards.creature("Creature — Wall","First strike, lifelink","2","5").orElseThrow();
  var drain=CommanderSimpleCards.combat(crush,drainWall,40,1);
  check(drain.playerDamage()==1&&drain.blockerLifeGain()==2,"First-step blocker lifelink keeps defender alive until normal-step trample");
  var shadow=CommanderSimpleCards.creature("Creature — Spirit","Shadow (This creature can block or be blocked by only creatures with shadow.)","2","2").orElseThrow();
  var skulker=CommanderSimpleCards.creature("Creature — Rogue","Skulk","2","2").orElseThrow();
  var rider=CommanderSimpleCards.creature("Creature — Soldier","Horsemanship","2","2").orElseThrow();
  check(!CommanderSimpleCards.canBlock(bear,shadow,false),"Ordinary creature cannot block shadow");
  check(!CommanderSimpleCards.canBlock(shadow,bear,false),"Shadow cannot block ordinary attacker");
  check(CommanderSimpleCards.canBlock(shadow,shadow,false),"Shadow blocks shadow");
  check(!CommanderSimpleCards.canBlock(shadow,shadow,true),"Tapped shadow cannot block");
  check(!CommanderSimpleCards.canBlock(giant,skulker,false),"Greater power cannot block skulk");
  check(CommanderSimpleCards.canBlock(bear,skulker,false),"Equal power can block skulk");
  check(CommanderSimpleCards.canBlock(spider,skulker,false),"Lesser power can block skulk");
  check(CommanderSimpleCards.canBlock(skulker,giant,false),"Skulk does not restrict its own blocks");
  check(!CommanderSimpleCards.canBlock(eagle,rider,false),"Flying cannot block horsemanship");
  check(!CommanderSimpleCards.canBlock(spider,rider,false),"Reach cannot block horsemanship");
  check(CommanderSimpleCards.canBlock(rider,rider,false),"Horsemanship blocks horsemanship");
  check(CommanderSimpleCards.canBlock(rider,bear,false),"Horsemanship can block ordinary attackers");
  var airShadow=CommanderSimpleCards.creature("Creature — Spirit","Flying, shadow","2","2").orElseThrow();
  check(!CommanderSimpleCards.canBlock(shadow,airShadow,false),"Shadow alone does not bypass flying");
  check(!CommanderSimpleCards.canBlock(eagle,airShadow,false),"Flying alone does not bypass shadow");
  check(CommanderSimpleCards.canBlock(airShadow,airShadow,false),"Matching flying and shadow can block");
  var airSkulk=CommanderSimpleCards.creature("Creature — Spirit","Flying, skulk","2","2").orElseThrow();
  check(!CommanderSimpleCards.canBlock(bear,airSkulk,false),"Skulk does not bypass flying restriction");
  check(CommanderSimpleCards.canBlock(spider,airSkulk,false),"Low-power reach satisfies both restrictions");
  check(!CommanderSimpleCards.canBlock(shadow,rider,false),"Horsemanship does not bypass blocker's shadow");
  check(CommanderSimpleCards.creature("Creature — Spirit","Shadow\nWhenever this creature attacks, draw a card.","2","2").isEmpty(),"Evasion never hides unsupported triggers");
  check(CommanderSimpleCards.creature("Creature — Rogue","Skulk, menace","2","2").isEmpty(),"Multi-blocker menace remains unsupported");
  var lethalFlyer=CommanderVictory.attack(eagle,java.util.List.of(giant),false,40,2);
  var blockedGiant=CommanderVictory.attack(giant,java.util.List.of(giant),false,40,2);
  check(lethalFlyer.lethal()&&!blockedGiant.lethal()&&lethalFlyer.compareTo(blockedGiant)>0,
    "Lethal evasive attacker is preferred to larger blocked creature");
  check(!CommanderVictory.attack(eagle,java.util.List.of(spider),false,40,2).lethal(),
    "Reach blocker prevents a false flying lethal");
  check(!CommanderVictory.attack(eagle,java.util.List.of(),true,40,2).lethal(),
    "Unknown blocker prevents a forced-lethal claim");
  check(CommanderVictory.attack(duelist,java.util.List.of(),false,40,4).lethal(),
    "Double strike contributes both hits to lethal");
  check(!CommanderVictory.attack(duelist,java.util.List.of(bear),false,40,4).lethal(),
    "Dead blocker still stops double strike without trample");
  check(CommanderVictory.attack(crush,java.util.List.of(bear),false,40,4).lethal(),
    "Trample and double strike can force lethal through a blocker");
  check(!CommanderVictory.attack(crush,java.util.List.of(drainWall),false,40,1).lethal(),
    "Blocking lifelink prevents lethal even when raw damage reaches starting life");
  check(CommanderVictory.attack(snake,java.util.List.of(giant),false,40,40).mayDie(),
    "Trade risk is evaluated from legal responses");
  check(!CommanderVictory.attack(eagle,java.util.List.of(giant),false,40,40).mayDie(),
    "An illegal blocker does not create imaginary trade risk");
  var a=new CommanderVictory.Participant("self",false,true);
  var b=new CommanderVictory.Participant("enemy",false,true);
  var deadB=new CommanderVictory.Participant("enemy",true,true);
  var c=new CommanderVictory.Participant("third",false,true);
  check(CommanderVictory.result("self",true,false,java.util.List.of(a,b))==CommanderVictory.Result.ONGOING,"Two living players is ongoing");
  check(CommanderVictory.result("self",true,false,java.util.List.of(a,deadB))==CommanderVictory.Result.WON,"Last survivor wins");
  check(CommanderVictory.result("self",true,false,java.util.List.of(a,deadB,c))==CommanderVictory.Result.ONGOING,"One elimination in multiplayer is not a match win");
  check(CommanderVictory.result("enemy",true,false,java.util.List.of(a,deadB))==CommanderVictory.Result.LOST,"Eliminated player loses");
  check(CommanderVictory.result("self",true,false,java.util.List.of(new CommanderVictory.Participant("self",true,true),deadB))==CommanderVictory.Result.DRAW,"All eliminated simultaneously is a draw");
  check(CommanderVictory.result("self",true,false,java.util.List.of(a,new CommanderVictory.Participant("enemy",false,false)))==CommanderVictory.Result.UNKNOWN,"Missing counter is not a win");
  check(CommanderVictory.result("self",false,false,java.util.List.of(a,deadB))==CommanderVictory.Result.WAITING,"Pregame is not victory");
  check(CommanderVictory.result("self",true,true,java.util.List.of(a,deadB))==CommanderVictory.Result.WAITING,"Starting roulette is not victory");
  check(CommanderVictory.result("self",true,false,java.util.List.of(a))==CommanderVictory.Result.WAITING,"Single-person setup is not a completed match");
  check(CommanderVictory.result("missing",true,false,java.util.List.of(a,deadB))==CommanderVictory.Result.UNKNOWN,"Self must be a participant");
  check(CommanderVictory.result("self",true,false,java.util.List.of(a,a))==CommanderVictory.Result.UNKNOWN,"Duplicate participants do not manufacture a result");
  var poisonPlayer=new CommanderRules.Turn();
  poisonPlayer.poison(9);check(!poisonPlayer.lost(),"Nine poison is not lethal");
  poisonPlayer.poison(1);check(poisonPlayer.lossReasons().contains("poison"),"Ten poison is lethal in Commander");
  var decked=new CommanderRules.Turn();
  check(!decked.lost(),"An empty library without a failed draw is not inherently a loss");
  decked.failedDraw();check(decked.lossReasons().contains("failed draw"),"Failed required draw loses");
  var splitCommander=new CommanderRules.Turn();
  splitCommander.lifeChange(100);
  splitCommander.combatDamageFromCommander("first",20);
  splitCommander.combatDamageFromCommander("second",20);
  check(!splitCommander.lost(),"Damage from different commanders is not combined");
  splitCommander.combatDamageFromCommander("first",1);
  splitCommander.lifeChange(100);
  check(splitCommander.lossReasons().contains("commander damage"),"Lifegain does not erase 21 damage from one commander");
  var zeroLife=new CommanderRules.Turn();zeroLife.lifeChange(-40);
  check(zeroLife.lossReasons().contains("life"),"Zero life is lethal");
  var concession=new CommanderRules.Turn();concession.concede();check(concession.lost(),"Conceded player is eliminated");
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
