package dev.casz.caszualmtg;
import java.util.*;
import java.util.regex.*;
/** Whole-text grammar for untargeted draw/lifegain. Additional clauses fail closed. */
public final class CommanderSimpleSpells {
 private CommanderSimpleSpells(){}
 public record Effect(int draw,int life){}
 private static int number(String s){return switch(s){case "a","one"->1;case "two"->2;case "three"->3;case "four"->4;case "five"->5;case "six"->6;case "seven"->7;default->Integer.parseInt(s);};}
 public static Optional<Effect> parse(String type,String oracle){
  String t=Objects.requireNonNullElse(type,"").toLowerCase(Locale.ROOT);
  if(!(t.equals("instant")||t.equals("sorcery")))return Optional.empty();
  String text=CommanderOracle.rules(oracle).toLowerCase(Locale.ROOT).strip();
  Matcher draw=Pattern.compile("draw (a|one|two|three|four|five|six|seven|[1-7]) cards?\\.").matcher(text);
  if(draw.matches())return Optional.of(new Effect(number(draw.group(1)),0));
  Matcher life=Pattern.compile("you gain (one|two|three|four|five|six|seven|[1-9]|10) life\\.").matcher(text);
  if(life.matches())return Optional.of(new Effect(0,number(life.group(1))));
  return Optional.empty();
 }
}
