package dev.casz.caszualmtg;

import com.spider.mtgcard.util.CardCounterNbt;
import com.spider.mtgcard.util.StackData;
import com.spider.mtgcard.util.TcgCardMeta;
import net.minecraft.world.item.ItemStack;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.nbt.ListTag;
import java.util.*;

/** Render-only P/T and counter summaries backed by the actual MTGCard metadata.
 * Face-specific stats are used for transformed / double-faced creatures. */
public final class TabletopCardStats {
 private TabletopCardStats(){}
 public static Map<String,Integer> counters(ItemStack card){
  return card==null||card.isEmpty()?Map.of():CardCounterNbt.readCounterMap(card);
 }
 public static String powerToughness(ItemStack card){
  if(card==null||card.isEmpty())return "";
  var meta=TcgCardMeta.read(card);
  String type=meta.typeLine(),power=meta.power(),toughness=meta.toughness();
  var root=StackData.readCustom(card);
  CompoundTag mtg=root.getCompound(TcgCardMeta.MTG_META).orElseGet(CompoundTag::new);
  ListTag faces=mtg.getList("card_faces").orElse(mtg.getList("faces").orElse(null));
  if(faces!=null&&meta.face()>=0&&meta.face()<faces.size()){
   CompoundTag face=faces.getCompound(meta.face()).orElse(null);
   if(face!=null){
    type=face.getString("type_line").orElse(type);
    power=face.getString("power").orElse(power);
    toughness=face.getString("toughness").orElse(toughness);
   }
  }
  if(!type.toLowerCase(Locale.ROOT).contains("creature")||power.isBlank()||toughness.isBlank())return "";
  var counts=counters(card);
  int bonus=counts.getOrDefault("+1/+1",0)-counts.getOrDefault("-1/-1",0);
  return shifted(power,bonus)+"/"+shifted(toughness,bonus);
 }
 private static String shifted(String original,int bonus){
  if(bonus==0)return original;
  try{return Integer.toString(Integer.parseInt(original)+bonus);}
  catch(NumberFormatException ignored){return original;}
 }
}
