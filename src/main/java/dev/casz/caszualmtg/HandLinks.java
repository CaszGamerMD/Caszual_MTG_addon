package dev.casz.caszualmtg;

import net.minecraft.core.BlockPos;
import net.minecraft.server.level.ServerLevel;

import java.util.UUID;

/**
 * Resolves physically placed Hands by a durable reciprocal seat link.
 *
 * A 70-block cube contains nearly 3 million blocks: DO NOT search it each
 * golem tick or every tabletop refresh. New links use exact persisted positions.
 * The small fallback scan preserves old saves created before reverse links.
 */
public final class HandLinks {
 public static final int TABLE_RANGE=70;
 private static final int LEGACY_RANGE=8;
 private HandLinks(){}

 public static boolean inTableRange(BlockPos hand,BlockPos table){
  return hand!=null&&table!=null&&hand.distSqr(table)<=TABLE_RANGE*TABLE_RANGE;
 }

 /** Resolve the assigned seat's Hand, including across loaded chunks. */
 public static HandBlockEntity linked(ServerLevel world,TabletopBlockEntity seat,UUID owner){
  if(seat==null||owner==null)return null;
  BlockPos at=seat.getBlockPos();
  BlockPos handPos=seat.linkedHand();
  if(handPos!=null){
   if(!inTableRange(handPos,at)||!world.hasChunkAt(handPos))return null;
   if(world.getBlockEntity(handPos) instanceof HandBlockEntity hand
      &&owner.equals(hand.owner())&&at.equals(hand.linkedTable()))return hand;
   // Stale or unowned reverse pointers must never expose another player's
   // cards, nor fall through to an unrelated Hand.
   return null;
  }
  // Pre-upgrade saves lack a reverse pointer and only linked locally.
  HandBlockEntity closest=null;
  double best=Double.MAX_VALUE;
  for(BlockPos p:BlockPos.betweenClosed(at.offset(-LEGACY_RANGE,-LEGACY_RANGE,-LEGACY_RANGE),
                                        at.offset(LEGACY_RANGE,LEGACY_RANGE,LEGACY_RANGE))){
   if(!world.hasChunkAt(p))continue;
   if(world.getBlockEntity(p) instanceof HandBlockEntity h
      &&owner.equals(h.owner())
      &&(at.equals(h.linkedTable())||h.legacyTableDiscovery()&&h.linkedTable()==null)){
    double d=at.distSqr(p);
    if(d<best){closest=h;best=d;}
   }
  }
  return closest;
 }
}
