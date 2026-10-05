package dev.casz.mtg;

import com.spider.mtgcard.deckcontrol.DeckControlBlockEntity;
import com.spider.mtgcard.graveyard.GraveyardBlockEntity;
import net.fabricmc.fabric.api.networking.v1.ServerPlayNetworking;
import net.minecraft.core.*;
import net.minecraft.network.chat.Component;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.item.ItemStack;
import java.security.SecureRandom;

public final class HandLogic {
 private static final int LINK_RANGE=8;
 private static final SecureRandom RANDOM=new SecureRandom();

 public static void open(ServerPlayer player,BlockPos pos){
  HandBlockEntity hand=get(player,pos);if(hand==null)return;hand.ensureOwner(player);reply(player,hand,"Hand ready.");
 }

 public static void handle(ServerPlayer player,HandWire.Request req){
  HandBlockEntity hand=get(player,req.pos());if(hand==null)return;hand.ensureOwner(player);
  switch(req.action()){
   case "refresh" -> reply(player,hand,"Refreshed.");
   case "reveal" -> {if(!hand.canView(player)){reply(player,hand,"You are not allowed to reveal this hand.");return;}hand.revealAll(!hand.revealAll());reply(player,hand,hand.revealAll()?"Hand revealed to everyone.":"Hand is private again.");}
   case "link" -> {if(!hand.canManage(player)){reply(player,hand,"Only the hand owner can change its Deck Control link.");return;}DeckControlBlockEntity dc=nearestControl(player,hand.getBlockPos());if(dc==null){reply(player,hand,"No Deck Control found within "+LINK_RANGE+" blocks.");return;}hand.linkedControl(dc.getBlockPos());reply(player,hand,"Linked to Deck Control at "+shortPos(dc.getBlockPos())+".");}
   case "add_viewer" -> addViewer(player,hand,req.text());
   case "remove_viewer" -> {if(!hand.canManage(player)){reply(player,hand,"Only the hand owner can remove viewers.");return;}if(hand.removeViewer(req.text().trim()))reply(player,hand,"Viewer removed.");else reply(player,hand,"That viewer is not on this hand.");}
   case "discard_random" -> {if(!hand.canView(player)){reply(player,hand,"You cannot use this hand.");return;}String result=discardRandom(player,hand);reply(player,hand,result);}
  }
 }

 static void addViewer(ServerPlayer owner,HandBlockEntity hand,String raw){
  if(!hand.canManage(owner)){reply(owner,hand,"Only the hand owner can add viewers.");return;}
  String name=raw.trim();if(name.isBlank()){reply(owner,hand,"Enter an online player name.");return;}
  ServerPlayer target=owner.level().getServer().getPlayerList().getPlayerByName(name);
  if(target==null){reply(owner,hand,"Player must be online to add them.");return;}
  hand.addViewer(target.getUUID(),target.getGameProfile().name());reply(owner,hand,"Added "+target.getGameProfile().name()+" to this hand.");
 }

 static HandBlockEntity get(ServerPlayer player,BlockPos pos){
  if(player.distanceToSqr(pos.getX()+.5,pos.getY()+.5,pos.getZ()+.5)>64)return null;
  return player.level().getBlockEntity(pos) instanceof HandBlockEntity h?h:null;
 }

 static DeckControlBlockEntity nearestControl(ServerPlayer player,BlockPos from){
  DeckControlBlockEntity best=null;double bestD=Double.MAX_VALUE;
  for(BlockPos p:BlockPos.betweenClosed(from.offset(-LINK_RANGE,-LINK_RANGE,-LINK_RANGE),from.offset(LINK_RANGE,LINK_RANGE,LINK_RANGE))){
   if(!player.level().hasChunkAt(p))continue;
   if(player.level().getBlockEntity(p) instanceof DeckControlBlockEntity dc){double d=p.distSqr(from);if(d<bestD){best=dc;bestD=d;}}
  }
  return best;
 }

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
  HandBlockEntity hand=findLinked(control);if(hand==null||hand.cardCount()>=HandBlockEntity.SIZE)return false;
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
  int slot=-1;for(int i=0;i<100;i++)if(grave.getStack(i).isEmpty()){slot=i;break;}if(slot<0)return "Graveyard is full.";
  ItemStack card=hand.removeRandom(RANDOM);if(card.isEmpty())return "The hand is empty.";grave.setStack(slot,card);grave.markDirty();return "Discarded a random card to the Graveyard.";
 }

 static void reply(ServerPlayer player,HandBlockEntity hand,String message){
  boolean visible=hand.canView(player);String linked=hand.linkedControl()==null?"Not linked":shortPos(hand.linkedControl());
  ServerPlayNetworking.send(player,new HandWire.Reply(hand.getBlockPos(),message,visible,hand.canManage(player),hand.revealAll(),hand.cardCount(),linked,hand.viewerNames(),visible?hand.visibleCards():java.util.List.of()));
 }
 static String shortPos(BlockPos p){return p.getX()+", "+p.getY()+", "+p.getZ();}
 private HandLogic(){}
}
