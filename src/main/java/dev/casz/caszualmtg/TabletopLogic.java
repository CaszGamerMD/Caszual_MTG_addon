package dev.casz.caszualmtg;

import com.spider.mtgcard.deckcontrol.DeckControlBlockEntity;
import com.spider.mtgcard.graveyard.GraveyardBlockEntity;
import com.spider.mtgcard.life.LifePointBlockEntity;
import com.spider.mtgcard.life.LifePlayGroups;
import com.spider.mtgcard.deckbox.DeckboxBlockEntity;
import net.minecraft.server.level.ServerLevel;
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
 private static final Map<UUID,ScrySession> REVEALS=new ConcurrentHashMap<>();
 private record ScrySession(BlockPos control,List<ItemStack> cards) {}
 private record Located(TabletopBlockEntity tile,TabletopBlockEntity.PlayedCard card) {}
 private record Context(List<TabletopBlockEntity> tiles,TabletopBlockEntity seat,HandBlockEntity hand,DeckControlBlockEntity deck,GraveyardBlockEntity grave) {}

 public static void close(ServerPlayer player){SCRIES.remove(player.getUUID());REVEALS.remove(player.getUUID());}
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
  return linkedHand(player,seat,player.getUUID());
 }
 private static HandBlockEntity linkedHand(ServerPlayer player,TabletopBlockEntity seat,UUID owner){
  if(seat==null)return null;
  BlockPos at=seat.getBlockPos();HandBlockEntity best=null;double distance=Double.MAX_VALUE;
  for(BlockPos p:BlockPos.betweenClosed(at.offset(-LINK_RANGE,-LINK_RANGE,-LINK_RANGE),at.offset(LINK_RANGE,LINK_RANGE,LINK_RANGE))){
   if(!player.level().hasChunkAt(p))continue;
   if(player.level().getBlockEntity(p) instanceof HandBlockEntity h
      &&owner.equals(h.owner())){
    double d=at.distSqr(p);
    if(d<distance){best=h;distance=d;}
   }
  }
  return best;
 }
 private static LifePointBlockEntity life(ServerPlayer player,HandBlockEntity hand){
  if(hand==null||hand.linkedLife()==null||!player.level().hasChunkAt(hand.linkedLife()))return null;
  return player.level().getBlockEntity(hand.linkedLife()) instanceof LifePointBlockEntity lp?lp:null;
 }
 private static DeckboxBlockEntity commanderBox(ServerPlayer player,Context c){
  if(c.deck==null)return null;
  BlockPos pos=c.deck.getLinkedDeckboxPos();
  return pos!=null&&player.level().getBlockEntity(pos) instanceof DeckboxBlockEntity db?db:null;
 }
 private static ItemStack commander(ServerPlayer player,Context c){
  DeckboxBlockEntity db=commanderBox(player,c);
  return db==null?ItemStack.EMPTY:db.getStack(DeckboxBlockEntity.SECOND_SIDE_SLOT).copy();
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
  if(id==null||id.isEmpty()||id.length()>TabletopWire.MAX_CARD_ID_LENGTH)return null;
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
  if(!List.of("move","tap","hide","flip","return","grave","exile","commander_home","pass_turn").contains(req.action())&&c.hand==null){
   reply(player,req.pos(),requireLinks(c));return;
  }
  try{
   switch(req.action()){
    case "pass_turn" -> {
     LifePointBlockEntity lp=life(player,c.hand);
     if(lp==null){message="Link your MTGCard Life Point block in your Card Hand first.";break;}
     if(!lp.isGameStarted()||!lp.isTurnActive()){message="Only the active player may pass their turn.";break;}
     if(!(player.level() instanceof ServerLevel server)){message="Server unavailable.";break;}
     LifePlayGroups.passTurn(server,lp.getBlockPos());
     message="Turn passed to the next player.";
    }
    case "play_commander" -> {
     TabletopBlockEntity dest=tile(c,req.target());
     DeckboxBlockEntity box=commanderBox(player,c);
     if(dest==null||dest.cards().size()>=TabletopBlockEntity.MAX_CARDS){message="That battlefield is full.";break;}
     if(box==null){message="No deckbox connected to your Deck Control.";break;}
     ItemStack stack=box.getStack(DeckboxBlockEntity.SECOND_SIDE_SLOT);
     if(stack.isEmpty()||!stack.is(com.spider.mtgcard.item.ModItemTags.TCG_CARD)){message="Put your commander into the Deckbox Commander slot first.";break;}
     ItemStack one=stack.copyWithCount(1);
     var card=new TabletopBlockEntity.PlayedCard("commander:"+UUID.randomUUID(),player.getUUID().toString(),one,req.x(),req.y(),false,false);
     if(!dest.add(card)){message="Could not place commander.";break;}
     c.seat.rememberCommander(one);
     ItemStack remaining=stack.copy();remaining.shrink(1);
     box.setStack(DeckboxBlockEntity.SECOND_SIDE_SLOT,remaining);box.sync();
     message="Commander played.";
    }
    case "commander_home" -> {
     Located found=located(c,req.ref());
     if(!owned(player,found)||!found.card.id().startsWith("commander:")){message="Only your commander can return to your command zone.";break;}
     DeckboxBlockEntity box=commanderBox(player,c);
     if(box==null||!box.getStack(DeckboxBlockEntity.SECOND_SIDE_SLOT).isEmpty()){
      message="The deckbox Commander slot is occupied or missing.";break;
     }
     box.setStack(DeckboxBlockEntity.SECOND_SIDE_SLOT,found.card.stack().copy());box.sync();
     found.tile.remove(found.card.id());message="Commander returned to the deckbox Commander slot.";
    }
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
    case "tap", "hide", "flip" -> {
     Located found=located(c,req.ref());
     if(!owned(player,found)){message="Only the card's owner can change it.";break;}
     if(req.action().equals("tap")){
      found.tile.replace(found.card.tapped(!found.card.tapped()));
      message="Card tapped / untapped.";
     }else{
      int count=com.spider.mtgcard.util.TcgCardMeta.faceCount(found.card.stack());
      if(count>1){
       ItemStack flipped=found.card.stack().copy();
       int next=(com.spider.mtgcard.util.TcgCardMeta.read(flipped).face()+1)%count;
       com.spider.mtgcard.util.StackData.writeFace(flipped,next);
       var old=found.card;
       found.tile.replace(new TabletopBlockEntity.PlayedCard(old.id(),old.owner(),flipped,old.x(),old.y(),old.tapped(),false));
       message="Showing card face "+(next+1)+" of "+count+".";
      }else{
       found.tile.replace(found.card.hidden(!found.card.faceDown()));
       message=found.card.faceDown()?"Card face up.":"Card face down.";
      }
     }
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
     int count=Math.clamp(req.amount(),1,99),room=HandBlockEntity.SIZE-c.hand.cardCount();
     if(room<count){message="Not enough room in the Card Hand.";break;}
     List<ItemStack> drawn=c.deck.takeTopCards(count);
     for(ItemStack card:drawn)if(!c.hand.addCard(card))throw new IllegalStateException("Card Hand rejected a Deck Control card.");
     message="Drew "+drawn.size()+" card(s) into your hand.";
    }
    case "mill" -> {
     if(c.deck==null){message=requireLinks(c);break;}
     int count=Math.clamp(req.amount(),1,99);
     if(freeSlots(c.grave,0)<count){message="The graveyard needs "+count+" free slots to mill safely.";break;}
     List<ItemStack> milled=c.deck.takeTopCards(count);
     for(ItemStack stack:milled){
      int slot=emptySlot(c.grave,0);
      if(slot<0)throw new IllegalStateException("Graveyard filled during milling");
      c.grave.setStack(slot,stack);
     }
     message="Milled "+milled.size()+" card(s) to your graveyard.";
    }
    case "shuffle" -> {
     if(c.deck==null){message=requireLinks(c);break;}
     if(REVEALS.containsKey(player.getUUID())){message="Finish the reveal before shuffling.";break;}
     c.deck.shuffle();SCRIES.remove(player.getUUID());message="Shuffled your library.";
    }
    case "search_deck" -> {
     DeckboxBlockEntity box=commanderBox(player,c);
     if(box==null){message="No linked deckbox. Attach one to your Deck Control.";break;}
     player.openMenu(box);
     message="Opened linked deckbox.";
    }
    case "reset" -> message=reset(player,c);
    case "mulligan_friendly","mulligan_strict","mulligan_finish" -> message=mulligan(player,c,req.action());
    case "mulligan_discard" -> {
     if(c.hand==null||c.hand.pendingStrictDiscards()<=0){message="No strict mulligan discards are owed.";break;}
     int index=req.amount(),slot=emptySlot(c.grave,0);
     if(slot<0){message="Link a Graveyard with a free slot.";break;}
     if(index<0||index>=c.hand.cardCount()){message="Choose a card to discard from your hand.";break;}
     ItemStack card=c.hand.removeVisibleIndex(index);
     if(card.isEmpty()){message="Selected card no longer in hand.";break;}
     c.grave.setStack(slot,card);
     c.hand.consumeStrictDiscard();
     message="Discarded for mulligan. Remaining: "+c.hand.pendingStrictDiscards();
    }
    case "reveal_begin" -> {
     if(c.deck==null){message=requireLinks(c);break;}
     if(REVEALS.containsKey(player.getUUID())){message="Finish the current reveal first.";break;}
     int count=Math.clamp(req.amount(),1,20);
     List<ItemStack> shown=c.deck.peekTopCopies(count);
     if(shown.isEmpty()){message="Library is empty.";break;}
     REVEALS.put(player.getUUID(),new ScrySession(c.deck.getBlockPos(),List.copyOf(shown)));
     message="Revealed "+shown.size()+" cards. Take the top card or shuffle all revealed cards to the bottom.";
    }
    case "reveal_to_hand","reveal_to_field","reveal_end" -> message=resolveReveal(player,c,req);
    case "scry_begin" -> {
     if(c.deck==null){message=requireLinks(c);break;}
     int count=Math.clamp(req.amount(),1,20);
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


 /** Match Card Hand's friendly / strict mulligan behavior. */
 private static String mulligan(ServerPlayer player,Context c,String action){
  if(c.hand==null||c.deck==null)return requireLinks(c);
  if("mulligan_finish".equals(action)){
   c.hand.finishStrictMulligans();
   int owed=c.hand.pendingStrictDiscards();
   return owed>0?"Mulligan complete: discard "+owed+" card(s) from Hand.":"Mulligan complete.";
  }
  if(c.hand.pendingStrictDiscards()>0)return "Finish your strict mulligan discards first.";
  if(REVEALS.containsKey(player.getUUID()))return "Finish the deck reveal before mulligan.";
  List<ItemStack> returned=c.hand.takeAllCards();
  if(!returned.isEmpty())c.deck.putCardsOnBottom(returned);
  c.deck.shuffle();
  SCRIES.remove(player.getUUID());
  for(ItemStack card:c.deck.takeTopCards(7))c.hand.addCard(card);
  if("mulligan_strict".equals(action)){
   int tries=c.hand.addStrictMulligan();
   return "Strict mulligan #"+tries+": drew seven. Finish mulligans, then discard required cards.";
  }
  c.hand.resetMulligans();
  return "Friendly mulligan: hand shuffled back and seven new cards drawn.";
 }

 /** The reveal is just a *view* of the real library until its resolution.
  * Cards are physically removed once, then unused copies returned shuffled to the bottom. */
 private static String resolveReveal(ServerPlayer player,Context c,TabletopWire.Request req){
  ScrySession session=REVEALS.get(player.getUUID());
  if(session==null||c.deck==null||!session.control.equals(c.deck.getBlockPos()))
   return "No active reveal.";
  List<ItemStack> actual=c.deck.peekTopCopies(session.cards.size());
  if(actual.size()!=session.cards.size()){
   REVEALS.remove(player.getUUID());return "Library changed; reveal expired.";
  }
  for(int i=0;i<actual.size();i++)if(!ItemStack.isSameItemSameComponents(actual.get(i),session.cards.get(i))){
   REVEALS.remove(player.getUUID());return "Library changed; reveal expired.";
  }
  boolean toHand=req.action().equals("reveal_to_hand"),toField=req.action().equals("reveal_to_field");
  if(toHand&&(c.hand==null||c.hand.cardCount()>=HandBlockEntity.SIZE))return "Card Hand is full.";
  TabletopBlockEntity dest=toField?tile(c,req.target()):null;
  if(toField&&(dest==null||dest.cards().size()>=TabletopBlockEntity.MAX_CARDS))return "Battlefield is unavailable or full.";
  List<ItemStack> cards=new ArrayList<>(c.deck.takeTopCards(actual.size()));
  if(cards.size()!=actual.size()){
   if(!cards.isEmpty())c.deck.putCardsOnBottom(cards);
   REVEALS.remove(player.getUUID());
   return "Library changed during reveal. Remaining removed cards returned to library.";
  }
  ItemStack top=cards.removeFirst();
  if(toHand&&!c.hand.addCard(top)){
   cards.add(top);Collections.shuffle(cards);c.deck.putCardsOnBottom(cards);
   REVEALS.remove(player.getUUID());return "Hand rejected card; all revealed cards returned to library.";
  }
  if(toField&&!dest.add(new TabletopBlockEntity.PlayedCard(UUID.randomUUID().toString(),
    player.getUUID().toString(),top,req.x(),req.y(),false,false))){
   cards.add(top);Collections.shuffle(cards);c.deck.putCardsOnBottom(cards);
   REVEALS.remove(player.getUUID());return "Battlefield rejected card; all revealed cards returned to library.";
  }
  if(!toHand&&!toField)cards.add(top);
  Collections.shuffle(cards);
  c.deck.putCardsOnBottom(cards);
  REVEALS.remove(player.getUUID());
  return toHand?"Top revealed card moved to Hand; remainder shuffled to library bottom."
    :toField?"Top revealed card played; remainder shuffled to library bottom."
    :"All revealed cards shuffled to library bottom.";
 }

 private static boolean sameCommander(ItemStack stack,ItemStack reference){
  if(stack.isEmpty()||reference.isEmpty())return false;
  String a=com.spider.mtgcard.util.TcgCardMeta.read(stack).id();
  String b=com.spider.mtgcard.util.TcgCardMeta.read(reference).id();
  if(!a.isBlank()&&!b.isBlank())return a.equals(b);
  return ItemStack.isSameItemSameComponents(stack,reference);
 }

 /** Reset only the requesting player. Preflight deckbox capacity before touching
  * played cards, their Hand, or the GY/Exile; the reveal contains views, not items. */
 private static String reset(ServerPlayer player,Context c){
  if(c.deck==null||c.hand==null)return requireLinks(c);
  DeckboxBlockEntity box=commanderBox(player,c);
  if(box==null)return "Cannot reset: the linked deckbox is missing.";
  UUID owner=player.getUUID();
  ItemStack reference=c.seat.commanderReference();
  ItemStack inCommand=box.getStack(DeckboxBlockEntity.SECOND_SIDE_SLOT);
  if(reference.isEmpty()&&!inCommand.isEmpty())reference=inCommand.copyWithCount(1);
  List<Located> battlefield=new ArrayList<>();
  for(var t:c.tiles)for(var card:t.cards())if(owner.toString().equals(card.owner())){
   battlefield.add(new Located(t,card));
   if(reference.isEmpty()&&card.id().startsWith("commander:"))
    reference=card.stack().copyWithCount(1);
  }
  List<ItemStack> hand=c.hand.visibleCards();
  List<TabletopWire.ZoneCard> zones=new ArrayList<>();
  if(c.grave!=null)for(int i=0;i<200;i++){
   ItemStack stack=c.grave.getStack(i);
   if(!stack.isEmpty())zones.add(new TabletopWire.ZoneCard(i,stack.copy()));
  }
  // Determine a single physical commander that isn't already in the command zone.
  ItemStack commanderReturn=ItemStack.EMPTY;
  List<ItemStack> returning=new ArrayList<>();
  for(var entry:battlefield){
   ItemStack card=entry.card.stack();
   if(inCommand.isEmpty()&&commanderReturn.isEmpty()
       &&(entry.card.id().startsWith("commander:")||sameCommander(card,reference)))
    commanderReturn=card.copy();
   else returning.add(card.copy());
  }
  for(var card:hand){
   if(inCommand.isEmpty()&&commanderReturn.isEmpty()&&sameCommander(card,reference))
    commanderReturn=card.copy();
   else returning.add(card.copy());
  }
  for(var entry:zones){
   ItemStack card=entry.stack();
   if(inCommand.isEmpty()&&commanderReturn.isEmpty()&&sameCommander(card,reference))
    commanderReturn=card.copy();
   else returning.add(card.copy());
  }
  int sourceMainSlot=-1;
  if(inCommand.isEmpty()&&commanderReturn.isEmpty()&&!reference.isEmpty()){
   for(int i=0;i<DeckboxBlockEntity.MAIN_SLOTS;i++)
    if(sameCommander(box.getStack(i),reference)){sourceMainSlot=i;commanderReturn=box.getStack(i).copy();break;}
  }
  int spaces=0;
  for(int i=0;i<DeckboxBlockEntity.MAIN_SLOTS;i++)if(box.getStack(i).isEmpty())spaces++;
  if(sourceMainSlot>=0)spaces++;
  if(returning.size()>spaces)
   return "Reset blocked: "+returning.size()+" cards and only "+spaces+" free library slots. No cards moved.";
  // Commit all zone moves only after checking destination capacities.
  if(sourceMainSlot>=0)box.setStack(sourceMainSlot,ItemStack.EMPTY);
  if(!commanderReturn.isEmpty()){
   box.setStack(DeckboxBlockEntity.SECOND_SIDE_SLOT,commanderReturn);
   c.seat.rememberCommander(commanderReturn);
  }else if(!inCommand.isEmpty())c.seat.rememberCommander(inCommand);
  for(var entry:battlefield)entry.tile.remove(entry.card.id());
  c.hand.takeAllCards();
  for(var entry:zones)c.grave.setStack(entry.slot(),ItemStack.EMPTY);
  if(!returning.isEmpty())c.deck.putCardsOnBottom(returning);
  REVEALS.remove(owner);SCRIES.remove(owner);
  c.hand.resetMulligans();
  c.deck.shuffle();
  return "Reset complete: "+returning.size()+" cards returned and library shuffled"
   +(inCommand.isEmpty()&&!commanderReturn.isEmpty()?"; commander restored.":".");
 }

 public static void refreshColor(ServerPlayer player,HandBlockEntity hand){
  if(hand==null||hand.owner()==null)return;
  BlockPos at=hand.getBlockPos();
  int rgb=StaffColors.rgb(hand.tableColor());
  var desired=nearestDye(rgb);
  for(BlockPos pos:BlockPos.betweenClosed(at.offset(-LINK_RANGE,-LINK_RANGE,-LINK_RANGE),
                                        at.offset(LINK_RANGE,LINK_RANGE,LINK_RANGE))){
   if(!player.level().hasChunkAt(pos))continue;
   if(!(player.level().getBlockEntity(pos) instanceof TabletopBlockEntity tile))continue;
   if(!hand.owner().equals(tile.seatOwner()))continue;
   var state=tile.getBlockState();
   if(state.hasProperty(TabletopBlock.FELT)&&state.getValue(TabletopBlock.FELT)!=desired)
    player.level().setBlock(pos,state.setValue(TabletopBlock.FELT,desired),3);
  }
 }
 private static net.minecraft.world.item.DyeColor nearestDye(int rgb){
  net.minecraft.world.item.DyeColor[] choices=net.minecraft.world.item.DyeColor.values();
  int[] palette={0xF9FFFE,0xF9801D,0xC74EBD,0x3AB3DA,0xFED83D,0x80C71F,0xF38BAA,0x474F52,0x9D9D97,0x169C9C,0x8932B8,0x3C44AA,0x835432,0x5E7C16,0xB02E26,0x1D1D21};
  int min=Integer.MAX_VALUE;net.minecraft.world.item.DyeColor best=net.minecraft.world.item.DyeColor.GREEN;
  for(net.minecraft.world.item.DyeColor dye:choices){
   int c=palette[Math.clamp(dye.getId(),0,15)];
   int dr=(rgb>>16&255)-(c>>16&255),dg=(rgb>>8&255)-(c>>8&255),db=(rgb&255)-(c&255);
   int d=dr*dr+dg*dg+db*db;
   if(d<min){min=d;best=dye;}
  }
  return best;
 }
 private static void reply(ServerPlayer player,BlockPos origin,String message){
  Context c=context(player,origin);
  if(c.tiles.isEmpty())return;
  BlockPos owned=c.seat==null?origin:c.seat.getBlockPos();
  String uuid=player.getUUID().toString();
  List<TabletopWire.Tile> tiles=new ArrayList<>();
  List<TabletopWire.Card> played=new ArrayList<>();
  for(var t:c.tiles){
   HandBlockEntity other=t.seatOwner()==null?null:linkedHand(player,t,t.seatOwner());
   LifePointBlockEntity lp=life(player,other);
   int color=other!=null?StaffColors.rgb(other.tableColor()):0x315348;
   var state=t.getBlockState();
   if(state.hasProperty(TabletopBlock.FELT)){
    var desired=nearestDye(color);
    if(state.getValue(TabletopBlock.FELT)!=desired)player.level().setBlock(t.getBlockPos(),state.setValue(TabletopBlock.FELT,desired),3);
   }
   tiles.add(new TabletopWire.Tile(t.getBlockPos(),t.seatName(),color,lp==null?0:lp.getLife(),lp!=null,lp!=null&&lp.isTurnActive()));
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
  ScrySession revealSession=REVEALS.get(player.getUUID());
  List<ItemStack> reveal=revealSession!=null&&c.deck!=null&&revealSession.control.equals(c.deck.getBlockPos())?revealSession.cards:List.of();
  ServerPlayNetworking.send(player,new TabletopWire.Reply(
   origin,message,owned,List.copyOf(tiles),List.copyOf(played),
   c.hand==null||c.seat==null?List.of():c.hand.visibleCards(),
   c.deck==null?0:c.deck.getLibraryCount(),List.copyOf(grave),List.copyOf(exile),scry,reveal,commander(player,c)
  ));
 }
 private TabletopLogic(){}
}
