package dev.casz.caszualmtg;

import java.util.*;

/**
 * Explicit supported subset for AI card actions.
 * Missing rules support is never interpreted as a blank card effect.
 */
public final class CommanderSimpleCards {
 private static final Set<String> PASSIVE=Set.of("flying","reach","haste","vigilance","defender","deathtouch","indestructible","trample","lifelink");
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
    (!attacker.has("flying")||blocker.has("flying")||blocker.has("reach"));
 }
 public record Damage(int playerDamage,boolean attackerDies,boolean blockerDies,boolean tapAttacker,
                      int attackerLifeGain,int blockerLifeGain){}
 public static Damage combat(Traits attacker,Traits blocker){
  if(attacker==null)throw new IllegalArgumentException("Attacker required");
  int attack=Math.max(0,attacker.power());
  boolean tap=!attacker.has("vigilance");
  if(blocker==null)return new Damage(attack,false,false,tap,attacker.has("lifelink")?attack:0,0);
  int block=Math.max(0,blocker.power());
  // Damage is simultaneous. Deathtouch requires positive damage;
  // indestructible prevents destruction but does not prevent damage.
  boolean attackerDies=!attacker.has("indestructible")&&block>0
      &&(block>=attacker.toughness()||blocker.has("deathtouch"));
  boolean blockerDies=!blocker.has("indestructible")&&attack>0
      &&(attack>=blocker.toughness()||attacker.has("deathtouch"));
  int lethal=attacker.has("deathtouch")?1:blocker.toughness();
  // Trample assignment still requires lethal damage to an indestructible blocker.
  int spill=attacker.has("trample")?Math.max(0,attack-lethal):0;
  return new Damage(spill,attackerDies,blockerDies,tap,
      attacker.has("lifelink")?attack:0,blocker.has("lifelink")?block:0);
 }
}
