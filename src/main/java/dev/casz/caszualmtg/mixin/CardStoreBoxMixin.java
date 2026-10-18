package dev.casz.caszualmtg.mixin;

import com.spider.mtgcard.cardstore.CardStoreBlockEntity;
import com.spider.mtgcard.deckbox.DeckboxBlockItem;
import dev.casz.caszualmtg.*;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.Level;
import net.minecraft.core.BlockPos;
import net.minecraft.world.level.block.state.BlockState;
import net.fabricmc.fabric.api.networking.v1.ServerPlayNetworking;
import com.spider.mtgcard.cardstore.CardStoreScreenHandler;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.level.storage.ValueInput;
import net.minecraft.world.level.storage.ValueOutput;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Shadow;
import org.jetbrains.annotations.Nullable;
import java.util.UUID;
import org.spongepowered.asm.mixin.Unique;
import org.spongepowered.asm.mixin.injection.*;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;
import org.slf4j.LoggerFactory;

/** Stores the extra deckbox on the Card Store itself and routes printed cards into it. */
@Mixin(CardStoreBlockEntity.class)
public abstract class CardStoreBoxMixin implements CardStoreBoxAccess {
 @Shadow private @Nullable UUID activeBuyer;
 @Unique private ItemStack caszual$deckbox=ItemStack.EMPTY;
 @Unique private int caszual$inserted=0;
 @Unique private int caszual$total=0;
 @Unique private int caszual$overflow=0;
 @Unique private long caszual$finishedAt=-1;
 @Override public int caszual$inserted(){return caszual$inserted;}
 @Override public int caszual$total(){return caszual$total;}
 @Override public int caszual$overflow(){return caszual$overflow;}
 @Override public long caszual$finishedAt(){return caszual$finishedAt;}
 @Inject(method="beginPrinting",at=@At("HEAD"),remap=false)
 private void caszual$startProgress(UUID buyer,ItemStack template,int count,CallbackInfo ci){
  CardStoreBlockEntity be=(CardStoreBlockEntity)(Object)this;
  if(!be.isDelivering()){
   caszual$total=0;caszual$inserted=0;caszual$overflow=0;caszual$finishedAt=-1;
  }
  if(count>0&&!template.isEmpty())caszual$total=Math.min(1000000,caszual$total+count);
 }
 @Inject(method="stopDelivering",at=@At("TAIL"),remap=false)
 private void caszual$doneProgress(CallbackInfo ci){
  CardStoreBlockEntity be=(CardStoreBlockEntity)(Object)this;
  if(be.getLevel()!=null)caszual$finishedAt=be.getLevel().getGameTime();
 }
 @Inject(method="tick",at=@At("HEAD"),remap=false)
 private static void caszual$sendProgress(Level world,BlockPos pos,BlockState state,CardStoreBlockEntity be,CallbackInfo ci){
  if(!(world instanceof ServerLevel level)||level.getGameTime()%10!=0)return;
  CardStoreBoxAccess access=(CardStoreBoxAccess)be;
  boolean printing=be.isDelivering();
  long elapsed=level.getGameTime()-access.caszual$finishedAt();
  boolean recentlyDone=access.caszual$finishedAt()>=0&&elapsed>=0&&elapsed<=60;
  int phase=printing
   ?(access.caszual$overflow()>0?CardStoreStatusWire.Progress.FULL:CardStoreStatusWire.Progress.PRINTING)
   :recentlyDone
    ?(access.caszual$overflow()>0?CardStoreStatusWire.Progress.FULL:CardStoreStatusWire.Progress.DONE)
    :CardStoreStatusWire.Progress.IDLE;
  var progress=new CardStoreStatusWire.Progress(pos,phase,access.caszual$inserted(),access.caszual$total(),access.caszual$overflow());
  for(var player:level.players())
   if(player.containerMenu instanceof CardStoreScreenHandler menu&&menu.blockPos.equals(pos))
    ServerPlayNetworking.send(player,progress);
 }


 @Override public ItemStack caszual$getDeckbox(){return caszual$deckbox;}
 @Override public void caszual$setDeckbox(ItemStack stack){
  if(!stack.isEmpty()&&(!(stack.getItem() instanceof DeckboxBlockItem)||stack.getCount()!=1))return;
  caszual$deckbox=stack.isEmpty()?ItemStack.EMPTY:stack.copy();
  ((CardStoreBlockEntity)(Object)this).setChanged();
 }

 @Inject(method="loadAdditional",at=@At("TAIL"))
 private void caszual$load(ValueInput input,CallbackInfo ci){
  ItemStack loaded=input.read("CaszualCardStoreDeckbox",ItemStack.CODEC).orElse(ItemStack.EMPTY);
  caszual$deckbox=loaded.getItem() instanceof DeckboxBlockItem&&loaded.getCount()==1?loaded:ItemStack.EMPTY;
 }
 @Inject(method="saveAdditional",at=@At("TAIL"))
 private void caszual$save(ValueOutput output,CallbackInfo ci){
  if(!caszual$deckbox.isEmpty())output.store("CaszualCardStoreDeckbox",ItemStack.CODEC,caszual$deckbox);
 }

 @Inject(method="tryDeliverOne",at=@At("HEAD"),cancellable=true,remap=false)
 private void caszual$directDeckboxDelivery(ItemStack card,CallbackInfo ci){
  CardStoreBlockEntity be=(CardStoreBlockEntity)(Object)this;
  if(card.isEmpty()||caszual$deckbox.isEmpty()||!(be.getLevel() instanceof ServerLevel level))return;
  try {
   var loaded=DeckboxTransfer.load(level.getServer(),caszual$deckbox);
   for(int i=0;i<com.spider.mtgcard.deckbox.DeckboxBlockEntity.MAIN_SLOTS;i++){
    if(!loaded.items().get(i).isEmpty())continue;
    loaded.items().set(i,card.copyWithCount(1));
    DeckboxTransfer.save(level.getServer(),caszual$deckbox,loaded);
    caszual$inserted=Math.min(1000000,caszual$inserted+1);
    be.setChanged();ci.cancel();return;
   }
   // A card had to be delivered elsewhere because the inserted box filled.
   caszual$overflow=Math.min(1000000,caszual$overflow+1);
  }catch(RuntimeException error){
   caszual$overflow=Math.min(1000000,caszual$overflow+1);
   LoggerFactory.getLogger("caszual_mtg").warn("Card Store deckbox delivery failed; falling back to native output",error);
  }
  // When the chosen deckbox fills up, prefer the buyer's free inventory
  // slots; never destroy a purchase. MTGCard's adjacent-box/front-ejection
  // path remains the final fallback when the buyer is offline or full.
  if(activeBuyer!=null){
   var buyer=level.getServer().getPlayerList().getPlayer(activeBuyer);
   if(buyer!=null){
    for(int i=0;i<36;i++)if(buyer.getInventory().getItem(i).isEmpty()){
     buyer.getInventory().setItem(i,card.copyWithCount(1));
     buyer.getInventory().setChanged();
     buyer.inventoryMenu.broadcastChanges();
     ci.cancel();return;
    }
   }
  }
 }
}
