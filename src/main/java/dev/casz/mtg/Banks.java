package dev.casz.mtg;
import com.mojang.serialization.*;
import com.mojang.serialization.codecs.RecordCodecBuilder;
import com.spider.mtgcard.api.*;
import com.spider.mtgcard.util.*;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.level.saveddata.*;
import net.minecraft.server.MinecraftServer;
import java.util.*;
public final class Banks extends SavedData {
 public record Entry(int kind,ItemStack card,long count) {
  static final Codec<Entry> CODEC=RecordCodecBuilder.create(i->i.group(Codec.INT.fieldOf("kind").forGetter(Entry::kind),ItemStack.CODEC.fieldOf("card").forGetter(Entry::card),Codec.LONG.fieldOf("count").forGetter(Entry::count)).apply(i,Entry::new));
 }
 public static final Codec<Banks> CODEC=Entry.CODEC.listOf().fieldOf("entries").codec().xmap(Banks::new,b->new ArrayList<>(b.entries.values()));
 public static final SavedDataType<Banks> TYPE=new SavedDataType<>(Companion.id("community_banks"),Banks::new,CODEC,null);
 final Map<String,Entry> entries=new LinkedHashMap<>();
 public Banks(){}
 private Banks(List<Entry> saved){for(Entry e:saved)if(e.kind>=0&&e.kind<=2&&e.count>0&&(e.kind==2||kind(e.card)==e.kind))entries.put(key(e.kind,e.card),e);}
 public static Banks get(MinecraftServer s){return s.overworld().getDataStorage().computeIfAbsent(TYPE);}
 public static int kind(ItemStack s){var m=TcgCardMeta.read(s);return Catalogue.isToken(m.typeLine())?1:Catalogue.isLand(m.typeLine())?0:2;}
 public static String key(int kind,ItemStack s){return kind+":"+CardDatabaseCards.databaseKey(s);}
 public void add(ItemStack s,int kind,long count){if(!CardDatabaseCards.canStore(s)||kind(s)!=kind)return;String k=key(kind,s);var old=entries.get(k);var clean=CardDatabaseCards.copyForExtraction(s);clean.setCount(1);entries.put(k,new Entry(kind,clean,kind==2?CardDatabaseCards.saturatedAdd(old==null?0:old.count,count):1));setDirty();}
 public void take(String k,long qty){Entry e=entries.get(k);if(e==null||e.kind!=2)return;if(qty>=e.count)entries.remove(k);else entries.put(k,new Entry(2,e.card,e.count-qty));setDirty();}
 public List<Map.Entry<String,Entry>> search(int kind,String q){String n=DeckList.normalize(q);return entries.entrySet().stream().filter(e->e.getValue().kind==kind&&kind(e.getValue().card)==kind).filter(e->n.isBlank()||DeckList.normalize(TcgCardMeta.displayName(e.getValue().card)).contains(n)||TcgCardMeta.read(e.getValue().card).typeLine().toLowerCase(Locale.ROOT).contains(n)).sorted(Comparator.comparing(e->TcgCardMeta.displayName(e.getValue().card))).toList();}
}
