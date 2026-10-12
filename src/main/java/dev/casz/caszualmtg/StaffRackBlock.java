package dev.casz.caszualmtg;

import com.mojang.serialization.MapCodec;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.core.NonNullList;
import net.minecraft.core.component.DataComponents;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.*;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.item.*;
import net.minecraft.world.item.component.ItemContainerContents;
import net.minecraft.world.item.context.BlockPlaceContext;
import net.minecraft.world.level.*;
import net.minecraft.world.level.block.*;
import net.minecraft.world.level.block.entity.BlockEntity;
import net.minecraft.world.level.block.state.*;
import net.minecraft.world.level.block.state.properties.*;
import net.minecraft.world.phys.BlockHitResult;
import net.minecraft.world.phys.shapes.VoxelShape;
import net.minecraft.world.phys.shapes.CollisionContext;
import org.jetbrains.annotations.Nullable;

/** A slim wall rail. The four staff models extend roughly two blocks below it. */
public final class StaffRackBlock extends BaseEntityBlock {
 public static final MapCodec<StaffRackBlock> CODEC=simpleCodec(StaffRackBlock::new);
 public static final EnumProperty<Direction> FACING=BlockStateProperties.HORIZONTAL_FACING;
 public StaffRackBlock(Properties p){
  super(p);
  registerDefaultState(stateDefinition.any().setValue(FACING,Direction.NORTH));
 }
 @Override protected MapCodec<? extends BaseEntityBlock> codec(){return CODEC;}
 @Override protected void createBlockStateDefinition(StateDefinition.Builder<Block,BlockState> builder){builder.add(FACING);}
 @Override public RenderShape getRenderShape(BlockState state){return RenderShape.MODEL;}
 @Override public @Nullable BlockEntity newBlockEntity(BlockPos pos,BlockState state){return new StaffRackEntity(pos,state);}
 @Override public @Nullable BlockState getStateForPlacement(BlockPlaceContext ctx){
  // This is a wall-mounted rack, not a floor item. Face outward from the clicked wall.
  Direction side=ctx.getClickedFace();
  if(!side.getAxis().isHorizontal())return null;
  return defaultBlockState().setValue(FACING,side);
 }
 @Override protected VoxelShape getShape(BlockState state,BlockGetter world,BlockPos pos,CollisionContext ctx){
  return switch(state.getValue(FACING)){
   case NORTH -> Block.box(0,8,8,16,15,16);
   case SOUTH -> Block.box(0,8,0,16,15,8);
   case EAST -> Block.box(0,8,0,8,15,16);
   case WEST -> Block.box(8,8,0,16,15,16);
   default -> Block.box(0,8,8,16,15,16);
  };
 }
 @Override protected InteractionResult useItemOn(ItemStack held,BlockState state,Level level,BlockPos pos,Player player,InteractionHand hand,BlockHitResult hit){
  if(held.is(CaszualMtg.TARGETING_STAFF)){
   if(!level.isClientSide()&&level.getBlockEntity(pos) instanceof StaffRackEntity rack){
    for(int slot=0;slot<StaffRackEntity.SIZE;slot++){
     if(!rack.getItem(slot).isEmpty())continue;
     rack.setItem(slot,held.copyWithCount(1));
     // An inserted staff is a transfer, including in creative (keeps item data unique).
     held.shrink(1);
     return InteractionResult.SUCCESS;
    }
    player.sendSystemMessage(net.minecraft.network.chat.Component.literal("Staff Rack is full (4/4)."));
   }
   return InteractionResult.SUCCESS;
  }
  return useWithoutItem(state,level,pos,player,hit);
 }
 @Override protected InteractionResult useWithoutItem(BlockState state,Level level,BlockPos pos,Player player,BlockHitResult hit){
  if(player instanceof ServerPlayer sp)sp.openMenu(StaffRackMenu.provider(pos));
  return InteractionResult.SUCCESS;
 }
 @Override public void setPlacedBy(Level level,BlockPos pos,BlockState state,@Nullable LivingEntity placer,ItemStack stack){
  super.setPlacedBy(level,pos,state,placer,stack);
  if(level.getBlockEntity(pos) instanceof StaffRackEntity rack){
   ItemContainerContents contents=stack.get(DataComponents.CONTAINER);
   if(contents!=null){
    NonNullList<ItemStack> stored=NonNullList.withSize(StaffRackEntity.SIZE,ItemStack.EMPTY);
    contents.copyInto(stored);
    rack.restore(stored);
   }
  }
 }
 @Override protected ItemStack getCloneItemStack(LevelReader level,BlockPos pos,BlockState state,boolean data){
  ItemStack item=new ItemStack(this);
  if(level.getBlockEntity(pos) instanceof StaffRackEntity rack)
   item.set(DataComponents.CONTAINER,ItemContainerContents.fromItems(rack.contents()));
  return item;
 }
 @Override public BlockState playerWillDestroy(Level level,BlockPos pos,BlockState state,Player player){
  if(!level.isClientSide()&&level.getBlockEntity(pos) instanceof StaffRackEntity rack){
   ItemStack item=new ItemStack(this);
   item.set(DataComponents.CONTAINER,ItemContainerContents.fromItems(rack.contents()));
   popResource(level,pos,item);
  }
  return super.playerWillDestroy(level,pos,state,player);
 }
}
