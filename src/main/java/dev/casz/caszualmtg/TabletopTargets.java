package dev.casz.caszualmtg;

import net.minecraft.core.BlockPos;
import net.minecraft.server.level.ServerLevel;
import java.util.*;

/**
 * Public, ephemeral declarations of intent, not resolved spells or combat.
 * The card/item state is never moved and private hands are never disclosed.
 * One current marker per actor, expiring after 20 seconds.
 */
public final class TabletopTargets {
 private static final int MAX=64;
 private static final long TTL_TICKS=20*20L;
 private static final Map<ServerLevel,LinkedHashMap<UUID,Mark>> BY_LEVEL=
  Collections.synchronizedMap(new WeakHashMap<>());
 public record Mark(UUID actor,BlockPos fromSeat,String fromName,String sourceCard,
                    BlockPos targetSeat,String targetCard,String kind,long expires) {
  public Mark {
   Objects.requireNonNull(actor);Objects.requireNonNull(fromSeat);Objects.requireNonNull(targetSeat);
  }
  public boolean targetsCard(){return !targetCard.isBlank();}
 }
 private TabletopTargets(){}
 private static LinkedHashMap<UUID,Mark> state(ServerLevel world){
  return BY_LEVEL.computeIfAbsent(world,ignored->new LinkedHashMap<>());
 }
 public static void mark(ServerLevel world,UUID actor,BlockPos from,String fromName,
       String sourceCard,BlockPos target,String targetCard,String kind){
  if(actor==null||from==null||target==null)return;
  String safeName=fromName==null?"Player":fromName.substring(0,Math.min(fromName.length(),64));
  String source=sourceCard==null?"":sourceCard;
  String destination=targetCard==null?"":targetCard;
  if(source.length()>TabletopWire.MAX_CARD_ID_LENGTH||destination.length()>TabletopWire.MAX_CARD_ID_LENGTH)return;
  if(!Set.of("target","attack","block","cast","ability").contains(kind))return;
  synchronized(BY_LEVEL){
   LinkedHashMap<UUID,Mark> active=state(world);
   active.entrySet().removeIf(entry->entry.getValue().expires()<=world.getGameTime());
   active.remove(actor);
   while(active.size()>=MAX)active.remove(active.keySet().iterator().next());
   active.put(actor,new Mark(actor,from.immutable(),safeName,source,target.immutable(),
      destination,kind,world.getGameTime()+TTL_TICKS));
  }
 }
 public static void clear(ServerLevel world,UUID actor){
  synchronized(BY_LEVEL){state(world).remove(actor);}
 }
 public static List<Mark> visible(ServerLevel world,List<TabletopBlockEntity> connected){
  Set<BlockPos> available=new HashSet<>();
  for(var tile:connected)available.add(tile.getBlockPos());
  synchronized(BY_LEVEL){
   LinkedHashMap<UUID,Mark> active=state(world);
   active.entrySet().removeIf(entry->entry.getValue().expires()<=world.getGameTime());
   return active.values().stream().filter(m->available.contains(m.fromSeat())
       &&available.contains(m.targetSeat())).toList();
  }
 }
}
