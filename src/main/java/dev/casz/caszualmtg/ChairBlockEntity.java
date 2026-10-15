package dev.casz.caszualmtg;

import net.minecraft.core.BlockPos;
import net.minecraft.core.HolderLookup;
import net.minecraft.core.component.DataComponentMap;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.network.protocol.game.ClientboundBlockEntityDataPacket;
import net.minecraft.network.protocol.game.ClientGamePacketListener;
import net.minecraft.network.protocol.Packet;
import net.minecraft.world.level.block.entity.BlockEntity;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.storage.ValueInput;
import net.minecraft.world.level.storage.ValueOutput;
import org.jetbrains.annotations.Nullable;

/** The source material is saved with the chair and synced to clients as one
 * registry ID, avoiding one blockstate/property/model per wood material. */
public final class ChairBlockEntity extends BlockEntity {
 private String material=ChairWood.DEFAULT;
 private int matRgb=0xFFFFFF;
 public record RenderData(String wood,int paperRgb) {}
 public int paperRgb(){return matRgb;}
 public void paperRgb(int rgb){
  int next=rgb&0xFFFFFF;
  if(matRgb==next)return;
  matRgb=next;
  setChanged();
  if(level!=null){
   BlockState state=getBlockState();
   level.sendBlockUpdated(worldPosition,state,state,3);
  }
 }
 public ChairBlockEntity(BlockPos pos,BlockState state){super(CaszualMtg.CHAIR_BE,pos,state);}
 public String material(){return material;}
 public void material(String source){
  String next=ChairWood.safe(source);
  if(next.equals(material))return;
  material=next;
  setChanged();
  if(level!=null){
   BlockState state=getBlockState();
   level.sendBlockUpdated(worldPosition,state,state,3);
  }
 }
 /** Read by Fabric's per-block render-data model wrapper. */
 public Object getRenderData(){return new RenderData(material,matRgb);}
 @Override protected void saveAdditional(ValueOutput out){
  super.saveAdditional(out);out.putString("ChairWood",material);out.putInt("PaperRgb",matRgb);
 }
 @Override protected void loadAdditional(ValueInput in){
  super.loadAdditional(in);material=ChairWood.safe(in.getStringOr("ChairWood",ChairWood.DEFAULT));
  matRgb=in.getIntOr("PaperRgb",0xFFFFFF)&0xFFFFFF;
 }
 @Override protected void collectImplicitComponents(DataComponentMap.Builder builder){
  super.collectImplicitComponents(builder);
  builder.set(CaszualMtg.CHAIR_MATERIAL,material);
 }
 @Override public CompoundTag getUpdateTag(HolderLookup.Provider lookups){
  CompoundTag result=super.getUpdateTag(lookups);
  result.putString("ChairWood",material);
  result.putInt("PaperRgb",matRgb);
  return result;
 }
 @Override public @Nullable Packet<ClientGamePacketListener> getUpdatePacket(){
  return ClientboundBlockEntityDataPacket.create(this);
 }
}
