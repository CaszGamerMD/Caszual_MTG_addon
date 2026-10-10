package dev.casz.caszualmtg;

import com.spider.mtgcard.util.StackData;
import net.minecraft.core.component.DataComponents;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.component.CustomData;
import net.minecraft.world.scores.Team;
import java.util.Locale;

/** Two independent 24-bit staff outline colors; stored directly on staff ItemStacks. */
public final class StaffColors {
 public static final String LEFT_DEFAULT="#FFFFFF";
 public static final String RIGHT_DEFAULT="#FFAA00";
 private static final String LEFT="caszual_staff_left_rgb";
 private static final String RIGHT="caszual_staff_right_rgb";
 private static final String PREFIX="csrgb_";

 private StaffColors(){}

 public static boolean valid(String value){
  if(value==null||value.length()!=7||value.charAt(0)!='#')return false;
  for(int i=1;i<7;i++)if(Character.digit(value.charAt(i),16)<0)return false;
  return true;
 }
 public static String normalize(String value){
  if(!valid(value))throw new IllegalArgumentException("Use #RRGGBB, for example #35C9FF.");
  return value.toUpperCase(Locale.ROOT);
 }
 public static int rgb(String value){return Integer.parseInt(normalize(value).substring(1),16);}
 public static String left(ItemStack stack){return read(stack,LEFT,LEFT_DEFAULT);}
 public static String right(ItemStack stack){return read(stack,RIGHT,RIGHT_DEFAULT);}
 private static String read(ItemStack stack,String key,String fallback){
  if(stack==null||stack.isEmpty())return fallback;
  String raw=StackData.readCustom(stack).getString(key).orElse(fallback);
  return valid(raw)?normalize(raw):fallback;
 }
 public static void write(ItemStack stack,String left,String right){
  if(stack.isEmpty()||!stack.is(CaszualMtg.TARGETING_STAFF))return;
  String l=normalize(left),r=normalize(right);
  CompoundTag data=StackData.readCustom(stack);
  data.putString(LEFT,l);data.putString(RIGHT,r);
  stack.set(DataComponents.CUSTOM_DATA,CustomData.of(data));
 }
 /** Encoded team names synchronize by vanilla scoreboard, without custom target packets. */
 public static String teamName(int rgb){return PREFIX+String.format(Locale.ROOT,"%06X",rgb&0xFFFFFF);}
 /** Returns -1 for teams not created by this feature; preserves other mod teams. */
 public static int fromTeam(Team team){
  if(team==null)return -1;
  String name=team.getName();
  if(name.length()!=PREFIX.length()+6||!name.startsWith(PREFIX))return -1;
  String suffix=name.substring(PREFIX.length());
  for(int i=0;i<6;i++)if(Character.digit(suffix.charAt(i),16)<0)return -1;
  return Integer.parseInt(suffix,16);
 }
}
