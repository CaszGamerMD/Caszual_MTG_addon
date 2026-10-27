package dev.casz.caszualmtg.training;

import dev.casz.caszualmtg.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.*;

/** Local subprocess protocol. Reuses the production rules subset; never evaluates code. */
public final class RulesBridge {
 private static String quote(String s){
  StringBuilder b=new StringBuilder("\"");
  for(char c:s.toCharArray())switch(c){
   case '"'->b.append("\\\"");case '\\'->b.append("\\\\");
   case '\n'->b.append("\\n");case '\r'->b.append("\\r");case '\t'->b.append("\\t");
   default->{if(c<32)b.append(String.format("\\u%04x",(int)c));else b.append(c);}
  }
  return b.append('"').toString();
 }
 private static CommanderSimpleCards.Traits traits(String s){
  String[] p=s.split(";",-1);
  return new CommanderSimpleCards.Traits(Integer.parseInt(p[0]),Integer.parseInt(p[1]),
   p[2].isBlank()?Set.of():Set.copyOf(Arrays.asList(p[2].split(","))));
 }
 private static String audit(String[] p){
  String name=p[1],type=p[2],text=p[3],cost=p[4];
  if(type.toLowerCase(Locale.ROOT).contains("land")){
   var land=CommanderMana.land(name,type,text);
   if(land.isEmpty())return "{\"kind\":\"unsupported\",\"reason\":\"land abilities or conditions\"}";
   return "{\"kind\":\"land\",\"mask\":"+land.get().mask()+",\"tapped\":"+land.get().entersTapped()+"}";
  }
  var payment=CommanderMana.parse(cost);
  if(payment.isEmpty())return "{\"kind\":\"unsupported\",\"reason\":\"mana cost\"}";
  var creature=CommanderSimpleCards.creature(type,text,p[5],p[6]);
  if(creature.isPresent()){
   var t=creature.get();var keywords=new ArrayList<>(t.keywords());Collections.sort(keywords);
   return "{\"kind\":\"creature\",\"power\":"+t.power()+",\"toughness\":"+t.toughness()
    +",\"traits\":"+quote(t.power()+";"+t.toughness()+";"+String.join(",",keywords))+"}";
  }
  var spell=CommanderSimpleSpells.parse(type,text);
  if(spell.isPresent())return "{\"kind\":\"spell\",\"draw\":"+spell.get().draw()+",\"life\":"+spell.get().life()+"}";
  return "{\"kind\":\"unsupported\",\"reason\":\"card abilities, type, or variable statistics\"}";
 }
 private static String run(String[] p){
  switch(p[0]){
   case "audit":return audit(p);
   case "pay":{
    var cost=CommanderMana.parse(p[1]);List<CommanderMana.Source> sources=new ArrayList<>();
    for(int i=2;i<p.length;i++){String[] s=p[i].split(":");sources.add(new CommanderMana.Source(s[0],Integer.parseInt(s[1])));}
    var plan=CommanderMana.pay(cost.orElse(null),sources);
    if(plan.isEmpty())return "{\"paid\":false}";
    return "{\"paid\":true,\"sources\":["+String.join(",",plan.get().stream().map(RulesBridge::quote).toList())+"]}";
   }
   case "combat":{
    var a=traits(p[1]);var b=p[2].isBlank()?null:traits(p[2]);
    if(b!=null&&!CommanderSimpleCards.canBlock(b,a,false))return "{\"legal\":false}";
    var d=CommanderSimpleCards.combat(a,b,Integer.parseInt(p[3]),Integer.parseInt(p[4]));
    return "{\"legal\":true,\"damage\":"+d.playerDamage()+",\"attackerDies\":"+d.attackerDies()
     +",\"blockerDies\":"+d.blockerDies()+",\"tap\":"+d.tapAttacker()
     +",\"gainA\":"+d.attackerLifeGain()+",\"gainB\":"+d.blockerLifeGain()+"}";
   }
   default:throw new IllegalArgumentException("Unknown bridge command");
  }
 }
 public static void main(String[] args)throws Exception{
  try(var in=new BufferedReader(new InputStreamReader(System.in,StandardCharsets.UTF_8))){
   for(String line;(line=in.readLine())!=null;){
    try{
     String[] p=line.split("\t",-1);
     for(int i=0;i<p.length;i++)p[i]=new String(Base64.getDecoder().decode(p[i]),StandardCharsets.UTF_8);
     System.out.println(run(p));
    }catch(Exception e){System.out.println("{\"error\":"+quote(e.toString())+"}");}
   }
  }
 }
}
