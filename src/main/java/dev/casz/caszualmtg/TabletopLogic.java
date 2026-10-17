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
 private record TokenQuery(String text,int page) {}
 private record TokenPage(TokenQuery query,List<TabletopWire.TokenResult> cards,boolean more) {}
 private static final int TOKEN_PAGE_SIZE=8;
 private record ScrySession(BlockPos control,List<ItemStack> cards) {}
 private record Located(TabletopBlockEntity tile,TabletopBlockEntity.PlayedCard card) {}
 private record Context(List<TabletopBlockEntity> tiles,TabletopBlockEntity seat,HandBlockEntity hand,DeckControlBlockEntity deck,GraveyardBlockEntity grave) {}

 public static void close(ServerPlayer player){SCRIES.remove(player.getUUID());REVEALS.remove(player.getUUID());TOKEN_QUERIES.remove(player.getUUID());TOKEN_RESULTS.remove(player.getUUID());}
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
  if(!List.of("move","tap","untap_all","hide","flip","return","grave","exile","commander_home","pass_turn","counter_set","token_query","token_add","token_play","token_store","token_remove","quick_send","copy_token").contains(req.action())&&c.hand==null){
   reply(player,req.pos(),requireLinks(c));return;
  }
  try{
   switch(req.action()){
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
     // Catalogue pages are 40 cards; the tabletop tray displays EIGHT per
     // page. Fetch each 40-card batch and select the matching eight directly.
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
        Banks.get(player.level().getServer()).add(token,1,1); // Offline fallback.
       }
       boolean more=result.cards().size()>finish||result.hasMore();
       TOKEN_RESULTS.put(player.getUUID(),new TokenPage(current,List.copyOf(tokens),more));
       reply(player,req.pos(),tokens.isEmpty()?"No token matches on this page.":"Found "+tokens.size()+" tokens. Select one to save to your tray.");
      }));
    }
    case "token_add" -> {
     if(c.seat.tokenTray().size()>=TabletopBlockEntity.MAX_TOKEN_TEMPLATES){message="Token tray full (32 templates).";break;}
     TokenQuery query=TOKEN_QUERIES.getOrDefault(player.getUUID(),new TokenQuery("",0));
  TokenPage loaded=TOKEN_RESULTS.get(player.getUUID());
  List<TabletopWire.TokenResult> tokenResults=new ArrayList<>();
  boolean tokenMore;
  if(loaded!=null&&loaded.query().equals(query)){
   tokenResults.addAll(loaded.cards());
   tokenMore=loaded.more();
  }else{
   // Offline search is still useful before the first online lookup completes.
   var matches=Banks.get(player.level().getServer()).search(1,query.text());
   int offset=query.page()*TOKEN_PAGE_SIZE;
   for(int i=offset;i<Math.min(matches.size(),offset+TOKEN_PAGE_SIZE);i++)
    tokenResults.add(new TabletopWire.TokenResult(matches.get(i).getKey(),matches.get(i).getValue().card().copy()));
   tokenMore=matches.size()>offset+TOKEN_PAGE_SIZE;
  }
  ServerPlayNetworking.send(player,new TabletopWire.Reply(
   origin,message,owned,List.copyOf(tiles),List.copyOf(played),
   c.hand==null||c.seat==null?List.of():c.hand.visibleCards(),
   c.deck==null?0:c.deck.getLibraryCount(),List.copyOf(grave),List.copyOf(exile),scry,reveal,commander(player,c),
   c.seat==null?List.of():c.seat.tokenTray(),List.copyOf(tokenResults),query.page(),tokenMore
  ));
 }
 private TabletopLogic(){}
}
