package dev.casz.caszualmtg;

import net.fabricmc.fabric.api.networking.v1.ServerPlayNetworking;
import net.minecraft.core.BlockPos;
import net.minecraft.network.RegistryFriendlyByteBuf;
import net.minecraft.network.codec.StreamCodec;
import net.minecraft.network.protocol.common.custom.CustomPacketPayload;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.phys.Vec3;

public final class DeckboxRefreshWire {
 public record Refresh(BlockPos pos) implements CustomPacketPayload {
  public static final Type<Refresh> TYPE=new Type<>(CaszualMtg.id("deckbox_refresh"));
  public static final StreamCodec<RegistryFriendlyByteBuf,Refresh> CODEC=StreamCodec.of(
   (b,p)->b.writeBlockPos(p.pos),
   b->new Refresh(b.readBlockPos())
  );
  @Override public Type<Refresh> type(){return TYPE;}
 }

 public static void broadcast(ServerLevel level,BlockPos pos){
  Vec3 center=Vec3.atCenterOf(pos);
  for(ServerPlayer player:level.getServer().getPlayerList().getPlayers()){
   if(player.level()!=level)continue;
   if(player.distanceToSqr(center)>16384.0)continue;
   ServerPlayNetworking.send(player,new Refresh(pos.immutable()));
  }
 }
 private DeckboxRefreshWire(){}
}
