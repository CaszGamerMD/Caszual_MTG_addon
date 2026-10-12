package dev.casz.caszualmtg;

import com.spider.mtgcard.cardstore.CardStoreBlockEntity;
import com.spider.mtgcard.deckbox.DeckboxBlockItem;
import net.minecraft.world.Container;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.item.ItemStack;

/** Single-slot menu adapter backed by the Card Store's persistent block-entity data. */
public final class CardStoreBoxInventory implements Container {
 private final CardStoreBlockEntity block;
 public CardStoreBoxInventory(CardStoreBlockEntity block){this.block=block;}
 public int getContainerSize(){return 1;}
 public boolean isEmpty(){return getItem(0).isEmpty();}
 public ItemStack getItem(int slot){return slot==0?((CardStoreBoxAccess)block).caszual$getDeckbox():ItemStack.EMPTY;}
 public ItemStack removeItem(int slot,int qty){
  if(slot!=0)return ItemStack.EMPTY;
  ItemStack stack=getItem(0),out=stack.split(qty);
  if(stack.isEmpty())((CardStoreBoxAccess)block).caszual$setDeckbox(ItemStack.EMPTY);
  else block.setChanged();
  return out;
 }
 public ItemStack removeItemNoUpdate(int slot){
  if(slot!=0)return ItemStack.EMPTY;
  ItemStack result=getItem(0);
  ((CardStoreBoxAccess)block).caszual$setDeckbox(ItemStack.EMPTY);
  return result;
 }
 public void setItem(int slot,ItemStack stack){
  if(slot!=0||(!stack.isEmpty()&&(!(stack.getItem() instanceof DeckboxBlockItem)||stack.getCount()!=1)))return;
  ((CardStoreBoxAccess)block).caszual$setDeckbox(stack);
 }
 public void setChanged(){block.setChanged();}
 public boolean stillValid(Player player){
  return block.getLevel()!=null&&player.level()==block.getLevel()&&
     player.distanceToSqr(block.getBlockPos().getX()+.5,block.getBlockPos().getY()+.5,block.getBlockPos().getZ()+.5)<=64;
 }
 public void clearContent(){((CardStoreBoxAccess)block).caszual$setDeckbox(ItemStack.EMPTY);}
}
