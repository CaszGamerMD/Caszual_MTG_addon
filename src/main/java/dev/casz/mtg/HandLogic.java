package dev.casz.mtg;

import com.spider.mtgcard.deckcontrol.DeckControlBlockEntity;
import com.spider.mtgcard.graveyard.GraveyardBlockEntity;
import net.fabricmc.fabric.api.networking.v1.ServerPlayNetworking;
import net.minecraft.core.*;
import net.minecraft.network.chat.Component;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.item.ItemStack;
import java.security.SecureRandom;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;

public final class HandLogic {
 private static final int LINK_RANGE=8;
 private static final SecureRandom RANDOM=new SecureRandom();
 private static final Map<UUID,BlockPos> PENDING_LINKS=new ConcurrentHashMap<>();

 public static void open(ServerPlayer player,BlockPos pos){
  HandBlockEntity hand=get(player,pos);if(hand==null)return;hand.ensureOwner(player);reply(player,hand,"Hand ready.");
 }

 public static void depositHeld(ServerPlayer player,BlockPos pos,ItemStack held){
  HandBlockEntity hand=get(player,pos);if(hand==null)return;hand.ensureOwner(player);
  if(!hand.isAuthorized(player)){player.sendSystemMessage(Component.literal("This Card Hand is private."));return;}
  if(hand.cardCount()>=HandBlockEntity.SIZE){player.sendSystemMessage(Component.literal("Card Hand is full."));return;}
  if(!hand.addCard(held)){player.sendSystemMessage(Component.literal("Only MTG cards can be added to this hand."));return;}
  if(!player.getAbilities().instabuild)held.shrink(1);
  player.getInventory().setChanged();
  player.sendSystemMessage(Component.literal("Added a card to the Card Hand ("+hand.cardCount()+"/"+HandBlockEntity.SIZE+")."));
 }

 public static void handle(ServerPlayer player,HandWire.Request req){
  HandBlockEntity hand=get(player,req.pos());if(hand==null)return;hand.ensureOwner(player);
  switch(req.action()){
   case "refresh" -> reply(player,hand,"");
   case "reveal" -> {if(!hand.isAuthorized(player)){reply(player,hand,"Only selected hand players can change reveal mode.");return;}hand.revealAll(!hand.revealAll());reply(player,hand,hand.revealAll()?"Hand revealed to everyone.":"Hand is private again.");}
   case "link" -> {if(!hand.canManage(player)){reply(player,hand,"Only the hand owner can change its Deck Control link.");return;}PENDING_LINKS.put(player.getUUID(),hand.getBlockPos().immutable());reply(player,hand,"Link mode armed. Right-click the Deck Control you want to use.");}
   case "add_viewer" -> addViewer(player,hand,req.text());
   case "remove_viewer" -> {if(!hand.canManage(player)){reply(player,hand,"Only the hand owner can remove viewers.");return;}if(hand.removeViewer(req.text().trim()))reply(player,hand,"Viewer removed.");else reply(player,hand,"That viewer is not on this hand.");}
   case "discard_random" -> {
    if(!hand.isAuthorized(player)){reply(player,hand,"You can view this revealed hand, but only selected players can use it.");return;}
    if(hand.pendingStrictDiscards()>0){reply(player,hand,"Finish the required mulligan discards by selecting cards first.");return;}
    reply(player,hand,discardRandom(player,hand));
   }
   case "take_selected" -> takeSelected(player,hand,req.text());
   case "discard_selected" -> discardSelected(player,hand,req.text());
   case "mulligan_friendly" -> mulligan(player,hand,false);
   case "mulligan_strict" -> mulligan(player,hand,true);
   case "mulligan_cancel" -> finishMulligan(player,hand);
  }
 }

 static void addViewer(ServerPlayer owner,HandBlockEntity hand,String raw){
  if(!hand.canManage(owner)){reply(owner,hand,"Only the hand owner can add viewers.");return;}
  String name=raw.trim();if(name.isBlank()){reply(owner,hand,"Enter an online player name.");return;}
  ServerPlayer target=owner.level().getServer().getPlayerList().getPlayerByName(name);
  if(target==null){reply(owner,hand,"Player must be online to add them.");return;}
  hand.addViewer(target.getUUID(),target.getGameProfile().name());reply(owner,hand,"Added "+target.getGameProfile().name()+" to this hand.");
 }

 static void takeSelected(ServerPlayer player,HandBlockEntity hand,String raw){
  if(!hand.isAuthorized(player)){reply(player,hand,"Only selected players can take cards from this hand.");return;}
  if(hand.pendingStrictDiscards()>0){reply(player,hand,"Discard the required mulligan cards before taking cards out.");return;}
  int index=parseIndex(raw);if(index<0){reply(player,hand,"Select a card first.");return;}
  ItemStack card=hand.removeVisibleIndex(index);if(card.isEmpty()){reply(player,hand,"That card is no longer in the hand.");return;}
  if(!player.getInventory().add(card)){player.drop(card,false);}
  player.getInventory().setChanged();
  reply(player,hand,"Took selected card from the hand.");
 }

 static void discardSelected(ServerPlayer player,HandBlockEntity hand,String raw){
  if(!hand.isAuthorized(player)){reply(player,hand,"Only selected players can discard from this hand.");return;}
  if(hand.pendingStrictDiscards()<=0){reply(player,hand,"There are no required mulligan discards.");return;}
  int index=parseIndex(raw);if(index<0){reply(player,hand,"Select a card to discard.");return;}
  GraveyardBlockEntity grave=findGraveyard(player,hand);if(grave==null){reply(player,hand,"No Graveyard is touching the linked Deck Control.");return;}
  int slot=emptyGraveSlot(grave);if(slot<0){reply(player,hand,"Graveyard is full.");return;}
  ItemStack card=hand.removeVisibleIndex(index);if(card.isEmpty()){reply(player,hand,"That card is no longer in the hand.");return;}
  grave.setStack(slot,card);grave.markDirty();hand.consumeStrictDiscard();
  reply(player,hand,hand.pendingStrictDiscards()>0?"Discarded. "+hand.pendingStrictDiscards()+" mulligan discard"+(hand.pendingStrictDiscards()==1?"":"s")+" remaining.":"Strict mulligan complete.");
 }

 static void mulligan(ServerPlayer player,HandBlockEntity hand,boolean strict){
  if(!hand.isAuthorized(player)){reply(player,hand,"Only selected players can mulligan this hand.");return;}
  if(hand.pendingStrictDiscards()>0){reply(player,hand,"Finish the current strict mulligan discards first.");return;}
  DeckControlBlockEntity control=linkedControl(player,hand);if(control==null){reply(player,hand,"Link this hand to a Deck Control first.");return;}
  List<ItemStack> returned=hand.takeAllCards();
  if(!returned.isEmpty())control.putCardsOnBottom(returned);
  control.shuffle();
  for(ItemStack card:control.takeTopCards(7))hand.addCard(card);
  if(strict){
   int tries=hand.addStrictMulligan();
   reply(player,hand,"Strict mulligan #"+tries+": shuffled the hand into the library and drew 7.");
  }else{
   hand.resetMulligans();
   reply(player,hand,"Friendly mulligan: shuffled the hand into the library and drew 7.");
  }
 }

 static void finishMulligan(ServerPlayer player,HandBlockEntity hand){
  if(!hand.isAuthorized(player)){reply(player,hand,"Only selected players can finish mulligans.");return;}
  hand.finishStrictMulligans();
  int owed=hand.pendingStrictDiscards();
  reply(player,hand,owed>0?"Mulligan finished. Select and discard "+owed+" card"+(owed==1?"":"s")+".":"Mulligan finished. No discard required.");
 }

 static int parseIndex(String raw){try{return Integer.parseInt(raw.trim());}catch(Exception ignored){return -1;}}

 static HandBlockEntity get(ServerPlayer player,BlockPos pos){
  if(player.distanceToSqr(pos.getX()+.5,pos.getY()+.5,pos.getZ()+.5)>64)return null;
  return player.level().getBlockEntity(pos) instanceof HandBlockEntity h?h:null;
 }

 public static boolean completePendingLink(ServerPlayer player,BlockPos controlPos){
  BlockPos handPos=PENDING_LINKS.remove(player.getUUID());
  if(handPos==null)return false;
  if(!(player.level().getBlockEntity(handPos) instanceof HandBlockEntity hand)){player.sendSystemMessage(Component.literal("That Card Hand is no longer available."));return true;}
  if(!hand.canManage(player)){player.sendSystemMessage(Component.literal("Only the Card Hand owner can change its Deck Control link."));return true;}
  if(!(player.level().getBlockEntity(controlPos) instanceof DeckControlBlockEntity control)){return false;}
  long dx=controlPos.getX()-handPos.getX(),dy=controlPos.getY()-handPos.getY(),dz=controlPos.getZ()-handPos.getZ();
  if(Math.abs(dx)>LINK_RANGE||Math.abs(dy)>LINK_RANGE||Math.abs(dz)>LINK_RANGE){
   player.sendSystemMessage(Component.literal("That Deck Control is too far from the Card Hand (max "+LINK_RANGE+" blocks per axis)."));
   return true;
  }
  HandBlockEntity existing=findLinked(control);
  if(existing!=null&&existing!=hand){player.sendSystemMessage(Component.literal("That Deck Control is already linked to another Card Hand."));return true;}
  hand.linkedControl(controlPos);
  player.sendSystemMessage(Component.literal("Card Hand linked to Deck Control at "+shortPos(controlPos)+"."));
  return true;
 }
 public static void clearPendingLink(ServerPlayer player){PENDING_LINKS.remove(player.getUUID());}


 public static HandBlockEntity findLinked(DeckControlBlockEntity control){
  if(control==null||control.getLevel()==null)return null;BlockPos at=control.getBlockPos();
  for(BlockPos p:BlockPos.betweenClosed(at.offset(-LINK_RANGE,-LINK_RANGE,-LINK_RANGE),at.offset(LINK_RANGE,LINK_RANGE,LINK_RANGE))){
   if(!control.getLevel().hasChunkAt(p))continue;
   if(control.getLevel().getBlockEntity(p) instanceof HandBlockEntity hand&&at.equals(hand.linkedControl()))return hand;
  }
  return null;
 }

 /** @return true when the normal MTGCard draw was consumed by a linked hand. */
 public static boolean routeDraw(DeckControlBlockEntity control){
  HandBlockEntity hand=findLinked(control);if(hand==null)return false;if(hand.cardCount()>=HandBlockEntity.SIZE)return true;
  var drawn=control.takeTopCards(1);if(drawn.isEmpty())return true;
  ItemStack card=drawn.getFirst();if(hand.addCard(card))return true;
  control.putCardsOnBottom(drawn);return true;
 }

 public static String discardRandom(ServerPlayer player,HandBlockEntity hand){
  BlockPos linked=hand.linkedControl();if(linked==null)return "Link this hand to a Deck Control first.";
  if(!(player.level().getBlockEntity(linked) instanceof DeckControlBlockEntity control))return "Linked Deck Control is missing.";
  return discardRandom(control);
 }

 public static String discardRandom(DeckControlBlockEntity control){
  HandBlockEntity hand=findLinked(control);if(hand==null)return "No linked Hand block.";if(hand.cardCount()==0)return "The hand is empty.";
  GraveyardBlockEntity grave=null;for(Direction d:Direction.values())if(control.getLevel().getBlockEntity(control.getBlockPos().relative(d)) instanceof GraveyardBlockEntity g){grave=g;break;}
  if(grave==null)return "No Graveyard is touching the Deck Control.";
  int slot=emptyGraveSlot(grave);if(slot<0)return "Graveyard is full.";
  ItemStack card=hand.removeRandom(RANDOM);if(card.isEmpty())return "The hand is empty.";grave.setStack(slot,card);grave.markDirty();return "Discarded a random card to the Graveyard.";
 }

 static DeckControlBlockEntity linkedControl(ServerPlayer player,HandBlockEntity hand){
  BlockPos linked=hand.linkedControl();if(linked==null)return null;
  return player.level().getBlockEntity(linked) instanceof DeckControlBlockEntity dc?dc:null;
 }
 static GraveyardBlockEntity findGraveyard(ServerPlayer player,HandBlockEntity hand){
  DeckControlBlockEntity control=linkedControl(player,hand);if(control==null)return null;
  for(Direction d:Direction.values())if(player.level().getBlockEntity(control.getBlockPos().relative(d)) instanceof GraveyardBlockEntity grave)return grave;
  return null;
 }
 static int emptyGraveSlot(GraveyardBlockEntity grave){for(int i=0;i<100;i++)if(grave.getStack(i).isEmpty())return i;return -1;}

 static void reply(ServerPlayer player,HandBlockEntity hand,String message){
  boolean visible=hand.canView(player);String linked=hand.linkedControl()==null?"Not linked":shortPos(hand.linkedControl());
  boolean authorized=hand.isAuthorized(player);
  ServerPlayNetworking.send(player,new HandWire.Reply(
   hand.getBlockPos(),message,visible,authorized,hand.canManage(player),hand.revealAll(),hand.cardCount(),linked,
   hand.canManage(player)?hand.viewerNames():java.util.List.of(),visible?hand.visibleCards():java.util.List.of(),
   hand.strictMulligans(),hand.pendingStrictDiscards()
  ));
 }
 static String shortPos(BlockPos p){return p.getX()+", "+p.getY()+", "+p.getZ();}
 private HandLogic(){}
}
