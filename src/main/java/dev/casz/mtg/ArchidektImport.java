package dev.casz.mtg;

import com.google.gson.*;
import java.net.*;
import java.net.http.*;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.*;
import java.util.concurrent.CompletableFuture;
import java.util.regex.*;

/** Imports the public main deck from an Archidekt deck URL. */
public final class ArchidektImport {
 private static final Pattern DECK_URL=Pattern.compile("^https?://(?:www\\.)?archidekt\\.com/decks/(\\d+)(?:/[^?#]*)?(?:[?#].*)?$",Pattern.CASE_INSENSITIVE);
 private static final HttpClient HTTP=HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(8)).followRedirects(HttpClient.Redirect.NORMAL).build();
 private ArchidektImport(){}

 public record Result(String deckName,String text,int entries,int cards){}

 public static long deckId(String url){
  Matcher m=DECK_URL.matcher(url==null?"":url.trim());
  if(!m.matches())throw new IllegalArgumentException("Enter an Archidekt deck URL, for example https://archidekt.com/decks/123456/name");
  try{return Long.parseLong(m.group(1));}catch(NumberFormatException e){throw new IllegalArgumentException("Invalid Archidekt deck ID.");}
 }

 public static CompletableFuture<Result> fetch(String url){
  long id=deckId(url);
  HttpRequest request=HttpRequest.newBuilder(URI.create("https://archidekt.com/api/decks/"+id+"/"))
   .timeout(Duration.ofSeconds(20)).header("Accept","application/json").header("User-Agent","MTGCompanion/0.5.0 (Minecraft MTGCard addon)").GET().build();
  return HTTP.sendAsync(request,HttpResponse.BodyHandlers.ofByteArray()).thenApply(response->{
   if(response.statusCode()==401||response.statusCode()==403)throw new CompletionException(new IllegalArgumentException("That Archidekt deck is not publicly accessible."));
   if(response.statusCode()!=200)throw new CompletionException(new IllegalArgumentException("Archidekt returned HTTP "+response.statusCode()+"."));
   byte[] bytes=response.body();if(bytes.length>8*1024*1024)throw new CompletionException(new IllegalArgumentException("Archidekt deck response is too large."));
   try{return parse(new String(bytes,StandardCharsets.UTF_8));}
   catch(RuntimeException e){throw new CompletionException(e);}
  });
 }

 static Result parse(String json){
  JsonObject root=JsonParser.parseString(json).getAsJsonObject();
  String deckName=string(root,"name","");
  Set<String> included=new HashSet<>();
  JsonArray categories=array(root,"categories");
  if(categories!=null)for(JsonElement el:categories)if(el.isJsonObject()){
   JsonObject o=el.getAsJsonObject();String name=string(o,"name","").trim();
   boolean in=!o.has("includedInDeck")||!o.get("includedInDeck").isJsonPrimitive()||o.get("includedInDeck").getAsBoolean();
   if(in&&!name.isBlank())included.add(name.toLowerCase(Locale.ROOT));
  }

  LinkedHashMap<String,DeckList.Line> merged=new LinkedHashMap<>();
  JsonArray cards=array(root,"cards");
  if(cards==null)throw new IllegalArgumentException("Archidekt deck contains no card list.");
  int total=0;
  for(JsonElement el:cards){
   if(!el.isJsonObject())continue;JsonObject entry=el.getAsJsonObject();
   List<String> cats=categories(entry.get("categories"));
   if(cats.stream().anyMatch(ArchidektImport::excluded))continue;
   if(!included.isEmpty()&&!cats.isEmpty()&&cats.stream().noneMatch(c->included.contains(c.toLowerCase(Locale.ROOT))))continue;
   int qty=integer(entry,"quantity",1);if(qty<1||qty>500)continue;
   JsonObject card=object(entry,"card"),oracle=card==null?null:object(card,"oracleCard");
   String name=oracle==null?"":string(oracle,"name","");
   if(name.isBlank()&&card!=null)name=string(card,"displayName","");
   if(name.isBlank())continue;
   String collector=card==null?"":string(card,"collectorNumber","");
   JsonObject edition=card==null?null:object(card,"edition");
   String set=edition==null?"":first(edition,"editioncode","editionCode","code");
   String key=DeckList.normalize(name)+(set.isBlank()?"":"\u0000"+set.toLowerCase(Locale.ROOT)+"\u0000"+collector.toLowerCase(Locale.ROOT));
   DeckList.Line old=merged.get(key);merged.put(key,new DeckList.Line(name,qty+(old==null?0:old.quantity()),set,collector));total+=qty;
   if(total>500)throw new IllegalArgumentException("Archidekt main deck exceeds the 500-card importer limit.");
  }
  if(merged.isEmpty())throw new IllegalArgumentException("No main-deck cards were found. Sideboard and Maybeboard are intentionally ignored.");
  StringBuilder text=new StringBuilder();
  for(DeckList.Line line:merged.values())text.append(line.quantity()).append(' ').append(line.name()).append(line.hasPrinting()?" ("+line.set().toUpperCase(Locale.ROOT)+") "+line.collector():"").append('\n');
  return new Result(deckName,text.toString(),merged.size(),total);
 }

 static boolean excluded(String name){String n=name.trim().toLowerCase(Locale.ROOT).replace(" ","");return n.equals("sideboard")||n.equals("maybeboard");}
 static List<String> categories(JsonElement el){
  if(el==null||!el.isJsonArray())return List.of();List<String> out=new ArrayList<>();
  for(JsonElement c:el.getAsJsonArray()){if(c.isJsonPrimitive())out.add(c.getAsString());else if(c.isJsonObject()){String n=string(c.getAsJsonObject(),"name","");if(!n.isBlank())out.add(n);}}
  return out;
 }
 static JsonObject object(JsonObject o,String key){JsonElement e=o==null?null:o.get(key);return e!=null&&e.isJsonObject()?e.getAsJsonObject():null;}
 static JsonArray array(JsonObject o,String key){JsonElement e=o==null?null:o.get(key);return e!=null&&e.isJsonArray()?e.getAsJsonArray():null;}
 static String string(JsonObject o,String key,String fallback){JsonElement e=o==null?null:o.get(key);return e!=null&&e.isJsonPrimitive()?e.getAsString():fallback;}
 static int integer(JsonObject o,String key,int fallback){JsonElement e=o==null?null:o.get(key);try{return e!=null&&e.isJsonPrimitive()?e.getAsInt():fallback;}catch(Exception ex){return fallback;}}
 static String first(JsonObject o,String... keys){for(String k:keys){String s=string(o,k,"");if(!s.isBlank())return s;}return "";}
}
