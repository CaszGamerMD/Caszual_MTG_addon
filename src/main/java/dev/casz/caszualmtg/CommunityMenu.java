package dev.casz.caszualmtg;

import net.fabricmc.fabric.api.menu.v1.*;
import com.spider.mtgcard.deckbox.DeckboxBlockItem;
import net.minecraft.core.BlockPos;
import net.minecraft.network.RegistryFriendlyByteBuf;
import net.minecraft.network.codec.StreamCodec;
import net.minecraft.network.chat.Component;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.*;
import net.minecraft.world.entity.player.*;
import net.minecraft.world.inventory.*;
import net.minecraft.world.item.ItemStack;

/** Per-viewer deckbox slot; closing always returns its item to that viewer. */
public final class CommunityMenu extends AbstractContainerMenu {
 public record OpenData(BlockPos pos){public static final StreamCodec<RegistryFriendlyByteBuf,OpenData> CODEC=StreamCodec.of((b,d)->b.writeBlockPos(d.pos),b->new OpenData(b.readBlockPos()));}
 public final BlockPos pos;
 final SimpleContainer box=new SimpleContainer(1);
 final SimpleContainer loose=new SimpleContainer(1);
 final Player owner;
 public CommunityMenu(int sync,Inventory inv,OpenData data){super(CaszualMtg.COMMUNITY_MENU,sync);pos=data.pos.immutable();owner=inv.player;
  addSlot(new Slot(box,0,442,306){public boolean mayPlace(ItemStack s){return s.getItem() instanceof DeckboxBlockItem;}public int getMaxStackSize(){return 1;}});
  addSlot(new Slot(loose,0,442,282){
   @Override public boolean mayPlace(ItemStack s){return com.spider.mtgcard.api.CardDatabaseCards.canStore(s)&&Banks.kind(s)==2;}
  });
  addStandardInventorySlots(inv,12,318);
 }
 public static ExtendedMenuProvider<OpenData> provider(BlockPos at){return new ExtendedMenuProvider<>(){
  public OpenData getScreenOpeningData(ServerPlayer p){return new OpenData(at);}
  public Component getDisplayName(){return Component.literal("Community Card Collection");}
  public AbstractContainerMenu createMenu(int sync,Inventory inv,Player p){return new CommunityMenu(sync,inv,new OpenData(at));}
 };}
 public ItemStack deckbox(){return box.getItem(0);}
 public ItemStack looseCard(){return loose.getItem(0);}
 public void consumeLoose(){loose.setItem(0,ItemStack.EMPTY);broadcastChanges();}
 @Override public boolean stillValid(Player p){return p==owner&&!p.isRemoved()&&p.distanceToSqr(pos.getX()+.5,pos.getY()+.5,pos.getZ()+.5)<=64&&p.level().getBlockState(pos).is(CaszualMtg.CARDS);}
 @Override public ItemStack quickMoveStack(Player p,int index){
  if(index<0||index>=slots.size())return ItemStack.EMPTY;
  Slot from=slots.get(index);
  if(!from.hasItem())return ItemStack.EMPTY;
  ItemStack item=from.getItem(),copy=item.copy();
  if(index<2){
   if(!moveItemStackTo(item,2,slots.size(),true))return ItemStack.EMPTY;
  }else if(item.getItem() instanceof DeckboxBlockItem){
   if(!moveItemStackTo(item,0,1,false))return ItemStack.EMPTY;
  }else if(com.spider.mtgcard.api.CardDatabaseCards.canStore(item)&&Banks.kind(item)==2){
   if(!moveItemStackTo(item,1,2,false))return ItemStack.EMPTY;
  }else return ItemStack.EMPTY;
  if(item.isEmpty())from.setByPlayer(ItemStack.EMPTY);else from.setChanged();
  from.onTake(p,item);return copy;
 }
 @Override public void removed(Player p){super.removed(p);if(!p.level().isClientSide()){clearContainer(p,box);clearContainer(p,loose);if(p instanceof ServerPlayer sp)ServerLogic.close(sp);}}
}
