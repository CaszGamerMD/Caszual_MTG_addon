package dev.casz.caszualmtg;

import com.mojang.serialization.MapCodec;
import net.minecraft.core.BlockPos;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.level.storage.loot.LootParams;
import net.minecraft.world.level.storage.loot.parameters.LootContextParams;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.InteractionResult;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.DyeColor;
import net.minecraft.world.level.block.state.StateDefinition;
import net.minecraft.world.level.block.state.properties.EnumProperty;
import net.minecraft.world.level.block.state.properties.IntegerProperty;
import net.minecraft.world.level.*;
import net.minecraft.world.level.block.*;
import net.minecraft.world.level.block.entity.BlockEntity;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.phys.BlockHitResult;
import net.minecraft.world.phys.shapes.CollisionContext;
import net.minecraft.world.phys.shapes.VoxelShape;
import org.jetbrains.annotations.Nullable;

/** Adjacent tiles at equal height form one shared multiplayer tabletop. */
public final class TabletopBlock extends BaseEntityBlock {
 public static final MapCodec<TabletopBlock> CODEC=MapCodec.unit(()->new TabletopBlock(Properties.of()));
 public static final IntegerProperty CARDS=IntegerProperty.create("cards",0,4);
 public static final EnumProperty<DyeColor> FELT=EnumProperty.create("felt",DyeColor.class);
 private static final VoxelShape SHAPE=Block.box(0,0,0,16,14,16);
 public TabletopBlock(Properties props){super(props);registerDefaultState(stateDefinition.any().setValue(FELT,DyeColor.GREEN).setValue(CARDS,0));}
 @Override protected void createBlockStateDefinition(StateDefinition.Builder<Block,BlockState> builder){builder.add(FELT,CARDS);}
 @Override protected MapCodec<? extends BaseEntityBlock> codec(){return CODEC;}
 @Override public RenderShape getRenderShape(BlockState s){return RenderShape.MODEL;}
 @Override protected VoxelShape getShape(BlockState s,BlockGetter level,BlockPos pos,CollisionContext ctx){return SHAPE;}
 @Override public @Nullable BlockEntity newBlockEntity(BlockPos pos,BlockState s){return new TabletopBlockEntity(pos,s);}
 @Override public void setPlacedBy(Level level,BlockPos pos,BlockState state,@Nullable LivingEntity placer,ItemStack stack){
  super.setPlacedBy(level,pos,state,placer,stack);
  if(level.getBlockEntity(pos) instanceof TabletopBlockEntity table)
   table.material(stack.getOrDefault(CaszualMtg.TABLE_MATERIAL,"minecraft:dark_oak_planks"));
 }
 @Override protected ItemStack getCloneItemStack(LevelReader world,BlockPos pos,BlockState state,boolean includeData){
  ItemStack stack=new ItemStack(this);
  if(world.getBlockEntity(pos) instanceof TabletopBlockEntity table)
   stack.set(CaszualMtg.TABLE_MATERIAL,table.material());
  return stack;
 }
 @Override protected java.util.List<ItemStack> getDrops(BlockState state,LootParams.Builder params){
  ItemStack result=new ItemStack(this);
  BlockEntity entity=params.getOptionalParameter(LootContextParams.BLOCK_ENTITY);
  if(entity instanceof TabletopBlockEntity table)result.set(CaszualMtg.TABLE_MATERIAL,table.material());
  return java.util.List.of(result);
 }
 @Override protected InteractionResult useWithoutItem(BlockState s,Level level,BlockPos pos,Player player,BlockHitResult hit){
  if(player instanceof ServerPlayer sp)TabletopLogic.open(sp,pos);
  return InteractionResult.SUCCESS;
 }
 @Override protected InteractionResult useItemOn(ItemStack held,BlockState s,Level level,BlockPos pos,Player p,net.minecraft.world.InteractionHand hand,BlockHitResult hit){
  // Sneak-use with matching planks, logs or stripped wood to change a table's frame.
  // Ordinary use, including holding a card, still opens the gameplay screen.
  if(p.isShiftKeyDown()&&ChairWood.eligible(held)){
   if(!level.isClientSide()&&level.getBlockEntity(pos) instanceof TabletopBlockEntity table){
    String material=ChairWood.fromItem(held);
    if(!material.equals(table.material())){
     table.material(material);
     if(!p.getAbilities().instabuild)held.shrink(1);
    }
   }
   return InteractionResult.SUCCESS;
  }
  return useWithoutItem(s,level,pos,p,hit);
 }
 @Override public void onPlace(BlockState state,Level level,BlockPos pos,BlockState old,boolean moved){
  super.onPlace(state,level,pos,old,moved);
  if(!level.isClientSide())ChairBlock.refreshNextToTable(level,pos);
 }
 private static void dropContents(Level level,BlockPos pos){
  if(level.isClientSide())return;
  if(level.getBlockEntity(pos) instanceof TabletopBlockEntity tile)for(ItemStack card:tile.drain())popResource(level,pos,card);
 }
 @Override public BlockState playerWillDestroy(Level level,BlockPos pos,BlockState state,Player p){dropContents(level,pos);return super.playerWillDestroy(level,pos,state,p);}
 @Override protected void affectNeighborsAfterRemoval(BlockState state,ServerLevel level,BlockPos pos,boolean moved){
  if(!level.getBlockState(pos).is(CaszualMtg.TABLETOP)){
   dropContents(level,pos);
   ChairBlock.refreshNextToTable(level,pos);
  }
  super.affectNeighborsAfterRemoval(state,level,pos,moved);
 }
}
