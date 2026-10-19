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
import net.minecraft.world.entity.animal.golem.IronGolem;
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
    golem->golem.entityTags().contains(TAG)).isEmpty())return "That chair has an AI golem already.";
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
  // The manager chooses all four bindings; the AI never steals nearby
  // unassigned Hands, counters, Deck Controls or somebody else's table.
  HandBlockEntity hand=null;double nearest=Double.MAX_VALUE;
  BlockPos at=table.getBlockPos();
  for(BlockPos p:BlockPos.betweenClosed(at.offset(-RANGE,-2,-RANGE),at.offset(RANGE,2,RANGE))){
   if(!world.hasChunkAt(p))continue;
   if(world.getBlockEntity(p) instanceof HandBlockEntity h
      &&golem.getUUID().equals(h.owner())&&at.equals(h.linkedTable())){
    double d=at.distSqr(p);if(d<nearest){hand=h;nearest=d;}
   }
  }
  DeckControlBlockEntity control=null;
  LifePointBlockEntity life=null;
  if(hand!=null){
   BlockPos deckPos=hand.linkedControl(),lifePos=hand.linkedLife();
   if(deckPos!=null&&world.hasChunkAt(deckPos)&&world.getBlockEntity(deckPos) instanceof DeckControlBlockEntity dc)control=dc;
   if(lifePos!=null&&world.hasChunkAt(lifePos)&&world.getBlockEntity(lifePos) instanceof LifePointBlockEntity lp)life=lp;
  }
  return new Setup(table,hand,control,life);
 }
 /** Public intent directed at the AI. This is observation only, not resolution:
  * the bot must not auto-counter, block, or react until priority is implemented. */
 private static int incomingTargets(ServerLevel world,IronGolem golem,TabletopBlockEntity root){
  ArrayDeque<BlockPos> queue=new ArrayDeque<>();
  Set<BlockPos> seen=new HashSet<>();
  List<TabletopBlockEntity> tiles=new ArrayList<>();
  queue.add(root.getBlockPos());seen.add(root.getBlockPos());
  while(!queue.isEmpty()&&tiles.size()<32){
   BlockPos pos=queue.removeFirst();
   if(!world.hasChunkAt(pos)||!(world.getBlockEntity(pos) instanceof TabletopBlockEntity tile))continue;
   tiles.add(tile);
   for(Direction direction:Direction.Plane.HORIZONTAL){
    BlockPos next=pos.relative(direction);
    if(seen.add(next))queue.add(next);
   }
  }
  return (int)TabletopTargets.visible(world,tiles).stream()
   .filter(t->!t.actor().equals(golem.getUUID())
    &&t.targetSeat().equals(root.getBlockPos())).count();
 }
 public static String status(ServerLevel level,IronGolem golem){
  Setup s=setup(level,golem,true);
  if(s.table==null)return "Golem seat or chair missing; it cannot join the table.";
  if(s.hand==null)return "Golem needs a Hand explicitly linked to its table and assigned to this golem.";
  if(s.deck==null)return "Link the Golem Hand to a Deck Control and its deckbox.";
  BlockPos db=s.deck.getLinkedDeckboxPos();
  if(db==null||!(level.getBlockEntity(db) instanceof DeckboxBlockEntity box))
   return "Golem waiting for a linked deckbox.";
  if(box.getStack(DeckboxBlockEntity.SECOND_SIDE_SLOT).isEmpty())
   return "Insert a legal commander in the deckbox Commander slot.";
  if(!golem.entityTags().contains(FIRST_HAND)){
   String reason=deckError(box);
   if(reason!=null)return reason;
  }
  if(s.life==null)return "Link the Golem Hand to its dedicated Life Point counter.";
  if(!s.life.isGameStarted())return "Golem ready. Join Commander Golem's Life Point counter to the play group, then start the game.";
  if(s.table.aiAttack()!=null)return "Commander Golem is waiting for the defender to choose a block or take damage.";
  int incoming=incomingTargets(level,golem,s.table);
  return "Golem "+(s.life.isTurnActive()?"is taking its turn":"is waiting")+" | life "+s.life.getLife()
    +" | hand "+s.hand.cardCount()+" | library "+s.deck.getLibraryCount()
    +" | public targets aimed at me "+incoming+" (responses not implemented).";
 }

 /** Validate the physical deck and color identity before the first shuffle/draw.
  * Partner / Background and card-specific deck-size exceptions are not supported yet. */
 private static String deckError(DeckboxBlockEntity box){
  ItemStack commander=box.getStack(DeckboxBlockEntity.SECOND_SIDE_SLOT);
  if(commander.isEmpty())return "Missing commander in the deckbox Commander slot.";
  var commanderMeta=TcgCardMeta.read(commander);
  if(!com.spider.mtgcard.cards.CardNbt.isCommanderLegal(commander))
   return "This deckbox does not contain an eligible Commander.";
  List<CommanderRules.Card> list=new ArrayList<>();
  int color=mask(commanderMeta.colorIdentity());
  CommanderRules.Card leader=new CommanderRules.Card(
   TcgCardMeta.displayName(commander),commanderMeta.typeLine(),color,true);
  list.add(leader);
  for(int i=0;i<DeckboxBlockEntity.MAIN_SLOTS;i++){
   ItemStack card=box.getStack(i);
   if(card.isEmpty())return "Commander Golem needs exactly 99 main-deck cards and one commander.";
   var meta=TcgCardMeta.read(card);
   if("banned".equalsIgnoreCase(meta.commanderLegality()))
    return "Commander banned card: "+TcgCardMeta.displayName(card);
   list.add(new CommanderRules.Card(TcgCardMeta.displayName(card),
      meta.typeLine(),mask(meta.colorIdentity()),false));
  }
  List<String> errors=CommanderRules.validateDeck(list,List.of(leader));
  return errors.isEmpty()?null:errors.getFirst();
 }
 private static int mask(Set<String> colors){
  int out=0;
  for(String color:colors)out|=switch(color.toUpperCase(Locale.ROOT)){
   case "W"->1;case "U"->2;case "B"->4;case "R"->8;case "G"->16;default->0;
  };
  return out;
 }
 /** Tick only near online players, once per second. No chunk loading or background NPC activity. */
 public static void tick(ServerLevel world){
  if(world.getGameTime()%20!=0)return;
  Set<UUID> visited=new HashSet<>();
  for(ServerPlayer player:world.players()){
   for(IronGolem golem:world.getEntitiesOfClass(IronGolem.class,
       player.getBoundingBox().inflate(32),g->g.entityTags().contains(TAG))){
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
  if(!golem.entityTags().contains(FIRST_HAND)){
   // Verify a single-commander 100-card deck before removing anything.
   if(deckError(box)!=null)return;
   // Shuffle the physical library before the opening seven.
   if(s.deck.getLibraryCount()<7||s.hand.cardCount()!=0)return;
   s.deck.shuffle();
   for(ItemStack card:s.deck.takeTopCards(7))s.hand.addCard(card);
   golem.addTag(FIRST_HAND);
   s.table.rememberCommander(box.getStack(DeckboxBlockEntity.SECOND_SIDE_SLOT));
  }
  if(!s.life.isTurnActive()){
   golem.removeTag(ACTION_DONE);
   return;
  }
  // If a missing Graveyard blocked cleanup, retry only cleanup. The opening
  // draw and land play must not happen twice on the same turn.
  if(golem.entityTags().contains(ACTION_DONE)){
   var combat=s.table.aiAttack();
   if(combat!=null){
    if(world.getGameTime()%100==0)TabletopTargets.mark(world,golem.getUUID(),
     s.table.getBlockPos(),s.table.seatName(),combat.attackerId(),combat.defender(),"","attack");
    return; // Never advance the turn while another player is deciding blocks.
   }
   if(CommanderBattleActions.cleanup(world,s.hand,s.deck))
    LifePlayGroups.passTurn(world,s.life.getBlockPos());
   return;
  }
  golem.addTag(ACTION_DONE);
  // Mark creatures that survived to this untap as old enough to attack.
  CommanderBattleActions.untapAndMarkReady(golem,s.table);
  if(s.deck.getLibraryCount()==0){
   LifePlayGroups.setDead(world,s.life.getBlockPos(),true);
   return;
  }
  for(ItemStack card:s.deck.takeTopCards(1))s.hand.addCard(card);
  CommanderBattleActions.playLand(golem,s.table,s.hand);
  CommanderBattleActions.castHand(golem,s.table,s.hand);
  CommanderBattleActions.castCommander(golem,s.table,box);
  CommanderBattleActions.castHand(golem,s.table,s.hand);
  if(CommanderCombat.declare(world,golem,s.table,s.life))return;
  if(CommanderBattleActions.cleanup(world,s.hand,s.deck))
   LifePlayGroups.passTurn(world,s.life.getBlockPos());
 }
}
