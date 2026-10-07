package dev.casz.mtg;

import net.minecraft.ChatFormatting;
import net.minecraft.client.Minecraft;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.scores.PlayerTeam;
import net.minecraft.world.scores.Scoreboard;
import java.util.*;

public final class StaffTargets {
 public enum Color { WHITE, ORANGE }
 private record Original(boolean glowing,String team){}
 private static final Map<UUID,Original> ORIGINALS=new LinkedHashMap<>();
 private static final Map<UUID,Color> MARKS=new LinkedHashMap<>();
 private static final String WHITE_TEAM="mtgstaff_white";
 private static final String ORANGE_TEAM="mtgstaff_orange";

 public static void mark(Entity entity,Color color){
  if(entity==null)return;
  Minecraft mc=Minecraft.getInstance();
  if(mc.level==null)return;
  UUID id=entity.getUUID();
  ORIGINALS.computeIfAbsent(id,k->new Original(entity.hasGlowingTag(),entity.getTeam()==null?null:entity.getTeam().getName()));
  MARKS.put(id,color);
  entity.setGlowingTag(true);
  Scoreboard board=mc.level.getScoreboard();
  PlayerTeam team=ensureTeam(board,color);
  board.addPlayerToTeam(entity.getScoreboardName(),team);
 }

 public static void clear(){
  Minecraft mc=Minecraft.getInstance();
  if(mc.level!=null){
   Scoreboard board=mc.level.getScoreboard();
   for(var entry:ORIGINALS.entrySet()){
    Entity entity=mc.level.getEntity(entry.getKey());
    if(entity==null)continue;
    Original original=entry.getValue();
    entity.setGlowingTag(original.glowing());
    board.removePlayerFromTeam(entity.getScoreboardName());
    if(original.team()!=null){
     PlayerTeam old=board.getPlayerTeam(original.team());
     if(old!=null)board.addPlayerToTeam(entity.getScoreboardName(),old);
    }
   }
  }
  ORIGINALS.clear();MARKS.clear();
 }

 public static boolean hasTargets(){return !MARKS.isEmpty();}
 public static int count(){return MARKS.size();}

 private static PlayerTeam ensureTeam(Scoreboard board,Color color){
  String name=color==Color.WHITE?WHITE_TEAM:ORANGE_TEAM;
  PlayerTeam team=board.getPlayerTeam(name);
  if(team==null)team=board.addPlayerTeam(name);
  team.setColor(color==Color.WHITE?ChatFormatting.WHITE:ChatFormatting.GOLD);
  return team;
 }
 private StaffTargets(){}
}
