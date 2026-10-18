package dev.casz.caszualmtg;

import com.spider.mtgcard.graveyard.GraveyardBlockEntity;
import net.minecraft.core.BlockPos;
import net.minecraft.core.HolderLookup;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.network.protocol.Packet;
import net.minecraft.network.protocol.game.ClientGamePacketListener;
import net.minecraft.network.protocol.game.ClientboundBlockEntityDataPacket;
import net.minecraft.world.level.block.state.BlockState;
import org.jetbrains.annotations.Nullable;

/** Retains the exact native 100+100-card Graveyard BE and its MTGCard menus. */
public final class CustomGraveyardEntity extends GraveyardBlockEntity {
 public CustomGraveyardEntity(BlockPos pos,BlockState state){super(pos,state);}
 @Override public @Nullable Packet<ClientGamePacketListener> getUpdatePacket(){
  return ClientboundBlockEntityDataPacket.create(this);
 }
 @Override public CompoundTag getUpdateTag(HolderLookup.Provider lookup){
  CompoundTag out=super.getUpdateTag(lookup);
  out.putString("CaszualMaterial",((BoxMaterial)this).companion$material());
  return out;
 }
}
