package dev.casz.mtg;
import java.util.*;
import java.util.regex.*;
public final class DeckList {
 public record Line(String name,int quantity) {}
 public record Parsed(List<Line> lines,List<String> errors) {}
 private static final Pattern ENTRY=Pattern.compile("^(\\d+)\\s*[xX]?\\s+(.+)$");
 public static Parsed parse(String text) {
  Map<String,Line> merged=new LinkedHashMap<>(); List<String> errors=new ArrayList<>(); int total=0,number=0;
  for(String raw:text.replace("\uFEFF", "").split("\\R")) {
   number++; String s=raw.trim(); if(s.isEmpty()||s.startsWith("#")||s.startsWith("//"))continue;
   if(Set.of("commander","deck","mainboard","sideboard","maybeboard").contains(s.toLowerCase(Locale.ROOT))) {if(s.equalsIgnoreCase("sideboard")||s.equalsIgnoreCase("maybeboard"))break; continue;}
   Matcher m=ENTRY.matcher(s); int qty=1; String name=s;
   if(m.matches()){try{qty=Integer.parseInt(m.group(1));}catch(NumberFormatException e){qty=-1;}name=m.group(2).trim();}
   // Arena/Moxfield printing suffixes; name-only matching across printings.
   name=name.replaceFirst("\\s+\\([A-Za-z0-9]+\\)\\s+\\S+(?:\\s+\\*F\\*)?$", "").replaceFirst("\\s+\\*F\\*$", "");
   if(qty<1||qty>500||name.isBlank()||name.length()>200||total+qty>500){errors.add("Line "+number+": invalid quantity/name or deck exceeds 500 cards");continue;}
   total+=qty;String k=normalize(name);Line old=merged.get(k);merged.put(k,new Line(name,qty+(old==null?0:old.quantity())));
  }
  return new Parsed(List.copyOf(merged.values()),List.copyOf(errors));
 }
 public static String normalize(String name){return name.trim().replace('’','\'').replaceAll("\\s+"," ").toLowerCase(Locale.ROOT);}
}
