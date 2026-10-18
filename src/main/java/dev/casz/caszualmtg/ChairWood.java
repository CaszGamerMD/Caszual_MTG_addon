package dev.casz.caszualmtg;

import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.resources.Identifier;
import net.minecraft.tags.ItemTags;
import net.minecraft.world.item.BlockItem;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.level.block.Block;

/** A chair skin is a source block ID, never a fixed list of wood names.
 * Planks, logs, stripped logs, stems, hyphae and modded equivalents all work. */
public final class ChairWood {
 public static final String DEFAULT="minecraft:oak_planks";
 private ChairWood(){}

 public static boolean eligible(ItemStack stack){
  if(stack==null||stack.isEmpty()||!(stack.getItem() instanceof BlockItem))return false;
  Identifier id=BuiltInRegistries.ITEM.getKey(stack.getItem());
  if(id==null)return false;
  String p=id.getPath();
  return stack.is(ItemTags.PLANKS)||stack.is(ItemTags.LOGS)
    ||p.endsWith("_planks")||p.endsWith("_log")||p.endsWith("_wood")
    ||p.endsWith("_stem")||p.endsWith("_hyphae")
    ||p.contains("stripped_")&&(p.endsWith("_log")||p.endsWith("_wood")
         ||p.endsWith("_stem")||p.endsWith("_hyphae"));
 }
 public static String fromItem(ItemStack stack){
  return eligible(stack)?BuiltInRegistries.BLOCK.getKey(Block.byItem(stack.getItem())).toString():DEFAULT;
 }
 public static String safe(String name){
  if(name==null)return DEFAULT;
  Identifier id=Identifier.tryParse(name);
  if(id==null||!BuiltInRegistries.BLOCK.containsKey(id))return DEFAULT;
  Block block=BuiltInRegistries.BLOCK.getValue(id);
  if(block==null||block.defaultBlockState().isAir())return DEFAULT;
  return id.toString();
 }
 public static Block block(String name){return BuiltInRegistries.BLOCK.getValue(Identifier.parse(safe(name)));}
}
