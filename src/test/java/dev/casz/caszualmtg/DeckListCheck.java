package dev.casz.caszualmtg;
public final class DeckListCheck {
 static void check(boolean condition,String label){if(!condition)throw new AssertionError(label);}
 public static void main(String[] args){
  var p=DeckList.parse("\uFEFFCommander\n1 Ghave, Guru of Spores\nDeck\n4x Forest\n2 Forest\n1 Sol Ring (CMM) 396\nSideboard\n1 Plains\n");
  check(p.errors().isEmpty(),"valid import");check(p.lines().size()==3,"merge duplicate lines and exclude sideboard");check(p.lines().get(1).quantity()==6,"quantity accumulation");check(p.lines().get(2).name().equals("Sol Ring"),"printing suffix removed");check(p.lines().get(2).set().equals("CMM")&&p.lines().get(2).collector().equals("396"),"printing metadata preserved");check(p.lines().get(2).shopLine(1).equals("1 Sol Ring [CMM] 396"),"shop line includes printing");
  check(DeckList.parse("0 Forest").errors().size()==1,"zero rejected");check(!DeckList.parse("501 Forest").errors().isEmpty(),"oversized rejected");check(!DeckList.parse("499 Forest\n2 Plains").errors().isEmpty(),"total bounded");
  check(DeckList.parse("1 Fire // Ice").lines().getFirst().name().equals("Fire // Ice"),"double-faced names");check(DeckList.normalize("Urza’s Saga").equals(DeckList.normalize("Urza's Saga")),"apostrophes");
  check(DeckList.parse("# Comment\n\nSol Ring").lines().getFirst().quantity()==1,"name-only list");check(DeckList.parse("99999999999999999 Forest").errors().size()==1,"integer overflow rejected");System.out.println("PASS: decklist parser checks");
 }
}
