package dev.casz.caszualmtg;

import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.scores.PlayerTeam;
import net.minecraft.world.scores.Scoreboard;
import net.minecraft.world.scores.TeamColor;
import java.util.*;

public final class StaffTargets {
 public enum Color { WHITE, ORANGE }
 private record Original(boolean glowing,String team){}
 private static final Map<UUID,Original> ORIGINALS=new HashMap<>();
 private record Mark(Color action,int rgb){}
 private static final Map<UUID,LinkedHashMap<UUID,Mark>> ASSIGNMENTS=new HashMap<>();

 public static void mark(ServerPlayer owner,Entity entity,Color color){
  if(owner==null||entity==null)return;
  UUID target=entity.getUUID();
  ORIGINALS.computeIfAbsent(target,k->new Original(entity.hasGlowingTag(),entity.getTeam()==null?null:entity.getTeam().getName()));
  LinkedHashMap<UUID,Mark> marks=ASSIGNMENTS.computeIfAbsent(target,k->new LinkedHashMap<>());
  marks.remove(owner.getUUID());
  marks.put(owner.getUUID(),new Mark(color,StaffColors.rgb(color==Color.WHITE
    ?StaffColors.left(staff(owner)):StaffColors.right(staff(owner)))));
  apply(entity,marks.get(owner.getUUID()));
 }

 public static void clear(ServerPlayer owner){
  if(owner==null)return;
  UUID ownerId=owner.getUUID();
  List<UUID> emptied=new ArrayList<>();
  for(var entry:ASSIGNMENTS.entrySet()){
   LinkedHashMap<UUID,Mark> marks=entry.getValue();
   if(marks.remove(ownerId)==null)continue;
   Entity entity=find(owner,entry.getKey());
   if(marks.isEmpty()){
    if(entity!=null)restore(entity,ORIGINALS.get(entry.getKey()));
    emptied.add(entry.getKey());
   }else if(entity!=null){
    Mark remaining=null;
    for(Mark c:marks.values())remaining=c;
    if(remaining!=null)apply(entity,remaining);
   }
  }
  for(UUID id:emptied){ASSIGNMENTS.remove(id);ORIGINALS.remove(id);}
 }

 /** Recolor existing marks owned by a player immediately after a staff preset change. */
 public static void refreshOwner(ServerPlayer owner){
  UUID id=owner.getUUID();
  for(var entry:ASSIGNMENTS.entrySet()){
   var marks=entry.getValue();
   Mark previous=marks.get(id);
   if(previous==null)continue;
   Mark updated=new Mark(previous.action(),StaffColors.rgb(previous.action()==Color.WHITE
       ?StaffColors.left(staff(owner)):StaffColors.right(staff(owner))));
   marks.put(id,updated);
   Entity entity=find(owner,entry.getKey());
   if(entity!=null&&!marks.isEmpty()){
    Mark latest=null;
    for(Mark mark:marks.values())latest=mark;
    if(latest!=null)apply(entity,latest);
   }
  }
 }
 private static net.minecraft.world.item.ItemStack staff(ServerPlayer owner){
  var main=owner.getMainHandItem();
  if(main.is(CaszualMtg.TARGETING_STAFF))return main;
  var off=owner.getOffhandItem();
  if(off.is(CaszualMtg.TARGETING_STAFF))return off;
  for(int slot=0;slot<36;slot++){
   var item=owner.getInventory().getItem(slot);
   if(item.is(CaszualMtg.TARGETING_STAFF))return item;
  }
  return net.minecraft.world.item.ItemStack.EMPTY;
 }
 public static void clearAllForDisconnect(ServerPlayer owner){clear(owner);}

 private static Entity find(ServerPlayer owner,UUID id){
  for(ServerLevel level:owner.level().getServer().getAllLevels()){
   Entity entity=level.getEntity(id);
   if(entity!=null)return entity;
  }
  return null;
 }

 private static void apply(Entity entity,Mark mark){
  entity.setGlowingTag(true);
  Scoreboard board=entity.level().getScoreboard();
  board.addPlayerToTeam(entity.getScoreboardName(),ensureTeam(board,mark.rgb()));
 }

 private static void restore(Entity entity,Original original){
  if(original==null)return;
  Scoreboard board=entity.level().getScoreboard();
  entity.setGlowingTag(original.glowing());
  board.removePlayerFromTeam(entity.getScoreboardName());
  if(original.team()!=null){
   PlayerTeam old=board.getPlayerTeam(original.team());
   if(old!=null)board.addPlayerToTeam(entity.getScoreboardName(),old);
  }
 }

 private static PlayerTeam ensureTeam(Scoreboard board,int rgb){
  String name=StaffColors.teamName(rgb);
  PlayerTeam team=board.getPlayerTeam(name);
  if(team==null)team=board.addPlayerTeam(name);
  // The client getTeamColor mixin supplies the exact 24-bit color.
  // Vanilla team color provides a harmless fallback on unmodified clients.
  team.setColor(Optional.of(TeamColor.WHITE));
  return team;
 }
 private StaffTargets(){}
}
