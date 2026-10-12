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

/** Native inventory slot for the deckbox at the builder, not a nearby block. */
public final class BuilderMenu extends AbstractContainerMenu {
 public record OpenData(BlockPos pos){
  public static final StreamCodec<RegistryFriendlyByteBuf,OpenData> CODEC=StreamCodec.of((b,p)->b.writeBlockPos(p.pos),(b)->new OpenData(b.readBlockPos()));
 }
 public final BlockPos pos;
 private final Player owner;
 public BuilderMenu(int sync,Inventory inventory,OpenData data){
  super(CaszualMtg.BUILDER_MENU,sync);pos=data.pos().immutable();owner=inventory.player;
  Container target=inventory.player.level().getBlockEntity(pos) instanceof BuilderBlockEntity be?be:new SimpleContainer(1);
  addSlot(new Slot(target,0,449,56){@Override public boolean mayPlace(ItemStack item){return item.getItem() instanceof DeckboxBlockItem;}@Override public int getMaxStackSize(){return 1;}});
  addStandardInventorySlots(inventory,12,318);
 }
 public static ExtendedMenuProvider<OpenData> provider(BlockPos pos){return new ExtendedMenuProvider<>(){
  public OpenData getScreenOpeningData(ServerPlayer player){return new OpenData(pos);}
  public Component getDisplayName(){return Component.literal("Deck Builder");}
  public AbstractContainerMenu createMenu(int id,Inventory inv,Player player){return new BuilderMenu(id,inv,new OpenData(pos));}
 };}
 @Override public boolean stillValid(Player p){return owner==p&&!p.isRemoved()&&p.distanceToSqr(pos.getX()+.5,pos.getY()+.5,pos.getZ()+.5)<=64&&p.level().getBlockState(pos).is(CaszualMtg.BUILDER);}
 @Override public ItemStack quickMoveStack(Player p,int index){
  if(index<0||index>=slots.size())return ItemStack.EMPTY;Slot slot=slots.get(index);if(!slot.hasItem())return ItemStack.EMPTY;
  ItemStack moving=slot.getItem(),orig=moving.copy();
  if(index==0){if(!moveItemStackTo(moving,1,slots.size(),true))return ItemStack.EMPTY;}
  else if(moving.getItem() instanceof DeckboxBlockItem){if(!moveItemStackTo(moving,0,1,false))return ItemStack.EMPTY;}
  else return ItemStack.EMPTY;
  if(moving.isEmpty())slot.setByPlayer(ItemStack.EMPTY);else slot.setChanged();slot.onTake(p,moving);return orig;
 }
}
