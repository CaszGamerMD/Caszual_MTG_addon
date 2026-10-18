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
 private static final Map<UUID,TokenQuery> TOKEN_QUERIES=new ConcurrentHashMap<>();
 private static final Map<UUID,TokenPage> TOKEN_RESULTS=new ConcurrentHashMap<>();
 private static final Set<UUID> REVEALED_HANDS=ConcurrentHashMap.newKeySet();
 private record TokenQuery(String text,int page) {}
 private record TokenPage(TokenQuery query,List<TabletopWire.TokenResult> cards,boolean more) {}
 private static final int TOKEN_PAGE_SIZE=8;
 private record ScrySession(BlockPos control,List<ItemStack> cards) {}
 private record Located(TabletopBlockEntity tile,TabletopBlockEntity.PlayedCard card) {}
 private record Context(List<TabletopBlockEntity> tiles,TabletopBlockEntity seat,HandBlockEntity hand,DeckControlBlockEntity deck,GraveyardBlockEntity grave) {}

 public static void close(ServerPlayer player){SCRIES.remove(player.getUUID());REVEALS.remove(player.getUUID());TOKEN_QUERIES.remove(player.getUUID());TOKEN_RESULTS.remove(player.getUUID());REVEALED_HANDS.remove(player.getUUID());}
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
  if(!List.of("move","tap","untap_all","hide","flip","return","grave","exile","commander_home","pass_turn","counter_set","token_query","token_add","token_play","token_store","token_remove","quick_send","copy_token","scry_cancel","reveal_hand","card_scale").contains(req.action())&&c.hand==null){
   reply(player,req.pos(),requireLinks(c));return;
  }
  try{
   switch(req.action()){
    case "card_scale" -> {
     TabletopBlockEntity target=tile(c,req.target());
     if(target==null||!target.ownedBy(player)||!target.getBlockPos().equals(c.seat.getBlockPos())){
      message="Only the table owner can resize this battlefield.";break;
     }
     // Delta, rather than arbitrary absolute size, means rapid wheel input
     // can be applied without losing steps to delayed network replies.
     if(req.amount()<-2||req.amount()>2||req.amount()==0){
      message="Invalid card-size adjustment.";break;
     }
     target.cardScale(target.cardScale()+req.amount()*5);
     message="Battlefield cards: "+target.cardScale()+"%.";
    }
    case "reveal_hand" -> {
     if(c.hand==null){message="Link a Card Hand to reveal it.";break;}
     if(!c.hand.owner().equals(player.getUUID())){message="You can only reveal your own hand.";break;}
     if(REVEALED_HANDS.remove(player.getUUID())){
      message="Hand hidden from other players.";
     }else{
      REVEALED_HANDS.add(player.getUUID());
      message="YOUR HAND IS REVEALED to other tabletop players.";
     }
    }
    case "hand_to_zone" -> {
     if(c.hand==null){message="No linked Card Hand.";break;}
     int split=req.ref().indexOf('|');
     if(split<0){message="Invalid hand destination.";break;}
     String zone=req.ref().substring(0,split),expected=req.ref().substring(split+1);
     if(!zone.equals("grave")&&!zone.equals("exile")){
      message="Invalid hand destination.";break;
     }
     int slot=req.amount(),start=zone.equals("exile")?100:0;
     if(slot<0||slot>=c.hand.cardCount()){message="Hand changed. Select the card again.";break;}
     ItemStack selected=c.hand.visibleCards().get(slot);
     String id=com.spider.mtgcard.util.TcgCardMeta.read(selected).id();
     if(id.isBlank())id=com.spider.mtgcard.util.TcgCardMeta.read(selected).name();
     if(!id.equals(expected)){message="Hand changed. Re-select and confirm the card.";break;}
     // Validate all preconditions before removing anything from the private hand.
     int target=emptySlot(c.grave,start);
     if(target<0){message="No linked Graveyard or the destination is full. Card stayed in hand.";break;}
     ItemStack taken=c.hand.removeVisibleIndex(slot);
     if(taken.isEmpty()){message="Hand changed. Card not moved.";break;}
     c.grave.setStack(target,taken);
     message=start==100?"Hand card moved to exile.":"Hand card sent to graveyard.";
    }
    case "copy_token" -> {
     Located found=located(c,req.ref());
     if(!owned(player,found)||found.card.faceDown()){
      message="Only your own face-up cards can be copied.";break;
     }
     TabletopBlockEntity dest=found.tile;
     if(dest.cards().size()>=TabletopBlockEntity.MAX_CARDS){
      message="That battlefield is full; no copy was created.";break;
     }
     ItemStack copy=com.spider.mtgcard.api.CardDatabaseCards.copyForExtraction(found.card.stack());
     // A copy retains the source artwork and card type, but not existing counters.
     for(String key:com.spider.mtgcard.util.CardCounterNbt.readCounterMap(copy).keySet())
      com.spider.mtgcard.util.CardCounterNbt.setCounter(copy,key,0);
     TabletopBlockEntity.PlayedCard original=found.card;
     if(!dest.add(new TabletopBlockEntity.PlayedCard("copy:"+UUID.randomUUID(),
       player.getUUID().toString(),copy,Math.clamp(original.x()+55,0,1000),
       Math.clamp(original.y()+35,0,1000),false,false))){
      message="Could not create token copy.";break;
     }
     message="Created a token copy. It disappears when it leaves the battlefield.";
    }
    case "counter_set" -> {
     int separator=req.ref().indexOf('|');
     if(separator<=0){message="Choose one of your battlefield cards.";break;}
     String id=req.ref().substring(0,separator),key=req.ref().substring(separator+1).trim().toLowerCase(Locale.ROOT);
     Located found=located(c,id);
     if(!owned(player,found)||found.card.faceDown()){message="Only the owner may edit face-up card counters.";break;}
     if(key.isEmpty()||key.length()>40||!key.matches("[a-z0-9 +/\\-]+")||req.amount()<0||req.amount()>1000000){
      message="Invalid counter name or total.";break;
     }
     ItemStack modified=found.card.stack().copy();
     com.spider.mtgcard.util.CardCounterNbt.setCounter(modified,key,req.amount());
     var card=found.card;
     found.tile.replace(new TabletopBlockEntity.PlayedCard(card.id(),card.owner(),modified,card.x(),card.y(),card.tapped(),card.faceDown()));
     message=req.amount()==0?"Removed "+key+" counters.":key+" counters: "+req.amount()+".";
    }
    case "token_query" -> {
     String name=req.ref().trim();
     if(name.length()>120){message="Token search must be 120 characters or shorter.";break;}
     int page=Math.clamp(req.amount(),0,50);
     TokenQuery current=new TokenQuery(name,page);
     TOKEN_QUERIES.put(player.getUUID(),current);
     TOKEN_RESULTS.remove(player.getUUID());
     message="Searching tokens (online; saved catalogue shown while loading)...";
     // Scryfall catalogue pages contain 40 tokens; the tabletop tray shows
     // eight at a time, so we fetch the correct 40-card batch and slice it.
     Catalogue.search(1,name,0,page/5).whenComplete((result,error)->
      player.level().getServer().execute(()->{
       if(player.isRemoved()||!current.equals(TOKEN_QUERIES.get(player.getUUID())))return;
       if(error!=null||result==null){
        reply(player,req.pos(),"Token search unavailable; showing previously saved tokens.");
        return;
       }
       List<TabletopWire.TokenResult> tokens=new ArrayList<>();
       int start=(page%5)*TOKEN_PAGE_SIZE,finish=Math.min(result.cards().size(),start+TOKEN_PAGE_SIZE);
       for(int i=start;i<finish;i++){
        var hit=result.cards().get(i);
        if(!Catalogue.isToken(hit.model().typeLine))continue;
        ItemStack token=com.spider.mtgcard.util.CardStackBuilders.buildScryfallStackFromModel(hit.model(),false);
        if(token.isEmpty())continue;
        tokens.add(new TabletopWire.TokenResult(Banks.key(1,token),token));
        Banks.get(player.level().getServer()).add(token,1,1);
       }
       boolean more=result.cards().size()>finish||result.hasMore();
       TOKEN_RESULTS.put(player.getUUID(),new TokenPage(current,List.copyOf(tokens),more));
       reply(player,req.pos(),tokens.isEmpty()?"No token matches on this page.":"Found "+tokens.size()+" tokens. Select one to save to your tray.");
      }));
    }
    case "token_add" -> {
     if(c.seat.tokenTray().size()>=TabletopBlockEntity.MAX_TOKEN_TEMPLATES){message="Token tray full (32 templates).";break;}
     TokenQuery query=TOKEN_QUERIES.getOrDefault(player.getUUID(),new TokenQuery("",0));
     TokenPage active=TOKEN_RESULTS.get(player.getUUID());
     ItemStack selected=ItemStack.EMPTY;
     if(active!=null&&query.equals(active.query())){
      for(var row:active.cards())if(row.key().equals(req.ref())){selected=row.stack();break;}
     }else{
      var results=Banks.get(player.level().getServer()).search(1,query.text());
      int from=query.page()*TOKEN_PAGE_SIZE;
      for(int i=from;i<Math.min(results.size(),from+TOKEN_PAGE_SIZE);i++)
       if(results.get(i).getKey().equals(req.ref())){selected=results.get(i).getValue().card();break;}
     }
     message=!selected.isEmpty()&&c.seat.addToken(selected)?"Token saved to your tray.":"Select an available token from the current search results.";
    }
    case "token_remove" -> message=c.seat.removeToken(req.amount())?"Removed token template.":"Invalid token slot.";
    case "token_play" -> {
     TabletopBlockEntity dest=tile(c,req.target());
     if(dest==null||dest.cards().size()>=TabletopBlockEntity.MAX_CARDS){message="Choose an open battlefield tile.";break;}
     ItemStack template=c.seat.tokenAt(req.amount());
     if(template.isEmpty()){message="Select a stored token first.";break;}
     ItemStack token=com.spider.mtgcard.api.CardDatabaseCards.copyForExtraction(template);
     if(!dest.add(new TabletopBlockEntity.PlayedCard("token:"+UUID.randomUUID(),player.getUUID().toString(),token,
       req.x(),req.y(),false,false))){message="Could not place token.";break;}
     message="Token placed. Template stays in tray.";
    }
    case "quick_send" -> {
     // Destination is determined exclusively by the server; the client cannot
     // disguise a commander or a token as an ordinary graveyard card.
     Located found=located(c,req.ref());
     if(!owned(player,found)){message="You can only quick-send your own battlefield cards.";break;}
     if(found.card.id().startsWith("copy:")){
      found.tile.remove(found.card.id());
      message="Token copy ceased to exist.";
      break;
     }
     ItemStack card=found.card.stack();
     boolean commander=found.card.id().startsWith("commander:")
      ||(!c.seat.commanderReference().isEmpty()&&sameCommander(card,c.seat.commanderReference()));
     if(commander){
      DeckboxBlockEntity box=commanderBox(player,c);
      if(box==null){message="No linked deckbox to receive your commander. Card was not moved.";break;}
      if(!box.getStack(DeckboxBlockEntity.SECOND_SIDE_SLOT).isEmpty()){
       message="Commander slot is occupied. Card was not moved.";break;
      }
      box.setStack(DeckboxBlockEntity.SECOND_SIDE_SLOT,TabletopCounters.leavingBattlefield(card));box.sync();
      found.tile.remove(found.card.id());
      message="Commander returned to command zone.";
     }else if(Catalogue.isToken(com.spider.mtgcard.util.TcgCardMeta.read(card).typeLine())){
      if(!c.seat.addToken(TabletopCounters.leavingBattlefield(card))){message="Token tray is full. Token remains on battlefield.";break;}
      found.tile.remove(found.card.id());
      message="Token returned to your tray.";
     }else{
      int slot=emptySlot(c.grave,0);
      if(slot<0){message="No linked Graveyard or no free slot. Card was not moved.";break;}
      c.grave.setStack(slot,TabletopCounters.leavingBattlefield(card));
      found.tile.remove(found.card.id());
      message="Card sent to graveyard.";
     }
    }
    case "token_store" -> {
     Located found=located(c,req.ref());
     if(owned(player,found)&&found.card.id().startsWith("copy:")){
      found.tile.remove(found.card.id());message="Token copy vanished; it was not saved to the tray.";break;
     }
     if(!owned(player,found)||!Catalogue.isToken(com.spider.mtgcard.util.TcgCardMeta.read(found.card.stack()).typeLine())){
      message="Only your token cards can return to the tray.";break;
     }
     if(!c.seat.addToken(TabletopCounters.leavingBattlefield(found.card.stack()))){message="Token tray full.";break;}
     found.tile.remove(found.card.id());
     message="Token returned to tray.";
    }
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
     box.setStack(DeckboxBlockEntity.SECOND_SIDE_SLOT,TabletopCounters.leavingBattlefield(found.card.stack()));box.sync();
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
    case "untap_all" -> {
     // Cards can span multiple connected tabletop blocks. Untap only this
     // player's cards, regardless of which battlefield view is currently open.
     String owner=player.getUUID().toString();
     int count=0;
     for(TabletopBlockEntity table:c.tiles)
      for(TabletopBlockEntity.PlayedCard card:table.cards())
       if(owner.equals(card.owner())&&card.tapped()){
        table.replace(card.tapped(false));
        count++;
       }
     message=count==0?"All your cards are already untapped.":"Untapped "+count+" of your cards.";
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
     if(found.card.id().startsWith("copy:")){
      found.tile.remove(found.card.id());message="Token copy vanished instead of entering your hand.";break;
     }
     if(c.hand==null||c.hand.cardCount()>=HandBlockEntity.SIZE||!c.hand.addCard(TabletopCounters.leavingBattlefield(found.card.stack()))){message="Your Card Hand is missing or full.";break;}
     found.tile.remove(found.card.id());message="Card returned to your private hand.";
    }
    case "grave", "exile" -> {
     Located found=located(c,req.ref());
     if(!owned(player,found)){message="You can only move your own cards into a zone.";break;}
     if(found.card.id().startsWith("copy:")){
      found.tile.remove(found.card.id());message="Token copy vanished instead of entering a zone.";break;
     }
     int slot=emptySlot(c.grave,req.action().equals("exile")?100:0);
     if(slot<0){message="No linked Graveyard or the target zone is full.";break;}
     c.grave.setStack(slot,TabletopCounters.leavingBattlefield(found.card.stack()));
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
    case "scry_cancel" -> {SCRIES.remove(player.getUUID());message="Scry cancelled; library order unchanged.";}
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
    reference=TabletopCounters.leavingBattlefield(card.stack()).copyWithCount(1);
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
   if(entry.card.id().startsWith("copy:"))continue;
   if(inCommand.isEmpty()&&commanderReturn.isEmpty()
       &&(entry.card.id().startsWith("commander:")||sameCommander(card,reference)))
    commanderReturn=TabletopCounters.leavingBattlefield(card);
   else if(!entry.card.id().startsWith("copy:")
      &&!Catalogue.isToken(com.spider.mtgcard.util.TcgCardMeta.read(card).typeLine()))returning.add(TabletopCounters.leavingBattlefield(card));
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
  for(BlockPos pos:BlockPos.betweenClosed(at.offset(-LINK_RANGE,-LINK_RANGE,-LINK_RANGE),
                                        at.offset(LINK_RANGE,LINK_RANGE,LINK_RANGE))){
   if(!player.level().hasChunkAt(pos))continue;
   if(!(player.level().getBlockEntity(pos) instanceof TabletopBlockEntity tile))continue;
   if(!hand.owner().equals(tile.seatOwner()))continue;
   tile.matRgb(rgb);
   ChairBlock.refreshNextToTable(player.level(),pos);
  }
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
   // Exact 24-bit seat color; legacy FELT blockstate is no longer used to tint.
   t.matRgb(color);
   ChairBlock.refreshNextToTable(player.level(),t.getBlockPos());
   tiles.add(new TabletopWire.Tile(t.getBlockPos(),t.seatName(),color,lp==null?0:lp.getLife(),lp!=null,lp!=null&&lp.isTurnActive(),t.cardScale()));
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
  TokenQuery query=TOKEN_QUERIES.getOrDefault(player.getUUID(),new TokenQuery("",0));
  TokenPage loaded=TOKEN_RESULTS.get(player.getUUID());
  List<TabletopWire.TokenResult> tokenResults=new ArrayList<>();
  boolean tokenMore;
  if(loaded!=null&&loaded.query().equals(query)){
   tokenResults.addAll(loaded.cards());
   tokenMore=loaded.more();
  }else{
   var matches=Banks.get(player.level().getServer()).search(1,query.text());
   int offset=query.page()*TOKEN_PAGE_SIZE;
   for(int i=offset;i<Math.min(matches.size(),offset+TOKEN_PAGE_SIZE);i++)
    tokenResults.add(new TabletopWire.TokenResult(matches.get(i).getKey(),matches.get(i).getValue().card().copy()));
   tokenMore=matches.size()>offset+TOKEN_PAGE_SIZE;
  }
  List<TabletopWire.ShownHand> shownHands=new ArrayList<>();
  for(TabletopBlockEntity t:c.tiles){
   UUID handOwner=t.seatOwner();
   if(handOwner==null||!REVEALED_HANDS.contains(handOwner))continue;
   HandBlockEntity revealed=linkedHand(player,t,handOwner);
   if(revealed==null)continue;
   shownHands.add(new TabletopWire.ShownHand(t.getBlockPos(),t.seatName(),revealed.visibleCards()));
  }
  // Only real deck reveal sessions linked to this exact player's seat
  // become public; scry and other private deck inspection stay private.
  List<TabletopWire.PublicReveal> publicReveals=new ArrayList<>();
  for(TabletopBlockEntity table:c.tiles){
   UUID owner=table.seatOwner();
   if(owner==null)continue;
   ScrySession publicSession=REVEALS.get(owner);
   if(publicSession==null)continue;
   HandBlockEntity ownerHand=linkedHand(player,table,owner);
   if(ownerHand==null)continue;
   DeckControlBlockEntity control=HandLogic.linkedControl(player,ownerHand);
   if(control==null||!publicSession.control().equals(control.getBlockPos()))continue;
   publicReveals.add(new TabletopWire.PublicReveal(table.getBlockPos(),table.seatName(),publicSession.cards()));
  }
  ServerPlayNetworking.send(player,new TabletopWire.Reply(
   origin,message,owned,List.copyOf(tiles),List.copyOf(played),
   c.hand==null||c.seat==null?List.of():c.hand.visibleCards(),
   c.deck==null?0:c.deck.getLibraryCount(),List.copyOf(grave),List.copyOf(exile),scry,reveal,commander(player,c),
   c.seat==null?List.of():c.seat.tokenTray(),List.copyOf(tokenResults),query.page(),tokenMore,REVEALED_HANDS.contains(player.getUUID()),List.copyOf(shownHands),List.copyOf(publicReveals)
  ));
 }
 private TabletopLogic(){}
}
