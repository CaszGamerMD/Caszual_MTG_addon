package dev.casz.caszualmtg;

import net.minecraft.core.BlockPos;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.entity.EntityTypes;
import net.minecraft.world.entity.decoration.ArmorStand;
import net.minecraft.world.phys.AABB;
import java.util.*;

/**
 * One tiny, invisible mount per occupied chair. Abandoned mounts are removed
 * when the rider leaves, when the chair breaks, or on the next server tick.
 */
public final class ChairSeats {
 private static final Map<UUID,Seat> ACTIVE=new HashMap<>();
 private record Seat(ServerLevel world,BlockPos pos,ArmorStand mount) {}
 private ChairSeats(){}
 public static void sit(ServerPlayer player,BlockPos pos){
  if(!(player.level() instanceof ServerLevel level)||player.isPassenger())return;
  Seat old=ACTIVE.get(player.getUUID());
  if(old!=null&&old.mount.isAlive())old.mount.discard();
  // Marker armor stands have no collisions and do not appear through the chair.
  ArmorStand seat=new ArmorStand(EntityTypes.ARMOR_STAND,level);
  seat.setPos(pos.getX()+.5,pos.getY()+.37,pos.getZ()+.5);
  seat.setSmall(true);
  seat.setMarker(true);
  seat.setInvisible(true);
  seat.setSilent(true);
  seat.setNoGravity(true);
  seat.setInvulnerable(true);
  seat.addTag("caszual_mtg_chair_seat");
  level.addFreshEntity(seat);
  if(player.startRiding(seat,true))ACTIVE.put(player.getUUID(),new Seat(level,pos.immutable(),seat));
  else seat.discard();
 }
 public static void tick(ServerLevel world){
  var iterator=ACTIVE.entrySet().iterator();
  while(iterator.hasNext()){
   var entry=iterator.next();
   var e=entry.getValue();
   if(e.world!=world)continue;
   var mount=e.mount();
   boolean valid=mount.isAlive()&&world.getBlockState(e.pos()).getBlock() instanceof ChairBlock
     &&mount.hasPassenger(world.getServer().getPlayerList().getPlayer(entry.getKey()));
   if(!valid){if(mount.isAlive())mount.discard();iterator.remove();}
  }
 }
}
