package dev.casz.caszualmtg;

import net.fabricmc.fabric.api.menu.v1.ExtendedMenuProvider;
import net.fabricmc.fabric.api.menu.v1.ExtendedMenuType;
import net.minecraft.core.BlockPos;
import net.minecraft.network.RegistryFriendlyByteBuf;
import net.minecraft.network.codec.StreamCodec;
import net.minecraft.network.chat.Component;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.*;
import net.minecraft.world.entity.player.*;
import net.minecraft.world.inventory.*;
import net.minecraft.world.item.ItemStack;

/** Four transfer-safe slots and the player's normal inventory. */
public final class StaffRackMenu extends AbstractContainerMenu {
 public record OpenData(BlockPos pos){
  public static final StreamCodec<RegistryFriendlyByteBuf,OpenData> CODEC=StreamCodec.of(
    (b,data)->b.writeBlockPos(data.pos()),b->new OpenData(b.readBlockPos()));
 }
 public final BlockPos pos;
 public StaffRackMenu(int sync,Inventory inventory,OpenData data){
  super(CaszualMtg.STAFF_RACK_MENU,sync);
  pos=data.pos().immutable();
  Container target=inventory.player.level().getBlockEntity(pos) instanceof StaffRackEntity rack?rack:new SimpleContainer(4);
  for(int i=0;i<4;i++)addSlot(new Slot(target,i,28+39*i,50){
   @Override public boolean mayPlace(ItemStack item){return item.is(CaszualMtg.TARGETING_STAFF);}
   @Override public int getMaxStackSize(){return 1;}
  });
  addStandardInventorySlots(inventory,12,126);
 }
 public static ExtendedMenuProvider<OpenData> provider(BlockPos pos){return new ExtendedMenuProvider<>(){
  public OpenData getScreenOpeningData(ServerPlayer player){return new OpenData(pos);}
  public Component getDisplayName(){return Component.literal("Staff Rack");}
  public AbstractContainerMenu createMenu(int sync,Inventory inventory,Player player){
   return new StaffRackMenu(sync,inventory,new OpenData(pos));
  }
 };}
 @Override public boolean stillValid(Player player){
  return !player.isRemoved()&&player.distanceToSqr(pos.getX()+.5,pos.getY()+.5,pos.getZ()+.5)<=64
    &&player.level().getBlockState(pos).is(CaszualMtg.STAFF_RACK);
 }
 @Override public ItemStack quickMoveStack(Player player,int index){
  if(index<0||index>=slots.size())return ItemStack.EMPTY;
  Slot from=slots.get(index);
  if(!from.hasItem())return ItemStack.EMPTY;
  ItemStack item=from.getItem(),original=item.copy();
  if(index<4){if(!moveItemStackTo(item,4,slots.size(),true))return ItemStack.EMPTY;}
  else if(item.is(CaszualMtg.TARGETING_STAFF)){if(!moveItemStackTo(item,0,4,false))return ItemStack.EMPTY;}
  else return ItemStack.EMPTY;
  if(item.isEmpty())from.setByPlayer(ItemStack.EMPTY);else from.setChanged();
  from.onTake(player,item);
  return original;
 }
}
