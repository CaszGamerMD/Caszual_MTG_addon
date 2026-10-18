package dev.casz.caszualmtg;

import java.util.*;

public final class CommanderManaCheck {
 private static void ok(boolean b,String why){if(!b)throw new AssertionError(why);}
 public static void main(String[] args){
  var c=CommanderMana.parse("{2}{W}{U}").orElseThrow();
  ok(c.total()==4&&c.generic()==2&&c.white()==1&&c.blue()==1,"parse colored cost");
  ok(CommanderMana.parse("").isPresent(),"zero mana cost");
  ok(CommanderMana.parse("{X}{G}").isEmpty(),"X cannot be guessed");
  ok(CommanderMana.parse("{W/U}").isEmpty(),"hybrid is unsupported");
  ok(CommanderMana.parse("{2}{G/P}").isEmpty(),"Phyrexian must be rejected");
  ok(CommanderMana.parse("{S}").isEmpty(),"snow mana must be rejected");
  ok(CommanderMana.parse("two mana").isEmpty(),"freeform text must be rejected");
  ok(CommanderMana.production("Plains","Basic Land — Plains","")==1,"basic white mana");
  ok(CommanderMana.production("Breeding Pool","Land — Forest Island","")==18,"dual basic types");
  ok(CommanderMana.production("Island","Basic Land — Island","{T}: Add {U}.")==2,"oracle tap blue mana");
  ok(CommanderMana.production("Any City","Land","{T}: Add one mana of any color.")==31,"one chosen color");
  ok(CommanderMana.production("Risky","Land","{T}, Pay 1 life: Add {B}.")==0,"extra costs unsupported");
  ok(CommanderMana.production("Ancient Tomb","Land","{T}: Add {C}{C}.")==0,"two-mana source unsupported");
  ok(CommanderMana.production("Tap Land","Land","Enters tapped.\n{T}: Add {U}.")==0,"ETB text must not be assumed");
  var sources=List.of(new CommanderMana.Source("any",3),
    new CommanderMana.Source("white",1),new CommanderMana.Source("blue",2),
    new CommanderMana.Source("none",32),new CommanderMana.Source("green",16));
  var plan=CommanderMana.pay(c,sources).orElseThrow();
  ok(plan.size()==4&&new HashSet<>(plan).size()==4,"unique sources");
  ok(plan.contains("white")||plan.contains("any"),"must pay white");
  ok(CommanderMana.pay(CommanderMana.parse("{W}{W}{U}").orElseThrow(),
    List.of(new CommanderMana.Source("only",3),new CommanderMana.Source("blue",2),
      new CommanderMana.Source("colorless",32))).isEmpty(),"do not double-spend flexible mana");
  ok(CommanderMana.pay(CommanderMana.parse("{C}{W}").orElseThrow(),
    List.of(new CommanderMana.Source("w",1),new CommanderMana.Source("c",32))).isPresent(),
    "colorless symbol is different from generic");
  ok(CommanderMana.pay(c.taxed(2),sources).isEmpty(),"commander tax must increase cost");
  ok(CommanderMana.pay(CommanderMana.parse("{0}").orElseThrow(),List.of()).orElseThrow().isEmpty(),
    "zero cost should pay no mana");
  System.out.println("Commander mana check passed.");
 }
}
