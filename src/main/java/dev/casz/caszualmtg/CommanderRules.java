package dev.casz.caszualmtg;

import java.util.*;

/**
 * Conservative Commander rules subset used by the experimental golem.
 * Unknown cards/effects are deliberately not treated as legal actions.
 * Does not replace the Magic Comprehensive Rules interpreter.
 */
public final class CommanderRules {
 public static final int STARTING_LIFE=40, STARTING_HAND=7, DECK_SIZE=100, LETHAL_COMMANDER_DAMAGE=21;
 private CommanderRules(){}

 public record Card(String name, String type, int colorIdentity, boolean commanderEligible) {
  public Card {
   Objects.requireNonNull(name);
   Objects.requireNonNull(type);
  }
  public boolean basicLand(){
   return type.toLowerCase(Locale.ROOT).contains("basic")&&type.toLowerCase(Locale.ROOT).contains("land");
  }
 }
 public static List<String> validateDeck(List<Card> cards, List<Card> commanders){
  List<String> errors=new ArrayList<>();
  if(cards==null||cards.size()!=DECK_SIZE){errors.add("Commander decks must contain exactly 100 cards, including commander(s).");return errors;}
  if(commanders==null||commanders.isEmpty()||commanders.size()>2||commanders.stream().anyMatch(c->!c.commanderEligible()))
   errors.add("A legal commander (or an eligible partner pair) is required.");
  int colors=0;
  if(commanders!=null)for(Card commander:commanders)colors|=commander.colorIdentity();
  Map<String,Integer> seen=new HashMap<>();
  for(Card card:cards){
   if((card.colorIdentity()&~colors)!=0)errors.add("Outside commander color identity: "+card.name());
   if(!card.basicLand()&&seen.merge(card.name().toLowerCase(Locale.ROOT),1,Integer::sum)>1)
    errors.add("Duplicate nonbasic card: "+card.name());
  }
  if(commanders!=null)for(Card commander:commanders)
   if(cards.stream().noneMatch(c->c==commander))errors.add("Commander must count among the 100 cards: "+commander.name());
  return errors;
 }
 public enum Phase {UNTAP, UPKEEP, DRAW, PRECOMBAT_MAIN, BEGIN_COMBAT, DECLARE_ATTACKERS,
  DECLARE_BLOCKERS, COMBAT_DAMAGE, END_COMBAT, POSTCOMBAT_MAIN, END_STEP, CLEANUP}
 public static final class Turn {
  private Phase phase=Phase.UNTAP;
  private int landPlays;
  private final Map<String,Integer> commanderCasts=new HashMap<>();
  private final Map<String,Integer> commanderDamage=new HashMap<>();
  private int life=STARTING_LIFE;
  private int poison;
  private boolean failedDraw,conceded;
  public void poison(int amount){poison=Math.max(0,poison+amount);}
  public void failedDraw(){failedDraw=true;}
  public void concede(){conceded=true;}
  /** Empty library alone is not a loss; an attempted failed draw is. */
  public Set<String> lossReasons(){
   Set<String> reasons=new LinkedHashSet<>();
   if(life<=0)reasons.add("life");
   if(poison>=10)reasons.add("poison");
   if(failedDraw)reasons.add("failed draw");
   if(conceded)reasons.add("conceded");
   if(commanderDamage.values().stream().anyMatch(v->v>=LETHAL_COMMANDER_DAMAGE))reasons.add("commander damage");
   return Set.copyOf(reasons);
  }
  public Phase phase(){return phase;}
  public int life(){return life;}
  public int landPlays(){return landPlays;}
  public void begin(){landPlays=0;phase=Phase.UNTAP;}
  public void phase(Phase next){phase=Objects.requireNonNull(next);}
  public boolean canPlayLand(){
   return landPlays<1&&(phase==Phase.PRECOMBAT_MAIN||phase==Phase.POSTCOMBAT_MAIN);
  }
  public boolean playLand(){
   if(!canPlayLand())return false;
   landPlays++;return true;
  }
  public int commanderTax(String commanderId){return 2*commanderCasts.getOrDefault(commanderId,0);}
  public void commanderCast(String commanderId){commanderCasts.merge(commanderId,1,Integer::sum);}
  public void lifeChange(int delta){life+=delta;}
  /** The source key includes the commander identity, not its controller. */
  public boolean combatDamageFromCommander(String commanderId,int damage){
   if(damage<=0)return false;
   commanderDamage.merge(commanderId,damage,Integer::sum);
   life-=damage;
   return life<=0||commanderDamage.get(commanderId)>=LETHAL_COMMANDER_DAMAGE;
  }
  public boolean lost(){return !lossReasons().isEmpty();}
  public int commanderDamage(String commanderId){return commanderDamage.getOrDefault(commanderId,0);}
 }
}

