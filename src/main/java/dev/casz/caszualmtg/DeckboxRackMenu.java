package dev.casz.caszualmtg;

import com.spider.mtgcard.deckbox.DeckboxBlockItem;
import net.fabricmc.fabric.api.menu.v1.*;
import net.minecraft.core.BlockPos;
import net.minecraft.network.RegistryFriendlyByteBuf;
import net.minecraft.network.codec.StreamCodec;
import net.minecraft.network.chat.Component;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.*;
import net.minecraft.world.entity.player.*;
import net.minecraft.world.inventory.*;
import net.minecraft.world.item.ItemStack;

public final class DeckboxRackMenu extends AbstractContainerMenu {
 public record OpenData(BlockPos pos){
  public static final StreamCodec<RegistryFriendlyByteBuf,OpenData> CODEC=StreamCodec.of((b,v)->b.writeBlockPos(v.pos()),b->new OpenData(b.readBlockPos()));
 }
 public final BlockPos pos;
 public DeckboxRackMenu(int sync,Inventory inv,OpenData data){
  super(CaszualMtg.RACK_MENU,sync);pos=data.pos();
  Container rack=inv.player.level().getBlockEntity(pos) instanceof DeckboxRackEntity be?be:new SimpleContainer(5);
  for(int i=0;i<5;i++)addSlot(new Slot(rack,i,22+i*32,50){
   @Override public boolean mayPlace(ItemStack stack){return stack.getItem() instanceof DeckboxBlockItem;}
   @Override public int getMaxStackSize(){return 1;}
  });
  addStandardInventorySlots(inv,12,126);
 }
 public static ExtendedMenuProvider<OpenData> provider(BlockPos pos){return new ExtendedMenuProvider<>(){
  public OpenData getScreenOpeningData(ServerPlayer player){return new OpenData(pos);}
  public Component getDisplayName(){return Component.literal("Deckbox Rack");}
  public AbstractContainerMenu createMenu(int id,Inventory inv,Player p){return new DeckboxRackMenu(id,inv,new OpenData(pos));}
 };}
 @Override public boolean stillValid(Player p){return !p.isRemoved()&&p.distanceToSqr(pos.getX()+.5,pos.getY()+.5,pos.getZ()+.5)<=64&&p.level().getBlockState(pos).is(CaszualMtg.RACK);}
 @Override public ItemStack quickMoveStack(Player p,int at){
  if(at<0||at>=slots.size())return ItemStack.EMPTY;
  Slot src=slots.get(at);if(!src.hasItem())return ItemStack.EMPTY;ItemStack stack=src.getItem(),copy=stack.copy();
  if(at<5){if(!moveItemStackTo(stack,5,slots.size(),true))return ItemStack.EMPTY;}
  else if(stack.getItem() instanceof DeckboxBlockItem){if(!moveItemStackTo(stack,0,5,false))return ItemStack.EMPTY;}
  else return ItemStack.EMPTY;
  if(stack.isEmpty())src.setByPlayer(ItemStack.EMPTY);else src.setChanged();src.onTake(p,stack);return copy;
 }
}
