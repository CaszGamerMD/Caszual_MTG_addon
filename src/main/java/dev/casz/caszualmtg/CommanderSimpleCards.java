package dev.casz.caszualmtg;

import java.util.*;

/**
 * Explicit supported subset for AI card actions.
 * Missing rules support is never interpreted as a blank card effect.
 */
public final class CommanderSimpleCards {
 private static final Set<String> PASSIVE=Set.of("flying","reach","haste","vigilance","defender","deathtouch","indestructible","trample","lifelink","first strike","double strike","shadow","skulk","horsemanship");
 private CommanderSimpleCards(){}
 public record Traits(int power,int toughness,Set<String> keywords){
  public boolean has(String keyword){return keywords.contains(keyword);}
 }
 public static Optional<Traits> creature(String typeLine,String oracle,String power,String toughness){
  String type=Objects.requireNonNullElse(typeLine,"").toLowerCase(Locale.ROOT);
  if(!type.contains("creature")||type.contains("land")||type.contains("token")||type.contains("battle"))
   return Optional.empty();
  int p,t;
  try {
   p=Integer.parseInt(Objects.requireNonNullElse(power,""));
   t=Integer.parseInt(Objects.requireNonNullElse(toughness,""));
  }catch(NumberFormatException e){return Optional.empty();}
  if(p<0||t<1||p>1000||t>1000)return Optional.empty();
  Set<String> keywords=new HashSet<>();
  String text=CommanderOracle.rules(oracle);
  if(!text.isBlank()){
   // Only completely-understood, passive keywords. No ETB triggers,
   // activated abilities, modifiers, reminder text, or conditional choices.
   for(String raw:text.split("[,\\n]")){
    String line=raw.strip().toLowerCase(Locale.ROOT).replaceAll("\\.$","").strip();
    if(line.isBlank())continue;
    if(!PASSIVE.contains(line))return Optional.empty();
    keywords.add(line);
   }
  }
  return Optional.of(new Traits(p,t,Set.copyOf(keywords)));
 }
 public static boolean canAttack(Traits attacker,boolean fresh,boolean tapped){
  return attacker!=null&&!tapped&&!attacker.has("defender")&&(!fresh||attacker.has("haste"));
 }
 public static boolean canBlock(Traits blocker,Traits attacker,boolean tapped){
  return blocker!=null&&attacker!=null&&!tapped&&
    (!attacker.has("flying")||blocker.has("flying")||blocker.has("reach"))&&
    (attacker.has("shadow")==blocker.has("shadow"))&&
    (!attacker.has("horsemanship")||blocker.has("horsemanship"))&&
    (!attacker.has("skulk")||blocker.power()<=attacker.power());
 }
 public record Damage(int playerDamage,boolean attackerDies,boolean blockerDies,boolean tapAttacker,
                      int attackerLifeGain,int blockerLifeGain){}
 public static Damage combat(Traits attacker,Traits blocker){
  return combat(attacker,blocker,1_000_000,1_000_000);
 }
 private static boolean early(Traits t){return t!=null&&(t.has("first strike")||t.has("double strike"));}
 private static boolean deals(Traits t,boolean first){return first?early(t):!early(t)||t.has("double strike");}
 /** Resolve each damage step and state-based destruction before the next.
  * Life totals stop a later damage step when a player has already lost.
  * No abilities may change between steps in this limited resolver.
  */
 public static Damage combat(Traits attacker,Traits blocker,int attackerLife,int defenderLife){
  if(attacker==null)throw new IllegalArgumentException("Attacker required");
  boolean aliveA=true,aliveB=blocker!=null;
  int markedA=0,markedB=0,playerDamage=0,gainA=0,gainB=0;
  int begin=early(attacker)||early(blocker)?0:1;
  for(int step=begin;step<=1;step++){
   boolean first=step==0;
   boolean hitA=aliveA&&deals(attacker,first);
   boolean hitB=aliveB&&deals(blocker,first);
   int toA=hitB?Math.max(0,blocker.power()):0;
   int toB=0,toPlayer=0;
   if(hitA){
    int power=Math.max(0,attacker.power());
    if(aliveB){
     int lethal=Math.max(0,blocker.toughness()-markedB);
     if(attacker.has("deathtouch")&&lethal>0)lethal=1;
     toB=attacker.has("trample")?Math.min(power,lethal):power;
     if(attacker.has("trample"))toPlayer=power-toB;
    }else if(blocker==null||attacker.has("trample"))toPlayer=power;
    // A blocked creature remains blocked even if its blocker died in the first step.
   }
   int thisGainA=attacker.has("lifelink")?toB+toPlayer:0;
   int thisGainB=blocker!=null&&blocker.has("lifelink")?toA:0;
   markedA+=toA;markedB+=toB;playerDamage+=toPlayer;
   gainA+=thisGainA;gainB+=thisGainB;
   // Both creatures deal their eligible damage before simultaneous deaths.
   if(toA>0&&!attacker.has("indestructible")
       &&(markedA>=attacker.toughness()||blocker.has("deathtouch")))aliveA=false;
   if(toB>0&&!blocker.has("indestructible")
       &&(markedB>=blocker.toughness()||attacker.has("deathtouch")))aliveB=false;
   attackerLife+=thisGainA;defenderLife+=thisGainB-toPlayer;
   if(attackerLife<=0||defenderLife<=0)break;
  }
  return new Damage(playerDamage,!aliveA,blocker!=null&&!aliveB,!attacker.has("vigilance"),gainA,gainB);
 }
}
