package dev.casz.mtg;

import com.spider.mtgcard.api.*;
import com.spider.mtgcard.deckbox.*;
import com.spider.mtgcard.util.*;
import net.minecraft.core.*;
import net.minecraft.core.component.DataComponents;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.nbt.*;
import net.minecraft.resources.RegistryOps;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.component.*;
import java.util.*;

/** Uses MTGCard's authoritative external deckbox record, never client item copies. */
public final class DeckboxTransfer {
 public record Loaded(UUID id,String type,String name,NonNullList<ItemStack> items){}
 public static Loaded load(ServerPlayer player,ItemStack box){if(!(box.getItem() instanceof DeckboxBlockItem item)||box.getCount()!=1)throw new IllegalArgumentException("Insert one MTGCard deckbox first.");
  var server=player.level().getServer();var tag=StackData.readCustom(box);String raw=tag.getString("mtgcard_deckbox_id").orElse("");
  if(!raw.isBlank()){var id=UUID.fromString(raw);var record=DeckboxStorage.load(server,server.registryAccess(),id).orElseThrow(()->new IllegalStateException("Deckbox storage record is missing; contents were not changed."));return new Loaded(id,record.type(),record.name(),copy(record.items()));}
  var items=NonNullList.withSize(DeckboxBlockEntity.INVENTORY_SIZE,ItemStack.EMPTY);var contents=box.get(DataComponents.CONTAINER);if(contents!=null)contents.copyInto(items);
  var legacy=tag.getCompound("BlockEntityTag");if(legacy.isPresent()){var list=legacy.get().getList("Items").orElse(new ListTag());var ops=RegistryOps.create(NbtOps.INSTANCE,server.registryAccess());for(var entry:list)if(entry instanceof CompoundTag stored){int index=stored.getInt("Slot").orElse(-1);if(index>=0&&index<items.size()){var stack=stored.getCompound("Stack").orElse(stored);items.set(index,ItemStack.CODEC.parse(ops,stack).getOrThrow());}}}
  return new Loaded(UUID.randomUUID(),BuiltInRegistries.BLOCK.getKey(item.getBlock()).toString(),box.getHoverName().getString(),items);
 }
 static NonNullList<ItemStack> copy(List<ItemStack> input){var result=NonNullList.withSize(DeckboxBlockEntity.INVENTORY_SIZE,ItemStack.EMPTY);for(int i=0;i<Math.min(input.size(),result.size());i++)result.set(i,input.get(i).copy());return result;}
 public static void save(ServerPlayer player,ItemStack box,Loaded loaded){for(ItemStack card:loaded.items)if(!card.isEmpty())CardStackCompactor.compact(card);var server=player.level().getServer();DeckboxStorage.save(server,server.registryAccess(),loaded.id,loaded.type,loaded.name,loaded.items);var tag=StackData.readCustom(box);tag.putString("mtgcard_deckbox_id",loaded.id.toString());tag.remove("BlockEntityTag");StackData.writeCustom(box,tag);box.remove(DataComponents.CONTAINER);}
 public static int deposit(ServerPlayer p,ItemStack item,Banks bank){Loaded box=load(p,item);List<ItemStack> deposit=new ArrayList<>();int count=0;for(int i=0;i<box.items.size();i++){ItemStack card=box.items.get(i);if(CardDatabaseCards.canStore(card)&&Banks.kind(card)==2){deposit.add(card.copy());count+=card.getCount();box.items.set(i,ItemStack.EMPTY);}}if(count==0)return 0;save(p,item,box);for(var card:deposit)bank.add(card,2,card.getCount());return count;}
 public static int withdraw(ServerPlayer p,ItemStack item,Banks bank,String key,String search,int wanted){Loaded box=load(p,item);List<Integer> free=new ArrayList<>();for(int i=0;i<DeckboxBlockEntity.MAIN_SLOTS;i++)if(box.items.get(i).isEmpty())free.add(i);if(free.isEmpty())return 0;
  var candidates=key==null?bank.search(2,search):bank.entries.containsKey(key)?List.of(Map.entry(key,bank.entries.get(key))):List.<Map.Entry<String,Banks.Entry>>of();Map<String,Long> taken=new LinkedHashMap<>();int placed=0,limit=Math.min(wanted,free.size());
  for(var candidate:candidates){var e=candidate.getValue();if(e.kind()!=2||Banks.kind(e.card())!=2)continue;int amount=(int)Math.min(e.count(),limit-placed);for(int i=0;i<amount;i++)box.items.set(free.get(placed++),CardDatabaseCards.copyForExtraction(e.card()));if(amount>0)taken.put(candidate.getKey(),(long)amount);if(placed>=limit)break;}
  if(placed==0)return 0;save(p,item,box);taken.forEach(bank::take);return placed;
 }
}
