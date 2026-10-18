package dev.casz.caszualmtg;

import com.spider.mtgcard.deckcontrol.DeckControlBlockEntity;
import com.spider.mtgcard.deckbox.DeckboxBlockEntity;
import com.spider.mtgcard.life.LifePointBlockEntity;
import com.spider.mtgcard.life.LifePlayGroups;
import com.spider.mtgcard.util.TcgCardMeta;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.network.chat.Component;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.entity.EntityTypes;
import net.minecraft.world.entity.ai.attributes.Attributes;
import net.minecraft.world.entity.animal.IronGolem;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.phys.AABB;

import java.util.*;

/**
 * Deliberately limited server-only AI pilot. Each golem owns a virtual tabletop
 * seat + an otherwise-unclaimed Card Hand. It never impersonates a ServerPlayer.
 * Only physically represented cards are moved; unsupported spells stay in hand.
 */
public final class CommanderGolems {
 public static final String TAG="caszual_mtg_commander_golem";
 private static final String FIRST_HAND="caszual_mtg_ai_opening_hand";
 private static final String ACTION_DONE="caszual_mtg_ai_turn_processed";
 private static final int RANGE=5;
 private CommanderGolems(){}

 public static String place(ServerLevel level,BlockPos chair,ServerPlayer placer){
  if(!(level.getBlockState(chair).getBlock() instanceof ChairBlock))
   return "Place the golem on a Caszual MTG chair.";
  TabletopBlockEntity table=adjacentTable(level,chair);
  if(table==null)return "Place a Caszual MTG tabletop immediately beside the chair.";
  if(table.seatOwner()!=null)return "That tabletop seat is already claimed.";
  AABB seatBox=new AABB(chair).inflate(.25);
  if(!level.getEntitiesOfClass(IronGolem.class,seatBox,
    golem->golem.getTags().contains(TAG)).isEmpty())return "That chair has an AI golem already.";
  IronGolem golem=new IronGolem(EntityTypes.IRON_GOLEM,level);
  golem.addTag(TAG);
  golem.setCustomName(Component.literal("Commander Golem"));
  golem.setCustomNameVisible(true);
  golem.setNoAi(true);
  golem.setNoGravity(true);
  golem.setSilent(true);
  golem.setPersistenceRequired();
  // A small, stationary iron golem fits the slab-height seat.
  var scale=golem.getAttribute(Attributes.SCALE);
  if(scale!=null)scale.setBaseValue(.36);
  golem.setPos(chair.getX()+.5,chair.getY()+.5,chair.getZ()+.5);
  var state=level.getBlockState(chair);
  Direction facing=state.getValue(ChairBlock.FACING);
  golem.setYRot(facing.toYRot());
  if(!level.addFreshEntity(golem))return "The golem could not be spawned.";
  if(!table.claim(golem.getUUID(),"Commander Golem")){
   golem.discard();return "That table seat is not available.";
  }
  return "Commander Golem seated. Place an unused Card Hand, linked Deck Control, deckbox and Life Point near its table; use the golem to check status.";
 }

 private static TabletopBlockEntity adjacentTable(ServerLevel level,BlockPos chair){
  for(Direction d:Direction.Plane.HORIZONTAL){
   if(level.getBlockEntity(chair.relative(d)) instanceof TabletopBlockEntity table)return table;
  }
  return null;
 }
 private static BlockPos chairFor(ServerLevel level,IronGolem golem){
  BlockPos pos=golem.blockPosition();
  for(BlockPos at:BlockPos.betweenClosed(pos.offset(-1,-1,-1),pos.offset(1,1,1)))
   if(level.getBlockState(at).getBlock() instanceof ChairBlock){
    if(Math.abs(at.getX()+.5-golem.getX())<.7 &&Math.abs(at.getZ()+.5-golem.getZ())<.7)
     return at.immutable();
   }
  return null;
 }
 private record Setup(TabletopBlockEntity table,HandBlockEntity hand,DeckControlBlockEntity deck,
                      LifePointBlockEntity life) {}
 private static Setup setup(ServerLevel world,IronGolem golem,boolean bind){
  BlockPos chair=chairFor(world,golem);
  if(chair==null)return new Setup(null,null,null,null);
  TabletopBlockEntity table=adjacentTable(world,chair);
  if(table==null||!golem.getUUID().equals(table.seatOwner()))
   return new Setup(null,null,null,null);
  BlockPos at=table.getBlockPos();
  HandBlockEntity hand=null;
  DeckControlBlockEntity control=null;
  LifePointBlockEntity life=null;
  double hd=Double.MAX_VALUE,cd=Double.MAX_VALUE,ld=Double.MAX_VALUE;
  for(BlockPos p:BlockPos.betweenClosed(at.offset(-RANGE,-2,-RANGE),at.offset(RANGE,2,RANGE))){
   if(!world.hasChunkAt(p))continue;
   var be=world.getBlockEntity(p);
   double distance=at.distSqr(p);
   if(be instanceof HandBlockEntity h && (golem.getUUID().equals(h.owner()) || h.owner()==null)
      && distance<hd){hand=h;hd=distance;}
   if(be instanceof DeckControlBlockEntity dc && dc.getLinkedDeckboxPos()!=null
      && distance<cd){control=dc;cd=distance;}
   if(be instanceof LifePointBlockEntity lp && distance<ld){life=lp;ld=distance;}
  }
  if(hand!=null && bind && hand.owner()==null){
   if(control==null)return new Setup(table,null,null,life);
   hand.claimBot(golem.getUUID(),"Commander Golem");
   hand.linkedControl(control.getBlockPos());
   if(life!=null)hand.linkedLife(life.getBlockPos());
  }
  if(hand!=null&&!golem.getUUID().equals(hand.owner()))hand=null;
  if(hand!=null&&hand.linkedControl()!=null && world.getBlockEntity(hand.linkedControl()) instanceof DeckControlBlockEntity assigned)
   control=assigned;
  if(hand!=null&&hand.linkedLife()!=null && world.getBlockEntity(hand.linkedLife()) instanceof LifePointBlockEntity assigned)
   life=assigned;
  return new Setup(table,hand,control,life);
 }
 public static String status(ServerLevel level,IronGolem golem){
  Setup s=setup(level,golem,true);
  if(s.table==null)return "Golem seat or chair missing; it cannot join the table.";
  if(s.hand==null)return "Golem waiting for an unclaimed Card Hand within 5 blocks.";
  if(s.deck==null)return "Golem waiting for a Deck Control linked to a placed deckbox.";
  BlockPos db=s.deck.getLinkedDeckboxPos();
  if(db==null||!(level.getBlockEntity(db) instanceof DeckboxBlockEntity box))
   return "Golem waiting for a linked deckbox.";
  if(box.getStack(DeckboxBlockEntity.SECOND_SIDE_SLOT).isEmpty())
   return "Insert a legal commander in the deckbox Commander slot.";
  if(s.life==null)return "Golem waiting for a Life Point block within 5 blocks.";
  if(!s.life.isGameStarted())return "Golem ready. Start a game with the linked Life Point counters.";
  return "Golem "+(s.life.isTurnActive()?"is taking its turn":"is waiting")+" | life "+s.life.getLife()
    +" | hand "+s.hand.cardCount()+" | library "+s.deck.getLibraryCount()+".";
 }

 /** Tick only near online players, once per second. No chunk loading or background NPC activity. */
 public static void tick(ServerLevel world){
  if(world.getGameTime()%20!=0)return;
  Set<UUID> visited=new HashSet<>();
  for(ServerPlayer player:world.players()){
   for(IronGolem golem:world.getEntitiesOfClass(IronGolem.class,
       player.getBoundingBox().inflate(32),g->g.getTags().contains(TAG))){
    if(!visited.add(golem.getUUID()))continue;
    run(world,golem);
   }
  }
 }
 private static void run(ServerLevel world,IronGolem golem){
  Setup s=setup(world,golem,true);
  if(s.table==null||s.hand==null||s.deck==null||s.life==null)return;
  if(!s.life.isGameStarted()||s.life.getLife()<=0){
   golem.removeTag(ACTION_DONE);return;
  }
  BlockPos boxPos=s.deck.getLinkedDeckboxPos();
  if(boxPos==null||!(world.getBlockEntity(boxPos) instanceof DeckboxBlockEntity box)
    ||box.getStack(DeckboxBlockEntity.SECOND_SIDE_SLOT).isEmpty())return;
  if(!golem.getTags().contains(FIRST_HAND)){
   // Seven cards from the actual MTGCard Deck Control's library order.
   if(s.deck.getLibraryCount()<7||s.hand.cardCount()!=0)return;
   for(ItemStack card:s.deck.takeTopCards(7))s.hand.addCard(card);
   golem.addTag(FIRST_HAND);
   s.table.rememberCommander(box.getStack(DeckboxBlockEntity.SECOND_SIDE_SLOT));
  }
  if(!s.life.isTurnActive()){
   golem.removeTag(ACTION_DONE);
   return;
  }
  if(golem.getTags().contains(ACTION_DONE))return;
  golem.addTag(ACTION_DONE); // idempotent across ticks and world saves
  // Untap only the golem's cards, not an opponent's; then draw once.
  for(var card:s.table.cards())if(golem.getUUID().toString().equals(card.owner())&&card.tapped())
   s.table.replace(card.tapped(false));
  for(ItemStack card:s.deck.takeTopCards(1))s.hand.addCard(card);
  // Conservative Commander turn: one basic/nonbasic land from Hand in a main phase.
  // We intentionally do not auto-cast spells without mana/stack/priority validation.
  List<ItemStack> cards=s.hand.visibleCards();
  for(int i=0;i<cards.size();i++){
   ItemStack c=cards.get(i);
   String type=TcgCardMeta.read(c).typeLine().toLowerCase(Locale.ROOT);
   if(!type.contains("land")||type.contains("creature")||type.contains("spell"))continue;
   if(s.table.cards().size()>=TabletopBlockEntity.MAX_CARDS)break;
   ItemStack moved=s.hand.removeVisibleIndex(i);
   if(moved.isEmpty())break;
   var played=new TabletopBlockEntity.PlayedCard(UUID.randomUUID().toString(),
     golem.getUUID().toString(),moved,280+(s.table.cards().size()%5)*90,700,false,false);
   if(!s.table.add(played))s.hand.addCard(moved);
   break;
  }
  // This experiment does not resolve the stack, combat, activated abilities,
  // commander tax or unknown oracle text. Pass rather than fabricate an illegal cast.
  LifePlayGroups.passTurn(world,s.life.getBlockPos());
 }
}
