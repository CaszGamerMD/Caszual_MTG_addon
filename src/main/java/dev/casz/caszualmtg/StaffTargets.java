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
 private static final Map<UUID,LinkedHashMap<UUID,Color>> ASSIGNMENTS=new HashMap<>();
 private static final String WHITE_TEAM="mtgstaff_white";
 private static final String ORANGE_TEAM="mtgstaff_orange";

 public static void mark(ServerPlayer owner,Entity entity,Color color){
  if(owner==null||entity==null)return;
  UUID target=entity.getUUID();
  ORIGINALS.computeIfAbsent(target,k->new Original(entity.hasGlowingTag(),entity.getTeam()==null?null:entity.getTeam().getName()));
  LinkedHashMap<UUID,Color> marks=ASSIGNMENTS.computeIfAbsent(target,k->new LinkedHashMap<>());
  marks.remove(owner.getUUID());
  marks.put(owner.getUUID(),color);
  apply(entity,color);
 }

 public static void clear(ServerPlayer owner){
  if(owner==null)return;
  UUID ownerId=owner.getUUID();
  List<UUID> emptied=new ArrayList<>();
  for(var entry:ASSIGNMENTS.entrySet()){
   LinkedHashMap<UUID,Color> marks=entry.getValue();
   if(marks.remove(ownerId)==null)continue;
   Entity entity=find(owner,entry.getKey());
   if(marks.isEmpty()){
    if(entity!=null)restore(entity,ORIGINALS.get(entry.getKey()));
    emptied.add(entry.getKey());
   }else if(entity!=null){
    Color remaining=null;
    for(Color c:marks.values())remaining=c;
    if(remaining!=null)apply(entity,remaining);
   }
  }
  for(UUID id:emptied){ASSIGNMENTS.remove(id);ORIGINALS.remove(id);}
 }

 public static void clearAllForDisconnect(ServerPlayer owner){clear(owner);}

 private static Entity find(ServerPlayer owner,UUID id){
  for(ServerLevel level:owner.level().getServer().getAllLevels()){
   Entity entity=level.getEntity(id);
   if(entity!=null)return entity;
  }
  return null;
 }

 private static void apply(Entity entity,Color color){
  entity.setGlowingTag(true);
  Scoreboard board=entity.level().getScoreboard();
  board.addPlayerToTeam(entity.getScoreboardName(),ensureTeam(board,color));
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

 private static PlayerTeam ensureTeam(Scoreboard board,Color color){
  String name=color==Color.WHITE?WHITE_TEAM:ORANGE_TEAM;
  PlayerTeam team=board.getPlayerTeam(name);
  if(team==null)team=board.addPlayerTeam(name);
  team.setColor(Optional.of(color==Color.WHITE?TeamColor.WHITE:TeamColor.GOLD));
  return team;
 }
 private StaffTargets(){}
}
