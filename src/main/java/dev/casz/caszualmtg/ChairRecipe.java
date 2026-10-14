package dev.casz.caszualmtg;

import com.mojang.serialization.MapCodec;
import net.minecraft.network.RegistryFriendlyByteBuf;
import net.minecraft.network.codec.StreamCodec;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.crafting.CraftingInput;
import net.minecraft.world.item.crafting.CustomRecipe;
import net.minecraft.world.item.crafting.RecipeSerializer;
import net.minecraft.world.level.Level;

/** One recipe for any eligible source block, including modded planks/logs.
 * All six ingredients must be the same block to avoid an ambiguous skin. */
public final class ChairRecipe extends CustomRecipe {
 public static final ChairRecipe INSTANCE=new ChairRecipe();
 public static final MapCodec<ChairRecipe> CODEC=MapCodec.unit(INSTANCE);
 public static final StreamCodec<RegistryFriendlyByteBuf,ChairRecipe> STREAM_CODEC=StreamCodec.unit(INSTANCE);
 public static final RecipeSerializer<ChairRecipe> SERIALIZER=new RecipeSerializer<>(CODEC,STREAM_CODEC);
 private ChairRecipe(){}

 private static String source(CraftingInput input){
  if(input.width()!=3||input.height()!=3)return null;
  String material=null;
  for(int y=0;y<3;y++)for(int x=0;x<3;x++){
   int index=y*3+x;
   boolean needed=(y==0&&x==0)||(y==1)||(y==2&&(x==0||x==2));
   ItemStack item=input.getItem(index);
   if(!needed){if(!item.isEmpty())return null;continue;}
   if(!ChairWood.eligible(item))return null;
   String current=ChairWood.fromItem(item);
   if(material==null)material=current;
   else if(!material.equals(current))return null;
  }
  return material;
 }
 @Override public boolean matches(CraftingInput input,Level level){return source(input)!=null;}
 @Override public ItemStack assemble(CraftingInput input){
  String material=source(input);
  if(material==null)return ItemStack.EMPTY;
  ItemStack chair=new ItemStack(CaszualMtg.MATERIAL_CHAIR);
  chair.set(CaszualMtg.CHAIR_MATERIAL,material);
  return chair;
 }
 @Override public RecipeSerializer<? extends CustomRecipe> getSerializer(){return SERIALIZER;}
}
