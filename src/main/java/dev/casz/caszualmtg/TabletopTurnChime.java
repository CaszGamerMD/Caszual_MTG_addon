package dev.casz.caszualmtg;

import com.spider.mtgcard.life.LifePointBlockEntity;
import net.minecraft.core.BlockPos;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.sounds.SoundEvents;
import net.minecraft.sounds.SoundSource;

import java.util.*;

/**
 * A short, personal chime at the transition to the player's own active turn.
 * This does not play to spectators and never force-loads distant chunks.
 */
public final class TabletopTurnChime {
 private record Watch(BlockPos life,boolean active){}
 private static final Map<UUID,Watch> WATCHED=new HashMap<>();
 private TabletopTurnChime(){}

 public static void watch(ServerPlayer player,HandBlockEntity hand){
  if(hand==null||!player.getUUID().equals(hand.owner()))return;
  BlockPos pos=hand.linkedLife();
  if(pos==null)return;
  Watch previous=WATCHED.get(player.getUUID());
  if(previous!=null&&previous.life().equals(pos))return;
  // Connecting midway through one's existing turn must not ring again.
  boolean current=player.level().getBlockEntity(pos) instanceof LifePointBlockEntity lp
    &&CommanderPod.status((ServerLevel)player.level(),lp).playable();
  WATCHED.put(player.getUUID(),new Watch(pos.immutable(),current));
 }

 public static void tick(ServerLevel world){
  if(world.getGameTime()%5!=0)return;
  for(ServerPlayer player:world.players()){
   Watch watch=WATCHED.get(player.getUUID());
   if(watch==null||!world.hasChunkAt(watch.life()))continue;
   if(!(world.getBlockEntity(watch.life()) instanceof LifePointBlockEntity lp))continue;
   boolean active=CommanderPod.status(world,lp).playable();
   if(active&&!watch.active())
    player.playNotifySound(SoundEvents.NOTE_BLOCK_CHIME.value(),SoundSource.PLAYERS,.72f,1.28f);
   WATCHED.put(player.getUUID(),new Watch(watch.life(),active));
  }
 }

 public static void clear(ServerPlayer player){WATCHED.remove(player.getUUID());}
}
