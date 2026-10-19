package dev.casz.caszualmtg;

import com.spider.mtgcard.life.LifePlayGroups;
import com.spider.mtgcard.life.LifePointBlockEntity;
import net.minecraft.core.BlockPos;
import net.minecraft.server.level.ServerLevel;

import java.util.*;

/**
 * Integrates a Commander Golem's explicitly linked Life Point with MTGCard's
 * persisted pod/turn-order system. Never starts or edits an active pod.
 */
public final class CommanderPod {
 private CommanderPod(){}

 public record Status(UUID id,String name,boolean started,boolean rolling,boolean active,
                      boolean dead,int memberCount,String problem) {
  public boolean playable(){return id!=null&&started&&!rolling&&active&&!dead&&problem.isEmpty();}
  public boolean member(){return id!=null&&problem.isEmpty();}
 }

 /** Returns a consistent server-side pod snapshot, not a possibly stale BE flag. */
 public static Status status(ServerLevel world,LifePointBlockEntity life){
  if(life==null)return missing("No Life Point linked to the Card Hand.");
  BlockPos pos=life.getBlockPos();
  UUID id=LifePlayGroups.findGroupId(world,pos);
  if(id==null)return missing("Life Point is not part of a pod.");
  LifePlayGroups.Group g=LifePlayGroups.getGroup(world,id);
  if(g==null||g.order.isEmpty())return missing("The Life Point pod is missing.");
  int index=g.order.indexOf(pos);
  if(index<0)return missing("The Life Point is not a pod member.");
  boolean dead=g.dead.contains(pos)||life.getLife()<=0;
  // MTGCard decides whether this counter belongs to the active turn.
  // During the initial turn-order roulette, active is not final.
  boolean active=g.started&&!g.rolling&&g.activeIndex>=0
    &&life.isGameStarted()&&life.isTurnActive()&&!dead;
  return new Status(id,g.name,g.started,g.rolling,active,dead,g.order.size(),"");
 }

 private static Status missing(String problem){
  return new Status(null,"",false,false,false,false,0,problem);
 }

 /** Link an unassigned golem counter to the *only* adjacent table pod,
  * before that pod starts. If ambiguous or started, leave everyone untouched.
  * The manager also can join through MTGCard's Life Point pod UI instead.
  */
 public static String joinNearbyPod(ServerLevel world,TabletopBlockEntity seat,LifePointBlockEntity life){
  if(seat==null||life==null)return "Link a Life Point and an MTG Table first.";
  Status own=status(world,life);
  if(own.member())return "Already in pod: "+own.name();
  Set<UUID> candidates=new LinkedHashSet<>();
  for(TabletopBlockEntity other:CommanderCombat.connected(world,seat.getBlockPos())){
   if(other.getBlockPos().equals(seat.getBlockPos())||other.seatOwner()==null)continue;
   LifePointBlockEntity lp=CommanderCombat.life(world,other);
   if(lp==null||lp.getBlockPos().equals(life.getBlockPos()))continue;
   UUID groupId=LifePlayGroups.findGroupId(world,lp.getBlockPos());
   if(groupId!=null)candidates.add(groupId);
  }
  if(candidates.isEmpty())return "No nearby connected-table pod found. Create a pod using an MTGCard Life Point.";
  if(candidates.size()!=1)return "Multiple pods detected. Join the intended pod through the Life Point menu.";
  UUID id=candidates.iterator().next();
  LifePlayGroups.Group target=LifePlayGroups.getGroup(world,id);
  if(target==null)return "The nearby pod could not be found.";
  if(target.started||target.rolling)return "That pod has already started. Join it manually, not automatically.";
  if(target.order.contains(life.getBlockPos()))return "Already in pod: "+target.name;
  // Refuse a duplicate participant counter and never change another person's
  // turn order outside the pre-game setup stage.
  List<BlockPos> newOrder=new ArrayList<>(target.order);
  newOrder.add(life.getBlockPos().immutable());
  LifePlayGroups.saveGroup(world,id,target.name,newOrder);
  Status joined=status(world,life);
  return joined.member()?"Joined pod: "+joined.name()+" ("+joined.memberCount()+" counters).":
     "Could not register the Golem's Life Point with the pod.";
 }
}
