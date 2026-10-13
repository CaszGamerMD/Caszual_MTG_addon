package dev.casz.caszualmtg;

import com.mojang.serialization.MapCodec;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.world.item.context.BlockPlaceContext;
import net.minecraft.world.level.block.state.StateDefinition;
import net.minecraft.world.level.block.state.properties.BlockStateProperties;
import net.minecraft.world.level.block.state.properties.EnumProperty;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.*;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.BaseEntityBlock;
import net.minecraft.world.level.block.RenderShape;
import net.minecraft.world.level.block.state.BlockBehaviour;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.block.entity.BlockEntity;
import net.minecraft.world.level.block.entity.BlockEntityType;
import net.minecraft.world.level.block.entity.BlockEntityTicker;
import net.minecraft.world.phys.BlockHitResult;
import org.jetbrains.annotations.Nullable;

public final class BuilderBlock extends BaseEntityBlock {
 public static final MapCodec<BuilderBlock> CODEC=simpleCodec(BuilderBlock::new);
 public static final EnumProperty<Direction> FACING=BlockStateProperties.HORIZONTAL_FACING;
 public BuilderBlock(BlockBehaviour.Properties p){
  super(p);
  // North is the old blockstate, so existing placed builders keep their appearance.
  registerDefaultState(stateDefinition.any().setValue(FACING,Direction.NORTH));
 }
 @Override protected void createBlockStateDefinition(StateDefinition.Builder<Block,BlockState> builder){
  builder.add(FACING);
 }
 @Override public BlockState getStateForPlacement(BlockPlaceContext context){
  // The computer screen on the north side of the model points toward its owner.
  return defaultBlockState().setValue(FACING,context.getHorizontalDirection().getOpposite());
 }
 @Override protected MapCodec<? extends BaseEntityBlock> codec(){return CODEC;}
 @Override public RenderShape getRenderShape(BlockState s){return RenderShape.MODEL;}
 @Override public @Nullable BlockEntity newBlockEntity(BlockPos pos,BlockState s){return new BuilderBlockEntity(pos,s);}
 /** Server-owned job keeps running after the menu closes or the player logs out. */
 @Override public <T extends BlockEntity> BlockEntityTicker<T> getTicker(Level level,BlockState state,BlockEntityType<T> type){
  return level.isClientSide()?null:createTickerHelper(type,CaszualMtg.BUILDER_BE,
    (world,pos,current,builder)->AutoDeckBuilder.tick((ServerLevel)world,builder));
 }
 @Override protected InteractionResult useItemOn(ItemStack item,BlockState state,Level level,BlockPos pos,Player player,InteractionHand hand,BlockHitResult hit){return useWithoutItem(state,level,pos,player,hit);}
 @Override protected InteractionResult useWithoutItem(BlockState s,Level l,BlockPos pos,Player p,BlockHitResult hit){if(p instanceof ServerPlayer sp)ServerLogic.open(sp,pos,3);return InteractionResult.SUCCESS;}
 @Override public BlockState playerWillDestroy(Level level,BlockPos pos,BlockState state,Player player){
  // Extract output before the block entity is detached from the world.
  if(!level.isClientSide()&&level.getBlockEntity(pos) instanceof BuilderBlockEntity builder){
   ItemStack item=builder.removeItemNoUpdate(0);
   if(!item.isEmpty())popResource(level,pos,item);
  }
  return super.playerWillDestroy(level,pos,state,player);
 }
 @Override protected void affectNeighborsAfterRemoval(BlockState state,ServerLevel world,BlockPos pos,boolean moved){
  if(world.getBlockState(pos).getBlock()!=this&&world.getBlockEntity(pos) instanceof BuilderBlockEntity builder)Containers.dropContents(world,pos,builder);
  super.affectNeighborsAfterRemoval(state,world,pos,moved);
 }
}
