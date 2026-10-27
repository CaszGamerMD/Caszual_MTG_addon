package dev.casz.caszualmtg;

import java.util.*;

/** Win/loss knowledge for the limited free-for-all pilot, without card-specific replacements. */
public final class CommanderVictory {
 private CommanderVictory(){}
 public enum Result {WAITING, UNKNOWN, ONGOING, WON, LOST, DRAW}
 public record Participant(String id,boolean eliminated,boolean known){}
 /** A missing/unloaded participant is never presumed eliminated. */
 public static Result result(String self,boolean started,boolean rolling,List<Participant> players){
  if(!started||rolling||players.size()<2)return Result.WAITING;
  if(players.stream().map(Participant::id).distinct().count()!=players.size())return Result.UNKNOWN;
  var own=players.stream().filter(p->p.id().equals(self)).findFirst();
  if(own.isEmpty())return Result.UNKNOWN;
  if(players.stream().anyMatch(p->!p.known()))return Result.UNKNOWN;
  long living=players.stream().filter(p->!p.eliminated()).count();
  if(living==0)return Result.DRAW;
  if(own.get().eliminated())return Result.LOST;
  return living==1?Result.WON:Result.ONGOING;
 }
 /** Worst legal single-blocker response, including the option not to block.
  * Unknown creatures prevent a claim of forced lethal. No hidden-card prediction.
  */
 public record Attack(int minimumDamage,boolean lethal,boolean mayDie,int openDamage)
       implements Comparable<Attack>{
  @Override public int compareTo(Attack other){
   int c=Boolean.compare(lethal,other.lethal);if(c!=0)return c;
   c=Integer.compare(minimumDamage,other.minimumDamage);if(c!=0)return c;
   c=Boolean.compare(other.mayDie,mayDie);if(c!=0)return c;
   return Integer.compare(openDamage,other.openDamage);
  }
 }
 public static Attack attack(CommanderSimpleCards.Traits attacker,
     List<CommanderSimpleCards.Traits> blockers,boolean unknownBlocker,int ownLife,int enemyLife){
  var open=CommanderSimpleCards.combat(attacker,null,ownLife,enemyLife);
  int minimum=open.playerDamage();
  boolean lethal=enemyLife+open.blockerLifeGain()-open.playerDamage()<=0;
  boolean dies=open.attackerDies();
  for(var blocker:blockers){
   if(!CommanderSimpleCards.canBlock(blocker,attacker,false))continue;
   var damage=CommanderSimpleCards.combat(attacker,blocker,ownLife,enemyLife);
   minimum=Math.min(minimum,Math.max(0,damage.playerDamage()-damage.blockerLifeGain()));
   lethal&=enemyLife+damage.blockerLifeGain()-damage.playerDamage()<=0;
   dies|=damage.attackerDies();
  }
  if(unknownBlocker){minimum=0;lethal=false;dies=true;}
  return new Attack(minimum,lethal,dies,open.playerDamage());
 }
}
