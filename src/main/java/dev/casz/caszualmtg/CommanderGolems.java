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
 /** Persistent scoreboard tags; one server tick per visible turn stage. */
 private static final String STAGE_LAND="caszual_mtg_ai_stage_land";
 private static final String STAGE_CAST="caszual_mtg_ai_stage_cast";
 private static final String STAGE_COMBAT="caszual_mtg_ai_stage_combat";
 private static final String STAGE_END="caszual_mtg_ai_stage_end";
 private static void clearTurn(IronGolem golem){
  golem.removeTag(ACTION_DONE);
  golem.removeTag(STAGE_LAND);
  golem.removeTag(STAGE_CAST);
  golem.removeTag(STAGE_COMBAT);
  golem.removeTag(STAGE_END);
 }
 private static void progress(IronGolem golem,String oldStage,String nextStage){
  if(oldStage!=null)golem.removeTag(oldStage);
  if(nextStage!=null)golem.addTag(nextStage);
 }
 /** Deliberately do not reveal cards still in the private Card Hand. */
 private static void say(ServerLevel world,IronGolem golem,String message){
  Component notice=Component.literal("[Commander Golem] "+message);
  for(ServerPlayer viewer:world.players())
   if(viewer.distanceToSqr(golem)<=32*32)viewer.sendSystemMessage(notice);
 }
 private static String phase(IronGolem golem){
  if(golem.entityTags().contains(STAGE_LAND))return "playing a land";
  if(golem.entityTags().contains(STAGE_CAST))return "casting creatures";
  if(golem.entityTags().contains(STAGE_COMBAT))return "declaring combat";
  if(golem.entityTags().contains(STAGE_END)||golem.entityTags().contains(ACTION_DONE))return "cleaning up";
  return "drawing";
 }
 private static final int RANGE=8;
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
  CommanderGolemVisuals.ensure(level,golem);
  return "Brass Squire Commander Golem seated. Link a Card Hand to its table, Deck Control and Life Point, then select this golem as primary.";
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
  HandBlockEntity hand=HandLinks.linked(world,table,golem.getUUID());
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
 /** Actionable diagnostics for hands already linked to this exact seat.
  * Never modify a player's ownership or silently rebind any Card Hand. */
 private static String missingHand(ServerLevel world,IronGolem golem,TabletopBlockEntity seat){
  BlockPos at=seat.getBlockPos();
  BlockPos precise=seat.linkedHand();
  if(precise!=null){
   if(!HandLinks.inTableRange(precise,at))
    return "Linked Card Hand is more than 70 blocks from the Golem's table.";
   if(!world.hasChunkAt(precise))
    return "Linked Card Hand is 70 blocks or less away, but its chunk is not loaded.";
   if(world.getBlockEntity(precise) instanceof HandBlockEntity exact){
    if(exact.owner()==null)return "Linked Card Hand's primary is unassigned. Use Links / Primary > Assign Seated Golem.";
    if(!golem.getUUID().equals(exact.owner()))
     return "Linked Card Hand's primary is "+exact.primaryName()+", not this Golem.";
    if(!at.equals(exact.linkedTable()))
     return "Table and Card Hand links do not agree. Relink this table from the Card Hand.";
   }
   return "The saved Card Hand position no longer contains a valid linked Hand. Relink it.";
  }
  HandBlockEntity wrongPrimary=null,unassigned=null,wrongSeat=null;
  for(BlockPos p:BlockPos.betweenClosed(at.offset(-RANGE,-RANGE,-RANGE),
                                      at.offset(RANGE,RANGE,RANGE))){
   if(!world.hasChunkAt(p)||!(world.getBlockEntity(p) instanceof HandBlockEntity h))continue;
   if(at.equals(h.linkedTable())||h.legacyTableDiscovery()&&h.linkedTable()==null){
    if(h.owner()==null)unassigned=h;
    else if(!golem.getUUID().equals(h.owner()))wrongPrimary=h;
   }else if(golem.getUUID().equals(h.owner()))wrongSeat=h;
  }
  if(unassigned!=null)return "Card Hand at "+unassigned.getBlockPos().toShortString()+
   " is linked to this table, but Primary is unassigned. Open Links / Primary and select the seated Golem.";
  if(wrongPrimary!=null)return "Card Hand at "+wrongPrimary.getBlockPos().toShortString()+
   " is linked, but Primary is "+wrongPrimary.primaryName()+
   ", not this Golem. Use Links / Primary > Select Golem.";
  if(wrongSeat!=null)return "This Golem's Card Hand at "+wrongSeat.getBlockPos().toShortString()+
   " is linked to a different table. Re-link it to this occupied seat.";
  return "No assigned Card Hand found within 70 blocks of this Golem's table. "+
    "Link the Hand to this table, then use Links / Primary > Select Golem.";
 }
 public static String status(ServerLevel level,IronGolem golem){
  Setup s=setup(level,golem,true);
  if(s.table==null)return "Golem seat or chair missing; it cannot join the table.";
  if(s.hand==null)return missingHand(level,golem,s.table);
  if(s.deck==null)return "Link the Golem Hand to a Deck Control and its deckbox.";
  BlockPos db=s.deck.getLinkedDeckboxPos();
  if(db==null||!(level.getBlockEntity(db) instanceof DeckboxBlockEntity box))
   return "Golem waiting for a linked deckbox.";
  if(!golem.entityTags().contains(FIRST_HAND)
    &&box.getStack(DeckboxBlockEntity.SECOND_SIDE_SLOT).isEmpty())
   return "Insert a legal commander in the deckbox Commander slot.";
  if(!golem.entityTags().contains(FIRST_HAND)){
   String reason=deckError(box);
   if(reason!=null)return reason;
  }
  if(s.life==null)return "Link the Golem Hand to its dedicated Life Point counter.";
  CommanderPod.Status pod=CommanderPod.status(level,s.life);
  if(!pod.member()){
   String attempt=CommanderPod.joinNearbyPod(level,s.table,s.life);
   pod=CommanderPod.status(level,s.life);
   if(!pod.member())return "Golem Life Point is not connected to a pod. "+attempt;
  }
  if(!pod.started())return "Golem joined pod '"+pod.name()+"'. Opening hand: "+
    (golem.entityTags().contains(FIRST_HAND)?"ready":"waiting")+"; start the pod when players are ready.";
  if(pod.rolling())return "Pod '"+pod.name()+"' is choosing the first turn. Golem is waiting.";
  if(s.table.aiAttack()!=null)return "Commander Golem is waiting for the defender to choose a block or take damage.";
  int incoming=incomingTargets(level,golem,s.table);
  return "Pod: "+pod.name()+" ("+pod.memberCount()+" players) | "+
    (pod.active()?"Golem's turn":"Waiting for its turn")+" | life "+s.life.getLife()
    +" | hand "+s.hand.cardCount()+" | library "+s.deck.getLibraryCount()
    +" | "+(pod.active()?phase(golem):"inactive")+" | public targets aimed at me "+incoming+
    " (responses not implemented).";
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
   CommanderGolemVisuals.prune(world,player);
   for(IronGolem golem:world.getEntitiesOfClass(IronGolem.class,
       player.getBoundingBox().inflate(32),g->g.entityTags().contains(TAG))){
    if(!visited.add(golem.getUUID()))continue;
    CommanderGolemVisuals.ensure(world,golem);
    run(world,golem);
   }
  }
 }
 /** Draw exactly N real library cards into the virtual Card Hand. Never
  * take physical cards when the Hand has insufficient inventory space. */
 private static boolean drawIntoHand(DeckControlBlockEntity deck,HandBlockEntity hand,int count){
  if(count<=0||hand.cardCount()+count>HandBlockEntity.SIZE
    ||deck.getLibraryCount()<count)return false;
  List<ItemStack> drawn=deck.takeTopCards(count);
  if(drawn.size()!=count){
   if(!drawn.isEmpty())deck.putCardsOnBottom(drawn);
   return false;
  }
  for(ItemStack card:drawn){
   if(!hand.addCard(card))throw new IllegalStateException(
       "Commander Golem Card Hand lost a preflighted drawing slot.");
  }
  return true;
 }

 /** Execute once per real pod turn, not during the starting-player roulette. */
 private static void run(ServerLevel world,IronGolem golem){
  Setup s=setup(world,golem,true);
  if(s.table==null||s.hand==null||s.deck==null||s.life==null)return;
  CommanderPod.Status pod=CommanderPod.status(world,s.life);
  if(!pod.member()&&world.getGameTime()%200==0){
   CommanderPod.joinNearbyPod(world,s.table,s.life);
   pod=CommanderPod.status(world,s.life);
  }
  if(!pod.member())return;
  // Keep the exact linked Life Point in a persisted pod; never treat an
  // ungrouped counter's local turnActive flag as permission to act.
  if(pod.dead()||s.life.getLife()<=0)return;
  BlockPos boxPos=s.deck.getLinkedDeckboxPos();
  if(boxPos==null||!world.hasChunkAt(boxPos)
    ||!(world.getBlockEntity(boxPos) instanceof DeckboxBlockEntity box))return;
  if(!golem.entityTags().contains(FIRST_HAND)){
   if(box.getStack(DeckboxBlockEntity.SECOND_SIDE_SLOT).isEmpty())return;
   // Validate the full physical deck before drawing a single card.
   if(deckError(box)!=null||s.hand.cardCount()!=0)return;
   s.deck.shuffle();
   if(!drawIntoHand(s.deck,s.hand,7))return;
   golem.addTag(FIRST_HAND);
   s.table.rememberCommander(box.getStack(DeckboxBlockEntity.SECOND_SIDE_SLOT));
  }
  if(!pod.started()||pod.rolling()||!pod.active()){
   clearTurn(golem);
   return;
  }
  // Preserve old-build ACTION_DONE as a safe cleanup-only state rather than
  // replaying a draw when upgrading an active saved game.
  if(golem.entityTags().contains(STAGE_END)||
     golem.entityTags().contains(ACTION_DONE)&&
     !golem.entityTags().contains(STAGE_LAND)&&
     !golem.entityTags().contains(STAGE_CAST)&&
     !golem.entityTags().contains(STAGE_COMBAT)){
   if(s.table.aiAttack()!=null){
    if(world.getGameTime()%100==0){
     var attack=s.table.aiAttack();
     TabletopTargets.mark(world,golem.getUUID(),s.table.getBlockPos(),
      s.table.seatName(),attack.attackerId(),attack.defender(),"","attack");
    }
    return;
   }
   if(!CommanderBattleActions.cleanup(world,s.hand,s.deck)){
    // Never lose physical cards when there is no adjacent Graveyard space.
    return;
   }
   if(CommanderPod.status(world,s.life).playable()){
    say(world,golem,"passes the turn.");
    LifePlayGroups.passTurn(world,s.life.getBlockPos());
    // If MTGCard declined to advance, retain END state: never draw again.
    if(!CommanderPod.status(world,s.life).active())clearTurn(golem);
   }
   return;
  }

  if(golem.entityTags().contains(STAGE_COMBAT)){
   progress(golem,STAGE_COMBAT,STAGE_END);
   if(CommanderCombat.declare(world,golem,s.table,s.life)){
    say(world,golem,"declares an attack; waiting for the defender to block or take damage.");
    return;
   }
   return;
  }

  if(golem.entityTags().contains(STAGE_CAST)){
   progress(golem,STAGE_CAST,STAGE_COMBAT);
   int creatures=CommanderBattleActions.castHand(golem,s.table,s.hand);
   boolean commander=CommanderBattleActions.castCommander(golem,s.table,box);
   creatures+=CommanderBattleActions.castHand(golem,s.table,s.hand);
   if(creatures>0)say(world,golem,"casts "+creatures+" creature"+(creatures==1?"":"s")+".");
   if(commander)say(world,golem,"casts its commander.");
   if(creatures==0&&!commander)say(world,golem,"has no supported creature spell it can pay for.");
   return;
  }

  if(golem.entityTags().contains(STAGE_LAND)){
   progress(golem,STAGE_LAND,STAGE_CAST);
   int previous=s.table.cards().size();
   boolean placed=CommanderBattleActions.playLand(golem,s.table,s.hand);
   if(placed&&s.table.cards().size()>previous)
    say(world,golem,"plays "+TcgCardMeta.displayName(s.table.cards().getLast().stack())+".");
   return;
  }

  // Start of a *new* real pod turn: mark next stage BEFORE drawing, so a
  // chunk unload/restart never plays or draws the same turn twice.
  golem.addTag(ACTION_DONE);
  golem.addTag(STAGE_LAND);
  CommanderBattleActions.untapAndMarkReady(golem,s.table);
  if(s.deck.getLibraryCount()==0){
   say(world,golem,"cannot draw from an empty library and loses.");
   LifePlayGroups.setDead(world,s.life.getBlockPos(),true);
   clearTurn(golem);
   return;
  }
  if(!drawIntoHand(s.deck,s.hand,1)){
   if(s.hand.cardCount()==HandBlockEntity.SIZE
     &&CommanderBattleActions.cleanup(world,s.hand,s.deck)
     &&drawIntoHand(s.deck,s.hand,1)){
    say(world,golem,"discards down to hand size, then draws one card.");
    return;
   }
   // A missing/full physical Graveyard blocks the draw safely. No duplicate
   // cards are created or removed; retry next tick if the blocker clears.
   clearTurn(golem);
   return;
  }
  say(world,golem,"draws a card ("+s.hand.cardCount()+" in hand).");
 }
}
