package dev.casz.mtg;

import com.google.gson.*;
import com.google.gson.reflect.TypeToken;
import com.spider.mtgcard.content.pack.cache.*;
import com.spider.mtgcard.util.StackData;
import com.spider.mtgcard.util.TcgCardMeta;
import net.minecraft.world.item.ItemStack;
import java.net.*;
import java.net.http.*;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.*;
import java.util.concurrent.CompletableFuture;
import java.util.regex.Pattern;

/** Free land/token vending catalogue, independent of owned collection counts. */
public final class Catalogue {
 static final Gson GSON=new GsonBuilder().setFieldNamingPolicy(FieldNamingPolicy.LOWER_CASE_WITH_UNDERSCORES).create();
 static final Pattern TOKEN=Pattern.compile("\\bToken\\b",Pattern.CASE_INSENSITIVE), LAND=Pattern.compile("\\bLand\\b",Pattern.CASE_INSENSITIVE);
 static final String MANA="WUBRGC", MANA_TAG="mtgcompanion_produced_mana";
 static final HttpClient HTTP=HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(8)).build();
 public record Hit(ScryfallModels.Card model,int mana){}
 public record Page(List<Hit> cards,int total,boolean hasMore){}
 record Cached(JsonObject json,long time){}
 static final Map<String,Cached> CACHE=new LinkedHashMap<>();
 public static boolean isToken(String line){return line!=null&&TOKEN.matcher(line.split("[—–]",2)[0]).find();}
 public static boolean isLand(String line){return line!=null&&LAND.matcher(line.split("[—–]",2)[0]).find();}
 static String quote(String text){return "\""+text.replace("\\","\\\\").replace("\"","\\\"")+"\"";}
 public static String query(int kind,String text,int mana){return query(kind,text,mana,"","");}
 public static String query(int kind,String text,int mana,String oracle,String stats){String q=text.trim();if(!q.isBlank()&&!q.contains(":"))q="name:"+quote(q);String base=kind==0?"t:land legal:commander":"t:token";if(!q.isBlank())base+=" ("+q+")";
  if(kind==0&&(mana&63)!=0){List<String> parts=new ArrayList<>();String colors="";for(int i=0;i<6;i++)if((mana&(1<<i))!=0){parts.add("produces:"+MANA.charAt(i));if(i<5)colors+=MANA.charAt(i);}base+=" id<="+(colors.isEmpty()?"c":colors)+" ("+String.join(" or ",parts)+")";for(int i=0;i<5;i++)if((mana&(1<<i))==0)base+=" -produces:"+MANA.charAt(i);}
  if(kind==1){if(!oracle.isBlank())base+=" o:"+quote(oracle.trim());String[] pt=stats(stats);if(pt!=null)base+=" pow="+pt[0]+" tou="+pt[1];}return base;
 }
 public static String[] stats(String text){if(text.isBlank())return null;var m=Pattern.compile("^\\s*(\\d{1,3})\\s*/\\s*(\\d{1,3})\\s*$").matcher(text);if(!m.matches())throw new IllegalArgumentException("Power/toughness must be numbers, for example 1/1.");return new String[]{Integer.toString(Integer.parseInt(m.group(1))),Integer.toString(Integer.parseInt(m.group(2)))};}
 public static boolean matchesToken(ItemStack card,String oracle,String stats){var meta=TcgCardMeta.read(card);String[] pt=stats(stats);return isToken(meta.typeLine())&&(oracle.isBlank()||meta.oracleText().toLowerCase(Locale.ROOT).contains(oracle.trim().toLowerCase(Locale.ROOT)))&&(pt==null||meta.power().equals(pt[0])&&meta.toughness().equals(pt[1]));}
 public static boolean acceptsLand(int produced,int identity,boolean legal,int selected){if(!legal)return false;if((selected&63)==0)return true;int colored=selected&31;return (identity&~colored)==0&&((produced&31)&~colored)==0&&(produced&selected)!=0;}
 public static void metadata(ItemStack card,ScryfallModels.Card model,int mana){var tag=StackData.readCustom(card);tag.putInt(MANA_TAG,mana&63);tag.putString("mtgcompanion_oracle_id",model.oracleId==null?"":model.oracleId);StackData.writeCustom(card,tag);}
 public static String artworkQuery(int kind,ItemStack card){String oracle=StackData.readCustom(card).getString("mtgcompanion_oracle_id").orElse("");if(oracle.matches("[0-9a-fA-F-]{36}"))return (kind==0?"t:land legal:commander":"t:token")+" oracleid:"+oracle;var meta=TcgCardMeta.read(card);return (kind==0?"t:land legal:commander":"t:token")+" !"+quote(meta.name());}
 public static int manaMask(JsonObject card){int mask=0;var arr=card.getAsJsonArray("produced_mana");if(arr!=null)for(var e:arr){int i=MANA.indexOf(e.getAsString());if(i>=0)mask|=1<<i;}return mask;}
 public static void setMana(ItemStack card,int mask){var tag=StackData.readCustom(card);tag.putInt(MANA_TAG,mask&63);StackData.writeCustom(card,tag);}
 public static boolean matchesMana(ItemStack card,int mask){var meta=TcgCardMeta.read(card);int identity=0;for(String c:meta.colorIdentity()){int i=MANA.indexOf(c.toUpperCase(Locale.ROOT));if(i>=0&&i<5)identity|=1<<i;}var tag=StackData.readCustom(card);if((mask&63)!=0&&!tag.contains(MANA_TAG))return false;return acceptsLand(tag.getInt(MANA_TAG).orElse(0),identity,"legal".equalsIgnoreCase(meta.commanderLegality()),mask);}
 public static ScryfallModels.Card model(JsonObject j){var m=GSON.fromJson(j,ScryfallModels.Card.class);m.manaValue=j.has("cmc")?j.get("cmc").getAsInt():0;m.isTokenLike=isToken(m.typeLine);m.faces=j.has("card_faces")?GSON.fromJson(j.get("card_faces"),new TypeToken<List<ScryfallModels.Card.Face>>(){}.getType()):List.of();m.price=j.has("prices")?GSON.fromJson(j.get("prices"),ScryfallModels.Card.Price.class):null;if(m.colors==null)m.colors=List.of();if(m.colorIdentity==null)m.colorIdentity=List.of();if(m.imageUris==null)m.imageUris=Map.of();if(m.legalities==null)m.legalities=Map.of();return m;}
 public static CompletableFuture<Page> search(int kind,String text,int mana,int page){return search(kind,text,mana,page,"","");}
 public static CompletableFuture<Page> search(int kind,String text,int mana,int page,String oracle,String stats){return page(kind,query(kind,text,mana,oracle,stats),page,"cards");}
 public static CompletableFuture<Page> artworks(int kind,ItemStack card,int page){return page(kind,artworkQuery(kind,card),page,"art");}
 static CompletableFuture<Page> page(int kind,String q,int page,String unique){return ScryfallService.supplyAsync(()->{int offset=Math.clamp(page,0,1000)*40,remote=offset/175+1,start=offset%175;JsonObject data=fetch(q,remote,unique);int total=data.has("total_cards")?data.get("total_cards").getAsInt():0;List<Hit> hits=new ArrayList<>();append(data,start,hits,kind);if(hits.size()<40&&data.has("has_more")&&data.get("has_more").getAsBoolean())append(fetch(q,remote+1,unique),0,hits,kind);return new Page(List.copyOf(hits),total,offset+40<total);});}
 static void append(JsonObject page,int start,List<Hit> result,int kind){JsonArray cards=page.getAsJsonArray("data");if(cards==null)return;for(int i=start;i<cards.size()&&result.size()<40;i++){JsonObject card=cards.get(i).getAsJsonObject();var m=model(card);if(kind==0?isLand(m.typeLine):isToken(m.typeLine))result.add(new Hit(m,manaMask(card)));}}
 static JsonObject fetch(String query,int page,String unique)throws Exception{
  String url="https://api.scryfall.com/cards/search?q="+URLEncoder.encode(query,StandardCharsets.UTF_8)+"&include_extras=true&unique="+unique+"&order=name&page="+page;
  synchronized(CACHE){var c=CACHE.get(url);if(c!=null&&System.currentTimeMillis()-c.time<300000)return c.json;}
  var request=HttpRequest.newBuilder(URI.create(url)).timeout(Duration.ofSeconds(20)).header("Accept","application/json").header("User-Agent","MTGCompanion/0.4.0 (Minecraft MTGCard addon)").GET().build();
  var response=HTTP.send(request,HttpResponse.BodyHandlers.ofInputStream());byte[] bytes;try(var body=response.body()){bytes=body.readNBytes(8*1024*1024+1);}if(bytes.length>8*1024*1024)throw new IllegalStateException("Catalogue response too large");
  JsonObject json=JsonParser.parseString(new String(bytes,StandardCharsets.UTF_8)).getAsJsonObject();if(response.statusCode()==404){JsonObject empty=new JsonObject();empty.add("data",new JsonArray());empty.addProperty("total_cards",0);empty.addProperty("has_more",false);return empty;}if(response.statusCode()!=200)throw new IllegalStateException("Catalogue HTTP "+response.statusCode());
  synchronized(CACHE){if(CACHE.size()>=32)CACHE.remove(CACHE.keySet().iterator().next());CACHE.put(url,new Cached(json,System.currentTimeMillis()));}return json;
 }
}
