package dev.casz.caszualmtg;

import com.mojang.serialization.MapCodec;
import net.minecraft.network.RegistryFriendlyByteBuf;
import net.minecraft.network.codec.StreamCodec;
import net.minecraft.world.item.*;
import net.minecraft.world.item.crafting.*;
import net.minecraft.world.level.Level;

/** One tabletop for planks, logs, stripped wood, stems and modded wood.
 * Three matching wood blocks on top, matching wood posts either side of
 * the felt, two sticks underneath. This keeps one source ID throughout. */
public final class TabletopRecipe extends CustomRecipe {
 public static final TabletopRecipe INSTANCE=new TabletopRecipe();
 public static final MapCodec<TabletopRecipe> CODEC=MapCodec.unit(INSTANCE);
 public static final StreamCodec<RegistryFriendlyByteBuf,TabletopRecipe> STREAM_CODEC=StreamCodec.unit(INSTANCE);
 public static final RecipeSerializer<TabletopRecipe> SERIALIZER=new RecipeSerializer<>(CODEC,STREAM_CODEC);
 private TabletopRecipe(){}

 private static String wood(CraftingInput input){
  if(input.width()!=3||input.height()!=3)return null;
  String source=null;
  for(int y=0;y<3;y++)for(int x=0;x<3;x++){
   ItemStack item=input.getItem(y*3+x);
   if(y==0||(y==1&&x!=1)){
    if(!ChairWood.eligible(item))return null;
    String current=ChairWood.fromItem(item);
    if(source!=null&&!source.equals(current))return null;
    source=current;
   }else if(y==1){
    if(!"minecraft:green_wool".equals(net.minecraft.core.registries.BuiltInRegistries.ITEM.getKey(item.getItem()).toString()))return null;
   }else if(x!=1){
    if(!item.is(Items.STICK))return null;
   }else if(!item.isEmpty())return null;
  }
  return source;
 }
 @Override public boolean matches(CraftingInput input,Level level){return wood(input)!=null;}
 @Override public ItemStack assemble(CraftingInput input){
  String id=wood(input);
  if(id==null)return ItemStack.EMPTY;
  ItemStack table=new ItemStack(CaszualMtg.TABLETOP);
  table.set(CaszualMtg.TABLE_MATERIAL,id);
  return table;
 }
 @Override public RecipeSerializer<? extends CustomRecipe> getSerializer(){return SERIALIZER;}
}
