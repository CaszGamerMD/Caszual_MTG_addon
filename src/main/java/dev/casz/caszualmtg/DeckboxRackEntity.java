package dev.casz.caszualmtg;

import com.mojang.serialization.Codec;
import com.mojang.serialization.codecs.RecordCodecBuilder;
import com.spider.mtgcard.deckbox.DeckboxBlockItem;
import net.minecraft.core.BlockPos;
import net.minecraft.core.NonNullList;
import net.minecraft.world.Container;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.level.block.entity.BlockEntity;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.storage.ValueInput;
import net.minecraft.world.level.storage.ValueOutput;
import net.minecraft.core.HolderLookup;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.nbt.NbtOps;
import net.minecraft.resources.RegistryOps;
import net.minecraft.network.protocol.Packet;
import net.minecraft.network.protocol.game.ClientGamePacketListener;
import net.minecraft.network.protocol.game.ClientboundBlockEntityDataPacket;
import java.util.*;

/** Rack inventory is owned by the block; all five deckboxes survive world saving. */
public final class DeckboxRackEntity extends BlockEntity implements Container {
 public static final int SIZE=5;
 private final NonNullList<ItemStack> boxes=NonNullList.withSize(SIZE,ItemStack.EMPTY);
 public DeckboxRackEntity(BlockPos at,BlockState s){super(CaszualMtg.RACK_BE,at,s);}
 public List<ItemStack> contents(){return boxes.stream().map(ItemStack::copy).toList();}
 public void restore(List<ItemStack> saved){
  for(int i=0;i<SIZE;i++)setItem(i,i<saved.size()?saved.get(i):ItemStack.EMPTY);
 }
 @Override protected void loadAdditional(ValueInput input){
  super.loadAdditional(input);Collections.fill(boxes,ItemStack.EMPTY);
  for(SlotSave slot:input.read("Deckboxes",SlotSave.CODEC.listOf()).orElse(List.of()))
   if(slot.index>=0&&slot.index<SIZE&&slot.item.getItem() instanceof DeckboxBlockItem)
    boxes.set(slot.index,slot.item.copyWithCount(1));
 }
 @Override protected void saveAdditional(ValueOutput output){
  super.saveAdditional(output);
  var saved=new ArrayList<SlotSave>();
  for(int i=0;i<SIZE;i++)if(!boxes.get(i).isEmpty())saved.add(new SlotSave(i,boxes.get(i)));
  output.store("Deckboxes",SlotSave.CODEC.listOf(),saved);
 }
 /** Sync actual ItemStacks, so the client renderer displays each real deckbox model. */
 @Override public CompoundTag getUpdateTag(HolderLookup.Provider lookup){
  CompoundTag tag=new CompoundTag();
  var saved=new ArrayList<SlotSave>();
  for(int i=0;i<SIZE;i++)if(!boxes.get(i).isEmpty())saved.add(new SlotSave(i,boxes.get(i)));
  SlotSave.CODEC.listOf().encodeStart(RegistryOps.create(NbtOps.INSTANCE,lookup),saved)
    .result().ifPresent(v->tag.put("Deckboxes",v));
  return tag;
 }
 @Override public Packet<ClientGamePacketListener> getUpdatePacket(){
  return ClientboundBlockEntityDataPacket.create(this);
 }
 private record SlotSave(int index,ItemStack item){
  static final Codec<SlotSave> CODEC=RecordCodecBuilder.create(i->i.group(
   Codec.INT.fieldOf("Slot").forGetter(SlotSave::index),
   ItemStack.CODEC.fieldOf("Stack").forGetter(SlotSave::item)
  ).apply(i,SlotSave::new));
 }
 @Override public int getContainerSize(){return SIZE;}
 @Override public boolean isEmpty(){return boxes.stream().allMatch(ItemStack::isEmpty);}
 @Override public ItemStack getItem(int i){return i>=0&&i<SIZE?boxes.get(i):ItemStack.EMPTY;}
 @Override public ItemStack removeItem(int i,int count){if(i<0||i>=SIZE)return ItemStack.EMPTY;ItemStack result=boxes.get(i).split(count);updated();return result;}
 @Override public ItemStack removeItemNoUpdate(int i){if(i<0||i>=SIZE)return ItemStack.EMPTY;ItemStack out=boxes.get(i);boxes.set(i,ItemStack.EMPTY);updated();return out;}
 @Override public void setItem(int i,ItemStack item){
  if(i<0||i>=SIZE||(!item.isEmpty()&&!(item.getItem() instanceof DeckboxBlockItem)))return;
  boxes.set(i,item.isEmpty()?ItemStack.EMPTY:item.copyWithCount(1));updated();
 }
 @Override public boolean stillValid(Player p){return level!=null&&level.getBlockState(worldPosition).is(CaszualMtg.RACK)&&p.distanceToSqr(worldPosition.getX()+.5,worldPosition.getY()+.5,worldPosition.getZ()+.5)<=64;}
 @Override public void clearContent(){Collections.fill(boxes,ItemStack.EMPTY);updated();}
 private void updated(){
  setChanged();
  if(level==null||level.isClientSide())return;
  BlockState old=getBlockState(),next=old;
  for(int i=0;i<SIZE;i++)next=next.setValue(DeckboxRackBlock.OCCUPIED[i],!boxes.get(i).isEmpty());
  if(!next.equals(old))level.setBlock(worldPosition,next,3);
  else level.sendBlockUpdated(worldPosition,old,old,3);
 }
}
