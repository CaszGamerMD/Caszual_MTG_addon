package dev.casz.caszualmtg;

import java.util.*;
import java.util.regex.*;

/**
 * Exact one-mana-source planner for the intentionally small subset of MTG
 * abilities understood by the Commander Golem. Unsupported symbols/abilities
 * fail closed instead of producing free mana or skipping costs.
 */
public final class CommanderMana {
 private CommanderMana(){}
 public record Cost(int generic,int white,int blue,int black,int red,int green,int colorless) {
  public int total(){return generic+white+blue+black+red+green+colorless;}
  public Cost taxed(int tax){return new Cost(generic+tax,white,blue,black,red,green,colorless);}
  public int requirement(int index){return switch(index){
   case 0->white;case 1->blue;case 2->black;case 3->red;case 4->green;case 5->colorless;
   default->throw new IllegalArgumentException("Unknown mana index");
  };}
 }
 public record Source(String id,int manaMask){
  public Source{Objects.requireNonNull(id);if(manaMask<=0||manaMask>63)throw new IllegalArgumentException("Mana mask must be between 1 and 63");}
 }
 // 1=W 2=U 4=B 8=R 16=G 32=C. Each source adds EXACTLY one mana.
 public static Optional<Cost> parse(String raw){
  if(raw==null)return Optional.empty();
  String s=raw.trim().toUpperCase(Locale.ROOT);
  if(s.isBlank())return Optional.empty(); // An absent mana cost is not {0}.
  Matcher m=Pattern.compile("\\{([^{}]+)}").matcher(s);
  int[] counts=new int[6];int generic=0,last=0;
  while(m.find()){
   if(!s.substring(last,m.start()).isBlank())return Optional.empty();
   last=m.end();String symbol=m.group(1);
   int type=switch(symbol){case "W"->0;case "U"->1;case "B"->2;case "R"->3;case "G"->4;case "C"->5;default->-1;};
   if(type>=0){counts[type]++;continue;}
   if(!symbol.matches("[0-9]{1,2}"))return Optional.empty(); // X, hybrid, phyrexian, snow etc.
   generic+=Integer.parseInt(symbol);
   if(generic>99)return Optional.empty();
  }
  if(!s.substring(last).isBlank()||last==0)return Optional.empty();
  return Optional.of(new Cost(generic,counts[0],counts[1],counts[2],counts[3],counts[4],counts[5]));
 }
 /** Only deterministic, unconditional one-mana land abilities can be automated.
  * Recognize the common ETB-tapped basic duals without ignoring their drawback. */
 public record Land(int mask,boolean entersTapped){}
 public static Optional<Land> land(String typeLine,String oracle){return land("",typeLine,oracle);}
 public static Optional<Land> land(String name,String typeLine,String oracle){
  String type=Objects.requireNonNullElse(typeLine,"").toLowerCase(Locale.ROOT);
  if(!type.contains("land")||type.contains("creature")||type.contains("battle"))
   return Optional.empty();
  String text=CommanderOracle.rules(oracle).trim().toUpperCase(Locale.ROOT).replace("\r","");
  String self=Objects.requireNonNullElse(name,"").toUpperCase(Locale.ROOT);
  if(!self.isBlank()&&text.startsWith(self+" ENTERS"))
   text="THIS LAND"+text.substring(self.length());
  boolean tapped=false;
  if(text.startsWith("THIS LAND ENTERS TAPPED.\n")){
   tapped=true;text=text.substring("THIS LAND ENTERS TAPPED.\n".length()).trim();
  }else if(text.startsWith("THIS LAND ENTERS THE BATTLEFIELD TAPPED.\n")){
   tapped=true;text=text.substring("THIS LAND ENTERS THE BATTLEFIELD TAPPED.\n".length()).trim();
  }
  // Any further conditional ability, ETB trigger or extra cost fails closed.
  if(text.isBlank()){
   int mask=0;
   if(type.contains("plains"))mask|=1;
   if(type.contains("island"))mask|=2;
   if(type.contains("swamp"))mask|=4;
   if(type.contains("mountain"))mask|=8;
   if(type.contains("forest"))mask|=16;
   if(type.contains("wastes"))mask|=32;
   return mask==0?Optional.empty():Optional.of(new Land(mask,tapped));
  }
  if(!text.startsWith("{T}: ADD "))return Optional.empty();
  String add=text.substring("{T}: ADD ".length()).replace(".","").trim();
  int mask=0;
  if(add.matches("\\{[WUBRGC]}"))mask=bit(add.charAt(1));
  else if(add.equals("ONE MANA OF ANY COLOR"))mask=31;
  else if(add.equals("ONE MANA OF ANY TYPE"))mask=63;
  else if(add.matches("\\{[WUBRGC]} OR \\{[WUBRGC]}")){
   mask=bit(add.charAt(1))|bit(add.charAt(8));
  }
  return mask==0?Optional.empty():Optional.of(new Land(mask,tapped));
 }
 /** Recognize basic lands and extremely simple, unconditional tap-for-one abilities. */
 public static int production(String name,String typeLine,String oracle){
  return land(name,typeLine,oracle).map(Land::mask).orElse(0);
 }
 private static int bit(char c){return switch(c){case 'W'->1;case 'U'->2;case 'B'->4;case 'R'->8;case 'G'->16;case 'C'->32;default->0;};}
 /** Source IDs are unique battlefield card ids. Plan is a deterministic list of ids to tap. */
 public static Optional<List<String>> pay(Cost cost,List<Source> available){
  if(cost==null||available==null||cost.total()>available.size())return Optional.empty();
  if(cost.total()==0)return Optional.of(List.of());
  boolean[] used=new boolean[available.size()];
  List<String> chosen=new ArrayList<>();
  if(!solve(0,cost,available,used,chosen))return Optional.empty();
  return Optional.of(List.copyOf(chosen));
 }
 private static boolean solve(int step,Cost cost,List<Source> sources,boolean[] used,List<String> out){
  // Most constrained color first minimizes search for multicolor costs.
  final int[] order={5,0,1,2,3,4};
  int needed=0;
  for(int type:order)needed+=cost.requirement(type);
  if(step>=needed){
   int generic=cost.generic();
   for(int i=0;i<sources.size()&&generic>0;i++)if(!used[i]){
    out.add(sources.get(i).id());generic--;
   }
   if(generic==0)return true;
   while(out.size()>step)out.remove(out.size()-1);
   return false;
  }
  int rem=step,type=-1;
  for(int index:order){int n=cost.requirement(index);if(rem<n){type=index;break;}rem-=n;}
  int bit=1<<type;
  for(int i=0;i<sources.size();i++){
   Source source=sources.get(i);
   if(used[i]||(source.manaMask()&bit)==0)continue;
   used[i]=true;out.add(source.id());
   if(solve(step+1,cost,sources,used,out))return true;
   out.remove(out.size()-1);used[i]=false;
  }
  return false;
 }
}

