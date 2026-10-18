package dev.casz.caszualmtg;

import net.minecraft.core.component.DataComponents;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.component.CustomData;

/**
 * Battlefield counters have no meaning outside the battlefield. Return a copy
 * with MTGCard's counter data stripped, preserving card identity, artwork,
 * face, foil and all unrelated custom metadata. The source stack is NEVER
 * mutated: a failed transfer must leave its battlefield counters untouched.
 */
public final class TabletopCounters {
 private TabletopCounters(){}

 public static ItemStack leavingBattlefield(ItemStack source){
  if(source==null||source.isEmpty())return ItemStack.EMPTY;
  ItemStack result=source.copy();
  CustomData component=result.get(DataComponents.CUSTOM_DATA);
  if(component==null)return result;
  CompoundTag root=component.copyTag();
  CompoundTag meta=root.getCompound("mtg_meta").orElse(null);
  if(meta==null)return result;
  if(!meta.contains("counters")&&!meta.contains("counter_icons"))return result;
  meta.remove("counters");
  meta.remove("counter_icons");
  root.put("mtg_meta",meta);
  result.set(DataComponents.CUSTOM_DATA,CustomData.of(root));
  return result;
 }
}
