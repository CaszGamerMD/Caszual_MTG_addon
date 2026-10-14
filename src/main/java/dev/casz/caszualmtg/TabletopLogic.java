package dev.casz.caszualmtg;

import com.spider.mtgcard.deckcontrol.DeckControlBlockEntity;
import com.spider.mtgcard.graveyard.GraveyardBlockEntity;
import net.fabricmc.fabric.api.networking.v1.ServerPlayNetworking;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.network.chat.Component;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.item.ItemStack;
import java.util.*;
import java.util.concurrent.ConcurrentHashMap;

/**
 * All mutations are server-side. Every tile persists its own cards, so extending,
 * disconnecting or rebuilding a table does not teleport or duplicate a battlefield.
 */
public final class TabletopLogic {
 private static final int MAX_TILES=32;
 private static final int LINK_RANGE=8;
 private static final Map<UUID,ScrySession> SCRIES=new ConcurrentHashMap<>();
 private record ScrySession(BlockPos control,List<ItemStack> cards) {}
 private record Located(TabletopBlockEntity tile,TabletopBlockEntity.PlayedCard card) {}
 private record Context(List<TabletopBlockEntity> tiles,TabletopBlockEntity seat,HandBlockEntity hand,DeckControlBlockEntity deck,GraveyardBlockEntity grave) {}

 public static void close(ServerPlayer player){SCRIES.remove(player.getUUID());}
 public static void open(ServerPlayer player,BlockPos origin){
  List<TabletopBlockEntity> tiles=connected(player,origin);if(tiles.isEmpty())return;
  TabletopBlockEntity own=seat(tiles,player);
  // Occupancy is tied to the exact block a player opens. Empty seats are claimed once.
  if(own==null&&player.level().getBlockEntity(origin) instanceof TabletopBlockEntity clicked)clicked.claim(player);
  reply(player,origin,"Table ready.");
 }
 private static List<TabletopBlockEntity> connected(ServerPlayer player,BlockPos origin){
  if(player.distanceToSqr(origin.getX()+.5,origin.getY()+.5,origin.getZ()+.5)>64)return List.of();
  if(!player.level().hasChunkAt(origin)||!(player.level().getBlockEntity(origin) instanceof TabletopBlockEntity))return List.of();
  ArrayDeque<BlockPos> queue=new ArrayDeque<>();Set<BlockPos> seen=new HashSet<>();
  List<TabletopBlockEntity> out=new ArrayList<>();queue.add(origin);seen.add(origin);
  while(!queue.isEmpty()&&out.size()<MAX_TILES){
   BlockPos at=queue.removeFirst();
   if(!player.level().hasChunkAt(at))continue;
   if(!(player.level().getBlockEntity(at) instanceof TabletopBlockEntity tile))continue;
   out.add(tile);
   for(Direction dir:List.of(Direction.NORTH,Direction.EAST,Direction.SOUTH,Direction.WEST)){
    BlockPos next=at.relative(dir);
    if(seen.add(next))queue.add(next);
   }
  }
  return out;
 }
 private static TabletopBlockEntity seat(List<TabletopBlockEntity> tiles,ServerPlayer player){
  for(var t:tiles)if(t.ownedBy(player))return t;return null;
 }
 private static HandBlockEntity linkedHand(ServerPlayer player,TabletopBlockEntity seat){
  if(seat==null)return null;
  BlockPos at=seat.getBlockPos();HandBlockEntity best=null;long distance=Long.MAX_VALUE;
  for(BlockPos p:BlockPos.betweenClosed(at.offset(-LINK_RANGE,-LINK_RANGE,-LINK_RANGE),at.offset(LINK_RANGE,LINK_RANGE,LINK_RANGE))){
   if(!player.level().hasChunkAt(p))continue;
   if(player.level().getBlockEntity(p) instanceof HandBlockEntity h
      &&player.getUUID().equals(h.owner())&&h.linkedControl()!=null){
    long d=at.distSqr(p);
    if(d<distance){best=h;distance=d;}
   }
  }
  return best;
 }
 private static Context context(ServerPlayer player,BlockPos origin){
  var tiles=connected(player,origin);
  TabletopBlockEntity seat=seat(tiles,player);
  HandBlockEntity hand=linkedHand(player,seat);
  DeckControlBlockEntity deck=hand!=null?HandLogic.linkedControl(player,hand):null;
  GraveyardBlockEntity grave=hand!=null?HandLogic.findGraveyard(player,hand):null;
  return new Context(tiles,seat,hand,deck,grave);
 }
 private static TabletopBlockEntity tile(Context c,BlockPos pos){
  for(var t:c.tiles)if(t.getBlockPos().equals(pos))return t;
  return null;
 }
 private static Located located(Context c,String id){
  if(id==null||id.length()>40)return null;
  for(var t:c.tiles){var card=t.find(id);if(card!=null)return new Located(t,card);}
  return null;
 }
 private static int emptySlot(GraveyardBlockEntity grave,int start){
  if(grave==null)return -1;for(int i=start;i<start+100;i++)if(grave.getStack(i).isEmpty())return i;return -1;
 }
 private static int freeSlots(GraveyardBlockEntity grave,int start){
  if(grave==null)return 0;int n=0;for(int i=start;i<start+100;i++)if(grave.getStack(i).isEmpty())n++;return n;
 }
 private static boolean owned(ServerPlayer p,Located card){
  return card!=null&&p.getUUID().toString().equals(card.card.owner());
 }
 private static String requireLinks(Context c){
  if(c.hand==null)return "Place your Card Hand within 8 blocks of your seat and link it to a Deck Control.";
  if(c.deck==null)return "Your Card Hand's linked Deck Control is missing.";
  return "";
 }
 public static void handle(ServerPlayer player,TabletopWire.Request req){
  Context c=context(player,req.pos());
  if(c.tiles.isEmpty())return;
  String message="";
  if(req.action().equals("refresh")){reply(player,req.pos(),"");return;}
  if(c.seat==null){reply(player,req.pos(),"Claim an empty tabletop seat to play.");return;}
  if(!List.of("move","tap","hide","return","grave","exile").contains(req.action())&&c.hand==null){
   reply(player,req.pos(),requireLinks(c));return;
  }
  try{
   switch(req.action()){
    case "put_hand" -> {
     TabletopBlockEntity dest=tile(c,req.target());
     int idx=req.amount();
     if(dest==null||dest.cards().size()>=TabletopBlockEntity.MAX_CARDS){message="That spot is unavailable or full.";break;}
     if(c.hand.pendingStrictDiscards()>0){message="Finish strict mulligan discards first.";break;}
     if(idx<0||idx>=c.hand.cardCount()){message="Select a card in your hand.";break;}
     ItemStack card=c.hand.removeVisibleIndex(idx);
     if(card.isEmpty()){message="The hand changed. Choose the card again.";break;}
     if(!dest.add(new TabletopBlockEntity.PlayedCard(UUID.randomUUID().toString(),player.getUUID().toString(),card.copy(),req.x(),req.y(),false,false))){
      c.hand.restore(card);message="Could not place that card.";break;
     }
     message="Played a card.";
    }
    case "put_grave", "put_exile" -> {
     if(c.grave==null){message="No Graveyard is touching your Deck Control.";break;}
     int slot=req.amount(),start=req.action().equals("put_exile")?100:0;
     TabletopBlockEntity dest=tile(c,req.target());
     if(slot<start||slot>=start+100||dest==null||dest.cards().size()>=TabletopBlockEntity.MAX_CARDS){message="Invalid zone card or destination.";break;}
     ItemStack card=c.grave.getStack(slot);
     if(card.isEmpty()){message="That card is no longer in the zone.";break;}
     ItemStack moved=card.copyWithCount(1);
     if(!dest.add(new TabletopBlockEntity.PlayedCard(UUID.randomUUID().toString(),player.getUUID().toString(),moved,req.x(),req.y(),false,false))){
      message="Could not place that card.";break;
     }
     ItemStack remaining=card.copy();remaining.shrink(1);
     c.grave.setStack(slot,remaining);
     message="Card returned to the battlefield.";
    }
    case "move" -> {
     Located found=located(c,req.ref());
     TabletopBlockEntity dest=tile(c,req.target());
     if(!owned(player,found)||dest==null){message="You may only move your own cards within this table.";break;}
     var updated=found.card.moved(req.x(),req.y());
     if(found.tile==dest){dest.replace(updated);message="Card moved.";break;}
     if(!dest.add(updated)){message="Destination tile is full.";break;}
     found.tile.remove(found.card.id());
     message="Card moved.";
    }
    case "tap", "hide" -> {
     Located found=located(c,req.ref());
     if(!owned(player,found)){message="Only the card's owner can change it.";break;}
     found.tile.replace(req.action().equals("tap")?found.card.tapped(!found.card.tapped()):found.card.hidden(!found.card.faceDown()));
     message=req.action().equals("tap")?"Card tapped / untapped.":"Card face changed.";
    }
    case "return" -> {
     Located found=located(c,req.ref());
     if(!owned(player,found)){message="Only your own cards can return to hand.";break;}
     if(c.hand==null||c.hand.cardCount()>=HandBlockEntity.SIZE||!c.hand.addCard(found.card.stack())){message="Your Card Hand is missing or full.";break;}
     found.tile.remove(found.card.id());message="Card returned to your private hand.";
    }
    case "grave", "exile" -> {
     Located found=located(c,req.ref());
     if(!owned(player,found)){message="You can only move your own cards into a zone.";break;}
     int slot=emptySlot(c.grave,req.action().equals("exile")?100:0);
     if(slot<0){message="No linked Graveyard or the target zone is full.";break;}
     c.grave.setStack(slot,found.card.stack().copy());
     found.tile.remove(found.card.id());
     message=req.action().equals("exile")?"Exiled card.":"Card sent to graveyard.";
    }
    case "zone_to_hand" -> {
     if(c.grave==null){message="No linked Graveyard.";break;}
     int slot=req.amount();if(slot<0||slot>=200){message="Invalid zone card.";break;}
     ItemStack stack=c.grave.getStack(slot);
     if(stack.isEmpty()||c.hand.cardCount()>=HandBlockEntity.SIZE){message="The zone card is missing or the hand is full.";break;}
     ItemStack one=stack.copyWithCount(1);
     if(!c.hand.addCard(one)){message="Could not add that card to your hand.";break;}
     ItemStack rest=stack.copy();rest.shrink(1);c.grave.setStack(slot,rest);
     message="Moved card to hand.";
    }
    case "draw" -> {
     if(c.deck==null){message=requireLinks(c);break;}
     int count=Math.clamp(req.amount(),1,20),room=HandBlockEntity.SIZE-c.hand.cardCount();
     if(room<count){message="Not enough room in the Card Hand.";break;}
     List<ItemStack> drawn=c.deck.takeTopCards(count);
     for(ItemStack card:drawn)if(!c.hand.addCard(card))throw new IllegalStateException("Card Hand rejected a Deck Control card.");
     message="Drew "+drawn.size()+" card(s) into your hand.";
    }
    case "mill" -> {
     if(c.deck==null){message=requireLinks(c);break;}
     int count=Math.clamp(req.amount(),1,20);
     if(freeSlots(c.grave,0)<count){message="The graveyard needs "+count+" free slots to mill safely.";break;}
     List<ItemStack> milled=c.deck.takeTopCards(count);
     for(ItemStack stack:milled){
      int slot=emptySlot(c.grave,0);
      if(slot<0)throw new IllegalStateException("Graveyard filled during milling");
      c.grave.setStack(slot,stack);
     }
     message="Milled "+milled.size()+" card(s) to your graveyard.";
    }
    case "shuffle" -> {if(c.deck==null){message=requireLinks(c);break;}c.deck.shuffle();SCRIES.remove(player.getUUID());message="Shuffled your library.";}
    case "scry_begin" -> {
     if(c.deck==null){message=requireLinks(c);break;}
     int count=Math.clamp(req.amount(),1,7);
     List<ItemStack> preview=c.deck.peekTopCopies(count);
     if(preview.isEmpty()){message="Your library is empty.";break;}
     SCRIES.put(player.getUUID(),new ScrySession(c.deck.getBlockPos(),List.copyOf(preview)));
     message="Scry "+preview.size()+": choose which cards stay on top.";
    }
    case "scry_cancel" -> {SCRIES.remove(player.getUUID());message="Scry closed; library order unchanged.";}
    case "scry_commit" -> {
     ScrySession session=SCRIES.get(player.getUUID());
     if(session==null||c.deck==null||!session.control.equals(c.deck.getBlockPos())){message="Scry session has expired.";break;}
     List<ItemStack> current=c.deck.peekTopCopies(session.cards.size());
     if(current.size()!=session.cards.size()){message="Library changed; scry cancelled.";SCRIES.remove(player.getUUID());break;}
     boolean matching=true;
     for(int i=0;i<current.size();i++)if(!ItemStack.isSameItemSameComponents(current.get(i),session.cards.get(i)))matching=false;
     if(!matching){message="Library changed; scry cancelled.";SCRIES.remove(player.getUUID());break;}
     String[] sides=req.ref().split("\\|",-1);
     if(sides.length!=2){message="Invalid scry order.";break;}
     List<Integer> order=new ArrayList<>();int tops=0;boolean valid=true;
     for(int side=0;side<2;side++){
      if(!sides[side].isEmpty())for(String raw:sides[side].split(",")){
       try{int n=Integer.parseInt(raw);if(n<0||n>=current.size()||order.contains(n)){valid=false;break;}order.add(n);}
       catch(NumberFormatException e){valid=false;break;}
      }
      if(side==0)tops=order.size();
     }
     if(!valid||order.size()!=current.size()){message="Invalid scry order.";break;}
     c.deck.resolveOrderedScry(current.size(),tops,order.stream().mapToInt(Integer::intValue).toArray(),false);
     SCRIES.remove(player.getUUID());message="Scry resolved.";
    }
    default -> message="Unknown tabletop action.";
   }
  }catch(Exception e){
   org.slf4j.LoggerFactory.getLogger("caszual_mtg").error("Tabletop action failed",e);
   message="Tabletop action failed; see server log.";
  }
  reply(player,req.pos(),message);
 }

 private static void reply(ServerPlayer player,BlockPos origin,String message){
  Context c=context(player,origin);
  if(c.tiles.isEmpty())return;
  BlockPos owned=c.seat==null?origin:c.seat.getBlockPos();
  String uuid=player.getUUID().toString();
  List<TabletopWire.Tile> tiles=new ArrayList<>();
  List<TabletopWire.Card> played=new ArrayList<>();
  for(var t:c.tiles){
   tiles.add(new TabletopWire.Tile(t.getBlockPos(),t.seatName()));
   for(var card:t.cards()){
    // Face-down card identities must never leave the server for opponents.
    ItemStack shown=card.faceDown()&&!uuid.equals(card.owner())?ItemStack.EMPTY:card.stack().copy();
    played.add(new TabletopWire.Card(t.getBlockPos(),card.id(),card.owner(),shown,card.x(),card.y(),card.tapped(),card.faceDown()));
   }
  }
  List<TabletopWire.ZoneCard> grave=new ArrayList<>(),exile=new ArrayList<>();
  if(c.grave!=null&&c.seat!=null){
   for(int i=0;i<200;i++){
    ItemStack stack=c.grave.getStack(i);
    if(!stack.isEmpty())(i<100?grave:exile).add(new TabletopWire.ZoneCard(i,stack.copy()));
   }
  }
  ScrySession session=SCRIES.get(player.getUUID());
  List<ItemStack> scry=session!=null&&c.deck!=null&&session.control.equals(c.deck.getBlockPos())?session.cards:List.of();
  ServerPlayNetworking.send(player,new TabletopWire.Reply(
   origin,message,owned,List.copyOf(tiles),List.copyOf(played),
   c.hand==null||c.seat==null?List.of():c.hand.visibleCards(),
   c.deck==null?0:c.deck.getLibraryCount(),List.copyOf(grave),List.copyOf(exile),scry
  ));
 }
 private TabletopLogic(){}
}
