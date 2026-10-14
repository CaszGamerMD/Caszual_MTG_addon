package dev.casz.caszualmtg;

import net.minecraft.core.BlockPos;
import net.minecraft.network.RegistryFriendlyByteBuf;
import net.minecraft.network.codec.StreamCodec;
import net.minecraft.network.protocol.common.custom.CustomPacketPayload;

/**
 * Server-authoritative print progress for the Card Store overlay.
 * Names and cards are deliberately omitted: only this public station's counts
 * and routing state are synced to players viewing its container.
 */
public final class CardStoreStatusWire {
 private CardStoreStatusWire(){}
 public record Progress(BlockPos pos, int phase, int inserted, int total, int overflow) implements CustomPacketPayload {
  public static final int IDLE=0, PRINTING=1, DONE=2, FULL=3;
  public static final Type<Progress> TYPE=new Type<>(CaszualMtg.id("card_store_progress"));
  public static final StreamCodec<RegistryFriendlyByteBuf,Progress> CODEC=StreamCodec.of(
   (b,p)->{
    b.writeBlockPos(p.pos());
    b.writeVarInt(p.phase());
    b.writeVarInt(p.inserted());
    b.writeVarInt(p.total());
    b.writeVarInt(p.overflow());
   },
   b->{
    BlockPos pos=b.readBlockPos();
    int phase=b.readVarInt(),inserted=b.readVarInt(),total=b.readVarInt(),overflow=b.readVarInt();
    if(phase<0||phase>FULL||inserted<0||total<0||overflow<0
       ||inserted>1000000||total>1000000||overflow>1000000)
     throw new IllegalArgumentException("Invalid Card Store progress");
    return new Progress(pos,phase,inserted,total,overflow);
   }
  );
  @Override public Type<Progress> type(){return TYPE;}
 }
}
