package dev.casz.caszualmtg;

import com.mojang.serialization.Codec;
import com.mojang.serialization.codecs.RecordCodecBuilder;
import net.minecraft.core.BlockPos;
import net.minecraft.core.HolderLookup;
import net.minecraft.core.NonNullList;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.nbt.NbtOps;
import net.minecraft.network.protocol.Packet;
import net.minecraft.network.protocol.game.ClientGamePacketListener;
import net.minecraft.network.protocol.game.ClientboundBlockEntityDataPacket;
import net.minecraft.resources.RegistryOps;
import net.minecraft.world.Container;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.level.block.entity.BlockEntity;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.storage.ValueInput;
import net.minecraft.world.level.storage.ValueOutput;
import java.util.*;

/** Four independent staff slots. Entire ItemStacks are retained, including custom RGB settings. */
public final class StaffRackEntity extends BlockEntity implements Container {
 public static final int SIZE=4;
 private final NonNullList<ItemStack> staffs=NonNullList.withSize(SIZE,ItemStack.EMPTY);

 public StaffRackEntity(BlockPos pos,BlockState state){super(CaszualMtg.STAFF_RACK_BE,pos,state);}
 public List<ItemStack> contents(){return staffs.stream().map(ItemStack::copy).toList();}
 public void restore(List<ItemStack> saved){
  for(int i=0;i<SIZE;i++)setItem(i,i<saved.size()?saved.get(i):ItemStack.EMPTY);
 }
 @Override protected void loadAdditional(ValueInput input){
  super.loadAdditional(input);
  Collections.fill(staffs,ItemStack.EMPTY);
  for(SlotSave slot:input.read("Staffs",SlotSave.CODEC.listOf()).orElse(List.of()))
   if(slot.index()>=0&&slot.index()<SIZE&&slot.item().is(CaszualMtg.TARGETING_STAFF))
    staffs.set(slot.index(),slot.item().copyWithCount(1));
 }
 @Override protected void saveAdditional(ValueOutput output){
  super.saveAdditional(output);
  output.store("Staffs",SlotSave.CODEC.listOf(),savedSlots());
 }
 private List<SlotSave> savedSlots(){
  List<SlotSave> saved=new ArrayList<>();
  for(int i=0;i<SIZE;i++)if(!staffs.get(i).isEmpty())saved.add(new SlotSave(i,staffs.get(i)));
  return saved;
 }
 /** Sync the actual staff stacks so visual rendering retains custom item components. */
 @Override public CompoundTag getUpdateTag(HolderLookup.Provider lookup){
  CompoundTag tag=new CompoundTag();
  SlotSave.CODEC.listOf().encodeStart(RegistryOps.create(NbtOps.INSTANCE,lookup),savedSlots())
    .result().ifPresent(nbt->tag.put("Staffs",nbt));
  return tag;
 }
 @Override public Packet<ClientGamePacketListener> getUpdatePacket(){return ClientboundBlockEntityDataPacket.create(this);}
 private record SlotSave(int index,ItemStack item){
  static final Codec<SlotSave> CODEC=RecordCodecBuilder.create(i->i.group(
   Codec.INT.fieldOf("Slot").forGetter(SlotSave::index),
   ItemStack.CODEC.fieldOf("Stack").forGetter(SlotSave::item)
  ).apply(i,SlotSave::new));
 }
 @Override public int getContainerSize(){return SIZE;}
 @Override public boolean isEmpty(){return staffs.stream().allMatch(ItemStack::isEmpty);}
 @Override public ItemStack getItem(int slot){return slot>=0&&slot<SIZE?staffs.get(slot):ItemStack.EMPTY;}
 @Override public ItemStack removeItem(int slot,int count){
  if(slot<0||slot>=SIZE)return ItemStack.EMPTY;
  ItemStack removed=staffs.get(slot).split(count);
  if(staffs.get(slot).isEmpty())staffs.set(slot,ItemStack.EMPTY);
  updated();
  return removed;
 }
 @Override public ItemStack removeItemNoUpdate(int slot){
  if(slot<0||slot>=SIZE)return ItemStack.EMPTY;
  ItemStack removed=staffs.get(slot);
  staffs.set(slot,ItemStack.EMPTY);
  updated();
  return removed;
 }
 @Override public void setItem(int slot,ItemStack stack){
  if(slot<0||slot>=SIZE||(!stack.isEmpty()&&!stack.is(CaszualMtg.TARGETING_STAFF)))return;
  staffs.set(slot,stack.isEmpty()?ItemStack.EMPTY:stack.copyWithCount(1));
  updated();
 }
 @Override public boolean stillValid(Player player){
  return level!=null&&level.getBlockState(worldPosition).is(CaszualMtg.STAFF_RACK)
    &&player.distanceToSqr(worldPosition.getX()+.5,worldPosition.getY()+.5,worldPosition.getZ()+.5)<=64;
 }
 @Override public void clearContent(){Collections.fill(staffs,ItemStack.EMPTY);updated();}
 private void updated(){
  setChanged();
  if(level!=null&&!level.isClientSide()){
   BlockState state=getBlockState();
   level.sendBlockUpdated(worldPosition,state,state,3);
  }
 }
}
