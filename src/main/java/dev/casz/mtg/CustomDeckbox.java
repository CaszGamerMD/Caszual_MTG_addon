package dev.casz.mtg;
import com.mojang.serialization.MapCodec;
import com.spider.mtgcard.deckbox.*;
import net.minecraft.core.BlockPos;
import net.minecraft.network.chat.Component;
import net.minecraft.world.*;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.item.*;
import net.minecraft.world.item.component.TooltipDisplay;
import net.minecraft.world.level.*;
import net.minecraft.world.level.block.state.*;
import net.minecraft.world.phys.BlockHitResult;
import java.util.function.Consumer;

public final class CustomDeckbox extends DeckboxBlock {
 public static final MapCodec<CustomDeckbox> CODEC=simpleCodec(CustomDeckbox::new);
 public CustomDeckbox(BlockBehaviour.Properties p){super(p);}
 @Override protected MapCodec<CustomDeckbox> codec(){return CODEC;}
 public InteractionResult applyMaterial(ItemStack stack,Level level,BlockPos pos,Player player){
  if(!player.isShiftKeyDown()||!(stack.getItem() instanceof BlockItem block))return InteractionResult.PASS;
  if(!player.mayBuild())return InteractionResult.FAIL;
  if(level.getBlockEntity(pos) instanceof BoxMaterial box){
   if(!level.isClientSide()){
    String selected=net.minecraft.core.registries.BuiltInRegistries.BLOCK.getKey(block.getBlock()).toString();
    if(!selected.equals(box.companion$material())){
     box.companion$material(selected);
     if(!player.getAbilities().instabuild)stack.shrink(1);
    }
   }
   return InteractionResult.SUCCESS;
  }
  return InteractionResult.PASS;
 }
 @Override protected InteractionResult useItemOn(ItemStack stack,BlockState state,Level level,BlockPos pos,Player player,InteractionHand hand,BlockHitResult hit){
  InteractionResult changed=applyMaterial(stack,level,pos,player);
  return changed!=InteractionResult.PASS?changed:useWithoutItem(state,level,pos,player,hit);
 }
 @Override public void setPlacedBy(Level level,BlockPos pos,BlockState state,LivingEntity owner,ItemStack stack){super.setPlacedBy(level,pos,state,owner,stack);if(level.getBlockEntity(pos) instanceof BoxMaterial box)box.companion$material(stack.getOrDefault(Companion.BOX_MATERIAL,BoxMaterial.DEFAULT));}
 @Override protected ItemStack getCloneItemStack(LevelReader level,BlockPos pos,BlockState state,boolean includeData){ItemStack result=super.getCloneItemStack(level,pos,state,includeData);if(level.getBlockEntity(pos) instanceof BoxMaterial box)result.set(Companion.BOX_MATERIAL,box.companion$material());return result;}
 public static final class Item extends DeckboxBlockItem {
  public Item(CustomDeckbox block,net.minecraft.world.item.Item.Properties p){super(block,p);}
  @Override public void appendHoverText(ItemStack stack,net.minecraft.world.item.Item.TooltipContext context,TooltipDisplay display,Consumer<Component> lines,TooltipFlag flag){super.appendHoverText(stack,context,display,lines,flag);lines.accept(Component.literal("Texture: ").append(BoxMaterial.block(stack.getOrDefault(Companion.BOX_MATERIAL,BoxMaterial.DEFAULT)).getName()));lines.accept(Component.literal("Sneak-use a block on the placed box to change its panels."));}
 }
}
