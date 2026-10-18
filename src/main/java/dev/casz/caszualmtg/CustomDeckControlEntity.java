package dev.casz.caszualmtg;

import com.spider.mtgcard.deckcontrol.DeckControlBlockEntity;
import net.minecraft.core.BlockPos;
import net.minecraft.core.HolderLookup;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.network.protocol.Packet;
import net.minecraft.network.protocol.game.ClientGamePacketListener;
import net.minecraft.network.protocol.game.ClientboundBlockEntityDataPacket;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.storage.ValueInput;
import net.minecraft.world.level.storage.ValueOutput;
import org.jetbrains.annotations.Nullable;

/** Native Deck Control functionality, with durable Caszual panel material. */
public final class CustomDeckControlEntity extends DeckControlBlockEntity implements BoxMaterial {
 private String caszualMaterial=BoxMaterial.DEFAULT;
 public CustomDeckControlEntity(BlockPos pos,BlockState state){super(pos,state);}
 @Override public String companion$material(){return caszualMaterial;}
 @Override public void companion$material(String value){
  String material=BoxMaterial.safe(value);
  if(material.equals(caszualMaterial))return;
  caszualMaterial=material;
  setChanged();
  if(level!=null){
   BlockState state=getBlockState();
   level.sendBlockUpdated(worldPosition,state,state,Block.UPDATE_ALL);
  }
 }
 @Override public Object getRenderData(){return caszualMaterial;}
 @Override protected void loadAdditional(ValueInput in){
  super.loadAdditional(in);
  caszualMaterial=BoxMaterial.safe(in.getStringOr("CaszualMaterial",BoxMaterial.DEFAULT));
 }
 @Override protected void saveAdditional(ValueOutput out){
  super.saveAdditional(out);
  out.putString("CaszualMaterial",caszualMaterial);
 }
 @Override public CompoundTag getUpdateTag(HolderLookup.Provider lookup){
  CompoundTag result=super.getUpdateTag(lookup);
  result.putString("CaszualMaterial",caszualMaterial);
  return result;
 }
 @Override public @Nullable Packet<ClientGamePacketListener> getUpdatePacket(){
  return ClientboundBlockEntityDataPacket.create(this);
 }
}
