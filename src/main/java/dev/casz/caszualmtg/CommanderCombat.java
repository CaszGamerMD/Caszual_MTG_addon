package dev.casz.caszualmtg;

import com.spider.mtgcard.deckcontrol.DeckControlBlockEntity;
import com.spider.mtgcard.graveyard.GraveyardBlockEntity;
import com.spider.mtgcard.life.LifePointBlockEntity;
import com.spider.mtgcard.life.LifePlayGroups;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.entity.animal.golem.IronGolem;

import java.util.*;

/**
 * Experimental one-attacker/one-blocker Commander combat with deliberate
 * defender acknowledgement. No instant-speed stack or triggered abilities.
 * Unsupported keywords/power modifiers are rejected, never approximated.
 */
public final class CommanderCombat {
 private static final int MAX_TILES=32;
 private CommanderCombat(){}

 public static List<TabletopBlockEntity> connected(ServerLevel world,BlockPos origin){
  ArrayDeque<BlockPos> queue=new ArrayDeque<>();
  Set<BlockPos> seen=new HashSet<>();
  List<TabletopBlockEntity> out=new ArrayList<>();
  queue.add(origin.immutable());seen.add(origin);
  while(!queue.isEmpty()&&out.size()<MAX_TILES){
   BlockPos pos=queue.removeFirst();
   if(!world.hasChunkAt(pos)||!(world.getBlockEntity(pos) instanceof TabletopBlockEntity table))continue;
   out.add(table);
   for(Direction dir:Direction.Plane.HORIZONTAL){
    BlockPos next=pos.relative(dir);
    if(seen.add(next))queue.add(next);
   }
  }
  return List.copyOf(out);
 }
 static HandBlockEntity hand(ServerLevel level,TabletopBlockEntity seat){
  return seat==null?null:HandLinks.linked(level,seat,seat.seatOwner());
 }
 static DeckControlBlockEntity control(ServerLevel world,HandBlockEntity hand){
  BlockPos pos=hand==null?null:hand.linkedControl();
  return pos!=null&&world.hasChunkAt(pos)&&world.getBlockEntity(pos) instanceof DeckControlBlockEntity c?c:null;
 }
 static LifePointBlockEntity life(ServerLevel world,TabletopBlockEntity seat){
  HandBlockEntity hand=hand(world,seat);
  BlockPos pos=hand==null?null:hand.linkedLife();
  return pos!=null&&world.hasChunkAt(pos)&&world.getBlockEntity(pos) instanceof LifePointBlockEntity lp?lp:null;
 }
 private static boolean simple(TabletopBlockEntity.PlayedCard card){
  return card!=null&&!card.faceDown()&&TabletopCardStats.counters(card.stack()).isEmpty()
   &&CommanderBattleActions.traits(card.stack()).isPresent();
 }
 public static boolean declare(ServerLevel world,IronGolem bot,TabletopBlockEntity table,LifePointBlockEntity botLife){
  if(table.aiAttack()!=null||!botLife.isTurnActive())return false;
  UUID group=LifePlayGroups.findGroupId(world,botLife.getBlockPos());
  if(group==null)return false;
  List<TabletopBlockEntity> tiles=connected(world,table.getBlockPos());
  TabletopBlockEntity defender=null;int lowLife=Integer.MAX_VALUE;
  for(TabletopBlockEntity seat:tiles){
   UUID who=seat.seatOwner();
   if(who==null||who.equals(bot.getUUID())||world.getServer().getPlayerList().getPlayer(who)==null)continue;
   LifePointBlockEntity lp=life(world,seat);
   if(lp==null||lp.getLife()<=0||!group.equals(LifePlayGroups.findGroupId(world,lp.getBlockPos())))continue;
   if(lp.getLife()<lowLife){lowLife=lp.getLife();defender=seat;}
  }
  if(defender==null)return false;
  TabletopBlockEntity.PlayedCard attacker=null;int bestPower=0;
  for(var card:CommanderBattleActions.owned(bot,table)){
   // Commander death/replacement zones need their own state machine, so first
   // pilot restricts automated attacks to ordinary simple creatures.
   if(card.id().startsWith("commander:")||!simple(card))continue;
   var traits=CommanderBattleActions.traits(card.stack()).orElseThrow();
   if(!CommanderSimpleCards.canAttack(traits,!CommanderBattleActions.ready(bot,card),card.tapped()))continue;
   if(traits.power()>bestPower){attacker=card;bestPower=traits.power();}
  }
  if(attacker==null||bestPower<=0)return false;
  if(!table.declareAiAttack(attacker.id(),defender.getBlockPos()))return false;
  if(!CommanderBattleActions.traits(attacker.stack()).orElseThrow().has("vigilance"))
   table.replace(attacker.tapped(true));
  TabletopTargets.mark(world,bot.getUUID(),table.getBlockPos(),table.seatName(),
   attacker.id(),defender.getBlockPos(),"","attack");
  return true;
 }
 private static int freeSlot(GraveyardBlockEntity grave){
  if(grave==null)return -1;
  for(int i=0;i<100;i++)if(grave.getStack(i).isEmpty())return i;
  return -1;
 }
 /** Player response against a previously declared bot attack. */
 public static String respond(ServerPlayer player,BlockPos attackerSeat,String blockerId){
  if(!(player.level() instanceof ServerLevel world))return "Combat requires a server.";
  if(!world.hasChunkAt(attackerSeat)||!(world.getBlockEntity(attackerSeat) instanceof TabletopBlockEntity attackers))
   return "Attacking table is not available.";
  var pending=attackers.aiAttack();
  if(pending==null)return "No pending golem attack.";
  if(!world.hasChunkAt(pending.defender())||!(world.getBlockEntity(pending.defender()) instanceof TabletopBlockEntity defending))
   return "Defending table is missing.";
  if(!player.getUUID().equals(defending.seatOwner()))return "Only the defending player can choose blockers or take damage.";
  if(!connected(world,attackerSeat).contains(defending))return "Seats are no longer connected.";
  TabletopBlockEntity.PlayedCard attacker=attackers.find(pending.attackerId());
  if(attacker==null||!simple(attacker))return "Attacker changed; leave combat unresolved.";
  var attackTraits=CommanderBattleActions.traits(attacker.stack()).orElseThrow();
  LifePointBlockEntity targetLife=life(world,defending);
  if(targetLife==null||targetLife.getLife()<=0)return "Defender's linked Life Point is unavailable.";
  TabletopBlockEntity.PlayedCard blocker=null;
  if(blockerId!=null&&!blockerId.isBlank()){
   blocker=defending.find(blockerId);
   if(blocker==null||!player.getUUID().toString().equals(blocker.owner())||!simple(blocker))
    return "Select a supported creature on your own battlefield.";
   if(!CommanderSimpleCards.canBlock(CommanderBattleActions.traits(blocker.stack()).orElseThrow(),attackTraits,blocker.tapped()))
    return "That creature cannot legally block this attacker.";
  }
  LifePointBlockEntity attackerLife=life(world,attackers);
  var damage=CommanderSimpleCards.combat(attackTraits,
   blocker==null?null:CommanderBattleActions.traits(blocker.stack()).orElseThrow(),
   attackerLife==null?1_000_000:attackerLife.getLife(),targetLife.getLife());
  if(damage.attackerLifeGain()>0&&attackerLife==null)
   return "Attacker's linked Life Point is required to resolve lifelink.";
  // Preflight storage for both deaths; never delete cards when a required GY
  // is absent. Tokens vanish, but physical cards need actual destination slots.
  GraveyardBlockEntity attackGrave=null,blockGrave=null;
  int attackSlot=-1,blockSlot=-1;
  if(damage.attackerDies()&&!attacker.id().startsWith("token:")&&!attacker.id().startsWith("copy:")){
   attackGrave=CommanderBattleActions.graveyard(world,control(world,hand(world,attackers)));
   attackSlot=freeSlot(attackGrave);
   if(attackSlot<0)return "Golem's Graveyard is missing or full.";
  }
  if(blocker!=null&&damage.blockerDies()&&!blocker.id().startsWith("token:")&&!blocker.id().startsWith("copy:")){
   blockGrave=CommanderBattleActions.graveyard(world,control(world,hand(world,defending)));
   blockSlot=freeSlot(blockGrave);
   if(blockSlot<0)return "Defender's Graveyard is missing or full.";
  }
  if(damage.attackerDies()){
   attackers.remove(attacker.id());
   if(attackGrave!=null)attackGrave.setStack(attackSlot,TabletopCounters.leavingBattlefield(attacker.stack()));
  }
  if(blocker!=null&&damage.blockerDies()){
   defending.remove(blocker.id());
   if(blockGrave!=null)blockGrave.setStack(blockSlot,TabletopCounters.leavingBattlefield(blocker.stack()));
  }
  // Apply simultaneous damage/lifelink before checking either player's life.
  if(damage.attackerLifeGain()>0)attackerLife.addLife(damage.attackerLifeGain());
  int defenderChange=damage.blockerLifeGain()-damage.playerDamage();
  if(defenderChange!=0)targetLife.addLife(defenderChange);
  if(targetLife.getLife()<=0)LifePlayGroups.setDead(world,targetLife.getBlockPos(),true);
  if(attackerLife!=null&&attackerLife.getLife()<=0)
   LifePlayGroups.setDead(world,attackerLife.getBlockPos(),true);
  attackers.clearAiAttack();
  // The server can resume the AI turn on its next tick and pass naturally.
  UUID bot=attackers.seatOwner();
  if(bot!=null)TabletopTargets.clear(world,bot);
  return blocker==null?"Unblocked golem attacker dealt "+damage.playerDamage()+" damage."
    :"Combat resolved: "+(damage.attackerDies()?"attacker died; ":"")
       +(damage.blockerDies()?"blocker died.":"blocker survived.");
 }
}

