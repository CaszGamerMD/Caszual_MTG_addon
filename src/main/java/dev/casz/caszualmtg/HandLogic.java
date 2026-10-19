package dev.casz.caszualmtg;

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
 private static final Map<UUID,BlockPos> PENDING_LIFE_LINKS=new ConcurrentHashMap<>();
 private static final Map<UUID,BlockPos> PENDING_TABLE_LINKS=new ConcurrentHashMap<>();
 private static final Map<UUID,BlockPos> PENDING_GOLEM_LINKS=new ConcurrentHashMap<>();
 private static final Map<UUID,BlockPos> PENDING_ALL=new ConcurrentHashMap<>();
 private static void clearPending(UUID id){
  PENDING_LINKS.remove(id);PENDING_LIFE_LINKS.remove(id);PENDING_TABLE_LINKS.remove(id);
  PENDING_GOLEM_LINKS.remove(id);PENDING_ALL.remove(id);
 }
 private static void arm(ServerPlayer player,BlockPos pos,String kind){
  UUID id=player.getUUID();clearPending(id);
  switch(kind){
   case "deck"->PENDING_LINKS.put(id,pos.immutable());
   case "life"->PENDING_LIFE_LINKS.put(id,pos.immutable());
   case "table"->PENDING_TABLE_LINKS.put(id,pos.immutable());
   case "golem"->PENDING_GOLEM_LINKS.put(id,pos.immutable());
   case "all"->PENDING_ALL.put(id,pos.immutable());
  }
 }
 private static boolean inRange(BlockPos hand,BlockPos target){
  return Math.abs(target.getX()-hand.getX())<=LINK_RANGE
    &&Math.abs(target.getY()-hand.getY())<=LINK_RANGE
    &&Math.abs(target.getZ()-hand.getZ())<=LINK_RANGE;
 }
 private static void advance(ServerPlayer player,HandBlockEntity hand){
  if(hand.linkedControl()!=null&&hand.linkedLife()!=null&&hand.linkedTable()!=null){
   PENDING_ALL.remove(player.getUUID());
   player.sendSystemMessage(Component.literal("Card Hand linked to Deck Control, Life Point and MTG Table."));
  }else player.sendSystemMessage(Component.literal("Still linking. Missing: "+
   (hand.linkedControl()==null?"Deck Control ":"")+
   (hand.linkedLife()==null?"Life Point ":"")+
   (hand.linkedTable()==null?"MTG Table":"")));
 }


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
   case "table_color" -> {
    if(!hand.canManage(player)){reply(player,hand,"Only the hand owner can change their table color.");return;}
    if(!StaffColors.valid(req.text())){reply(player,hand,"Enter #RRGGBB.");return;}
    hand.tableColor(req.text());TabletopLogic.refreshColor(player,hand);reply(player,hand,"Table color saved.");
   }
   case "link_life", "link", "link_table", "link_all", "primary_golem" -> {
    if(!hand.canManage(player)){reply(player,hand,"Only the Hand manager may configure it.");return;}
    String mode=switch(req.action()){
     case "link_life"->"life";case "link"->"deck";case "link_table"->"table";
     case "link_all"->"all";default->"golem";
    };
    arm(player,hand.getBlockPos(),mode);
    reply(player,hand,mode.equals("all")?
      "Click the first Deck Control, Life Point and MTG Table, in any order.":
      "Link mode armed. Right-click the chosen "+mode+".");
   }
   case "cancel_link" -> {clearPending(player.getUUID());reply(player,hand,"Link mode cancelled.");}
   case "unlink_all" -> {
    if(!hand.canManage(player)){reply(player,hand,"Only the manager can unlink.");return;}
    clearPending(player.getUUID());hand.linkedControl(null);hand.linkedLife(null);hand.linkedTable(null);
    reply(player,hand,"All three device links cleared.");
   }
   case "primary_player" -> {
    if(!hand.canManage(player)){reply(player,hand,"Only the manager can set the primary.");return;}
    ServerPlayer selected=player.level().getServer().getPlayerList().getPlayerByName(req.text().trim());
    if(selected==null){reply(player,hand,"Enter the exact username of a player currently online.");return;}
    if(hand.linkedTable()!=null&&player.level().getBlockEntity(hand.linkedTable()) instanceof TabletopBlockEntity table
      &&table.seatOwner()!=null&&!table.seatOwner().equals(selected.getUUID())){
     reply(player,hand,"That player's UUID does not own the linked table seat.");return;
    }
    hand.assignPrimary(selected.getUUID(),selected.getGameProfile().name());
    reply(player,hand,"Primary player: "+selected.getGameProfile().name()+".");
   }
   case "primary_clear" -> {
    if(!hand.canManage(player)){reply(player,hand,"Only the manager can clear the primary.");return;}
    hand.clearPrimary();reply(player,hand,"Primary player unassigned.");
   }
   case "add_viewer" -> addViewer(player,hand,req.text());
   case "remove_viewer" -> {if(!hand.canManage(player)){reply(player,hand,"Only the hand owner can remove viewers.");return;}if(hand.removeViewer(req.text().trim()))reply(player,hand,"Viewer removed.");else reply(player,hand,"That viewer is not on this hand.");}
   case "discard_random" -> {
    if(!hand.isAuthorized(player)){reply(player,hand,"You can view this revealed hand, but only selected players can use it.");return;}
    if(hand.pendingStrictDiscards()>0){reply(player,hand,"Finish the required mulligan discards by selecting cards first.");return;}
    reply(player,hand,discardRandom(player,hand));
   }
   case "deposit_inventory" -> depositInventory(player,hand);
   case "staff_colors" -> updateStaffColors(player,hand,req.text());
   case "take_selected" -> takeSelected(player,hand,req.text());
   case "discard_selected" -> discardSelected(player,hand,req.text());
   case "mulligan_friendly" -> mulligan(player,hand,false);
   case "mulligan_strict" -> mulligan(player,hand,true);
   case "mulligan_cancel" -> finishMulligan(player,hand);
  }
 }

 /** Transfer only actual TCG cards; creative inventory transfers still consume inputs. */
 static void depositInventory(ServerPlayer player,HandBlockEntity hand){
  if(!hand.isAuthorized(player)){reply(player,hand,"Only selected players can deposit into this hand.");return;}
  int moved=0;
  for(int slot=0;slot<36&&hand.cardCount()<HandBlockEntity.SIZE;slot++){
   ItemStack stack=player.getInventory().getItem(slot);
   if(stack.isEmpty()||!stack.is(com.spider.mtgcard.item.ModItemTags.TCG_CARD))continue;
   while(!stack.isEmpty()&&hand.cardCount()<HandBlockEntity.SIZE){
    if(!hand.addCard(stack))break;
    stack.shrink(1);
    moved++;
   }
  }
  if(moved>0){player.getInventory().setChanged();player.inventoryMenu.broadcastChanges();}
  reply(player,hand,moved>0?"Deposited "+moved+" inventory card"+(moved==1?"":"s")+" into the hand.":"No eligible cards or no space left in the hand.");
 }

 /**
  * Input is a comma-separated set of current visible indices. Reject duplicates,
  * invalid entries and insufficient space BEFORE removing anything; remove from
  * highest index downwards so remaining visible indices cannot shift.
  */
 static java.util.List<Integer> selectedIndices(String raw,int count){
  if(raw.isBlank()||raw.length()>512)return java.util.List.of();
  java.util.TreeSet<Integer> indices=new java.util.TreeSet<>(java.util.Comparator.reverseOrder());
  String[] parts=raw.split(",",-1);
  if(parts.length>HandBlockEntity.SIZE)return java.util.List.of();
  for(String part:parts){
   int idx=parseIndex(part);
   if(idx<0||idx>=count||!indices.add(idx))return java.util.List.of();
  }
  return java.util.List.copyOf(indices);
 }

 static int staffCount(ServerPlayer player){
  int count=0;
  for(int i=0;i<player.getInventory().getContainerSize();i++)
   if(player.getInventory().getItem(i).is(CaszualMtg.TARGETING_STAFF))count++;
  return count;
 }
 static void updateStaffColors(ServerPlayer player,HandBlockEntity hand,String raw){
  if(!hand.isAuthorized(player)){reply(player,hand,"Only authorized Hand players can change staff colors.");return;}
  if(staffCount(player)==0){reply(player,hand,"Keep a targeting staff in your inventory to edit its colors.");return;}
  String[] input=raw.split(",",-1);
  if(input.length!=2||!StaffColors.valid(input[0])||!StaffColors.valid(input[1])){
   reply(player,hand,"Enter two hex colors in #RRGGBB format.");return;
  }
  String left=StaffColors.normalize(input[0]),right=StaffColors.normalize(input[1]);
  hand.staffColors(left,right);
  int updated=0;
  for(int i=0;i<player.getInventory().getContainerSize();i++){
   ItemStack stack=player.getInventory().getItem(i);
   if(!stack.is(CaszualMtg.TARGETING_STAFF))continue;
   StaffColors.write(stack,left,right);
   updated++;
  }
  player.getInventory().setChanged();
  player.inventoryMenu.broadcastChanges();
  StaffTargets.refreshOwner(player);
  reply(player,hand,"Applied "+left+" / "+right+" to "+updated+" targeting staff"+(updated==1?"":"s")+".");
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
  java.util.List<Integer> indices=selectedIndices(raw,hand.cardCount());
  if(indices.isEmpty()){reply(player,hand,"Select one or more cards first.");return;}
  java.util.List<Integer> emptySlots=new java.util.ArrayList<>();
  for(int slot=0;slot<36;slot++)if(player.getInventory().getItem(slot).isEmpty())emptySlots.add(slot);
  if(emptySlots.size()<indices.size()){
   reply(player,hand,"Need "+indices.size()+" empty inventory slots (you have "+emptySlots.size()+"). Nothing was taken.");return;
  }
  int moved=0;
  for(int index:indices){
   ItemStack card=hand.removeVisibleIndex(index);
   if(card.isEmpty())throw new IllegalStateException("Hand changed during a validated bulk transfer.");
   player.getInventory().setItem(emptySlots.get(moved++),card);
  }
  player.getInventory().setChanged();
  player.inventoryMenu.broadcastChanges();
  reply(player,hand,"Took "+moved+" card"+(moved==1?"":"s")+" from the hand.");
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
  UUID id=player.getUUID();
  BlockPos handPos=PENDING_LINKS.getOrDefault(id,PENDING_ALL.get(id));
  if(handPos==null||!(player.level().getBlockEntity(controlPos) instanceof DeckControlBlockEntity control))return false;
  HandBlockEntity hand=get(player,handPos);
  if(hand==null||!hand.canManage(player)){clearPending(id);return true;}
  if(!inRange(handPos,controlPos)){player.sendSystemMessage(Component.literal("Deck Control must be within 8 blocks."));return true;}
  if(PENDING_ALL.containsKey(id)&&hand.linkedControl()!=null)return true;
  HandBlockEntity used=findLinked(control);
  if(used!=null&&used!=hand){player.sendSystemMessage(Component.literal("That Deck Control is linked to another Hand."));return true;}
  hand.linkedControl(controlPos);PENDING_LINKS.remove(id);
  player.sendSystemMessage(Component.literal("Deck Control linked: "+shortPos(controlPos)));
  if(PENDING_ALL.containsKey(id))advance(player,hand);
  return true;
 }
 public static boolean completePendingLifeLink(ServerPlayer player,BlockPos lifePos){
  UUID id=player.getUUID();
  BlockPos handPos=PENDING_LIFE_LINKS.getOrDefault(id,PENDING_ALL.get(id));
  if(handPos==null||!(player.level().getBlockEntity(lifePos) instanceof com.spider.mtgcard.life.LifePointBlockEntity))return false;
  HandBlockEntity hand=get(player,handPos);
  if(hand==null||!hand.canManage(player)){clearPending(id);return true;}
  if(!inRange(handPos,lifePos)){player.sendSystemMessage(Component.literal("Life Point must be within 8 blocks."));return true;}
  if(PENDING_ALL.containsKey(id)&&hand.linkedLife()!=null)return true;
  hand.linkedLife(lifePos);PENDING_LIFE_LINKS.remove(id);
  player.sendSystemMessage(Component.literal("Life Point linked: "+shortPos(lifePos)));
  if(PENDING_ALL.containsKey(id))advance(player,hand);
  return true;
 }
 public static boolean completePendingTableLink(ServerPlayer player,BlockPos tablePos){
  UUID id=player.getUUID();
  BlockPos handPos=PENDING_TABLE_LINKS.getOrDefault(id,PENDING_ALL.get(id));
  if(handPos==null||!(player.level().getBlockEntity(tablePos) instanceof TabletopBlockEntity table))return false;
  HandBlockEntity hand=get(player,handPos);
  if(hand==null||!hand.canManage(player)){clearPending(id);return true;}
  if(!inRange(handPos,tablePos)){player.sendSystemMessage(Component.literal("MTG Table must be within 8 blocks."));return true;}
  if(PENDING_ALL.containsKey(id)&&hand.linkedTable()!=null)return true;
  if(table.seatOwner()!=null&&hand.owner()!=null&&!table.seatOwner().equals(hand.owner())){
   player.sendSystemMessage(Component.literal("That table belongs to a different primary player."));return true;
  }
  hand.linkedTable(tablePos);PENDING_TABLE_LINKS.remove(id);
  player.sendSystemMessage(Component.literal("MTG Table linked: "+shortPos(tablePos)));
  if(PENDING_ALL.containsKey(id))advance(player,hand);
  return true;
 }
 public static boolean completePendingGolem(ServerPlayer player,net.minecraft.world.entity.animal.golem.IronGolem golem){
  UUID id=player.getUUID();BlockPos handPos=PENDING_GOLEM_LINKS.get(id);
  if(handPos==null||!golem.entityTags().contains(CommanderGolems.TAG))return false;
  HandBlockEntity hand=get(player,handPos);
  if(hand==null||!hand.canManage(player)){clearPending(id);return true;}
  if(player.level()!=golem.level()||!inRange(handPos,golem.blockPosition())){
   player.sendSystemMessage(Component.literal("Golem must be within 8 blocks of its Hand."));return true;
  }
  BlockPos at=hand.linkedTable();
  if(at!=null){
   if(!(player.level().getBlockEntity(at) instanceof TabletopBlockEntity table)
      ||!golem.getUUID().equals(table.seatOwner())){
    player.sendSystemMessage(Component.literal("Golem must own the Hand's linked table seat."));return true;
   }
  }
  hand.assignPrimary(golem.getUUID(),"Commander Golem");clearPending(id);
  player.sendSystemMessage(Component.literal("Card Hand primary player: Commander Golem."));
  return true;
 }
 public static void clearPendingLink(ServerPlayer player){clearPending(player.getUUID());}

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
   hand.strictMulligans(),hand.pendingStrictDiscards(),staffCount(player)>0,hand.staffLeft(),hand.staffRight(),hand.tableColor(),hand.linkedLife()==null?"Not linked":shortPos(hand.linkedLife()),
    hand.linkedTable()==null?"Not linked":shortPos(hand.linkedTable()),hand.primaryName()
  ));
 }
 static String shortPos(BlockPos p){return p.getX()+", "+p.getY()+", "+p.getZ();}
 private HandLogic(){}
}
