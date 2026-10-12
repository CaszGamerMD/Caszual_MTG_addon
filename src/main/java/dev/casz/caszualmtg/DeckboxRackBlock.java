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
import net.minecraft.world.phys.shapes.*;
import org.jetbrains.annotations.Nullable;
import java.util.List;

/** Quarter-block-high shelf, one-half block deep, with five item-preserving positions. */
public final class DeckboxRackBlock extends BaseEntityBlock {
 public static final MapCodec<DeckboxRackBlock> CODEC=simpleCodec(DeckboxRackBlock::new);
 public static final DirectionProperty FACING=BlockStateProperties.HORIZONTAL_FACING;
 public static final BooleanProperty WALL=BooleanProperty.create("wall");
 public static final BooleanProperty[] OCCUPIED={
  BooleanProperty.create("box0"),BooleanProperty.create("box1"),BooleanProperty.create("box2"),BooleanProperty.create("box3"),BooleanProperty.create("box4")
 };
 static final VoxelShape FLOOR=Block.box(0,0,0,16,8,8);
 static final VoxelShape WALL_SHAPE=Block.box(0,7,0,16,15,8);
 public DeckboxRackBlock(Properties p){
  super(p);
  BlockState state=stateDefinition.any().setValue(FACING,Direction.NORTH).setValue(WALL,false);
  for(var field:OCCUPIED)state=state.setValue(field,false);
  registerDefaultState(state);
 }
 @Override protected MapCodec<? extends BaseEntityBlock> codec(){return CODEC;}
 @Override protected void createBlockStateDefinition(StateDefinition.Builder<Block,BlockState> b){b.add(FACING,WALL);for(var v:OCCUPIED)b.add(v);}
 @Override public RenderShape getRenderShape(BlockState state){return RenderShape.MODEL;}
 @Override public @Nullable BlockEntity newBlockEntity(BlockPos pos,BlockState state){return new DeckboxRackEntity(pos,state);}
 @Override public BlockState getStateForPlacement(BlockPlaceContext ctx){
  BlockState state=defaultBlockState();
  Direction side=ctx.getClickedFace();
  return state.setValue(WALL,side.getAxis().isHorizontal()).setValue(FACING,side.getAxis().isHorizontal()?side:ctx.getHorizontalDirection().getOpposite());
 }
 @Override protected VoxelShape getShape(BlockState state,BlockGetter world,BlockPos pos,CollisionContext ctx){
  VoxelShape shape=state.getValue(WALL)?WALL_SHAPE:FLOOR;
  return switch(state.getValue(FACING)){
   case NORTH -> shape;
   case SOUTH -> Shapes.or(Block.box(0,state.getValue(WALL)?7:0,8,16,state.getValue(WALL)?15:8,16));
   case EAST -> Block.box(8,state.getValue(WALL)?7:0,0,16,state.getValue(WALL)?15:8,16);
   case WEST -> Block.box(0,state.getValue(WALL)?7:0,0,8,state.getValue(WALL)?15:8,16);
   default -> shape;
  };
 }
 @Override protected InteractionResult useItemOn(ItemStack stack,BlockState s,Level level,BlockPos pos,Player player,InteractionHand hand,BlockHitResult hit){
  if(stack.getItem() instanceof com.spider.mtgcard.deckbox.DeckboxBlockItem){
   if(!level.isClientSide()&&level.getBlockEntity(pos) instanceof DeckboxRackEntity rack){
    int slot=-1;for(int i=0;i<DeckboxRackEntity.SIZE;i++)if(rack.getItem(i).isEmpty()){slot=i;break;}
    if(slot>=0){rack.setItem(slot,stack.copyWithCount(1));if(!player.getAbilities().instabuild)stack.shrink(1);}
    else player.displayClientMessage(net.minecraft.network.chat.Component.literal("Deckbox rack is full."),true);
   }
   return InteractionResult.SUCCESS;
  }
  return useWithoutItem(s,level,pos,player,hit);
 }
 @Override protected InteractionResult useWithoutItem(BlockState state,Level level,BlockPos pos,Player player,BlockHitResult hit){
  if(player instanceof ServerPlayer sp)sp.openMenu(DeckboxRackMenu.provider(pos));
  return InteractionResult.SUCCESS;
 }
 @Override public void setPlacedBy(Level level,BlockPos pos,BlockState state,@Nullable LivingEntity placer,ItemStack stack){
  super.setPlacedBy(level,pos,state,placer,stack);
  if(level.getBlockEntity(pos) instanceof DeckboxRackEntity rack){
   var contents=stack.get(DataComponents.CONTAINER);
   if(contents!=null){var restored=NonNullList.withSize(DeckboxRackEntity.SIZE,ItemStack.EMPTY);contents.copyInto(restored);rack.restore(restored);}
  }
 }
 @Override protected ItemStack getCloneItemStack(LevelReader level,BlockPos pos,BlockState state,boolean data){
  ItemStack stack=new ItemStack(this);
  if(level.getBlockEntity(pos) instanceof DeckboxRackEntity rack)
   stack.set(DataComponents.CONTAINER,ItemContainerContents.fromItems(rack.contents()));
  return stack;
 }
 @Override public BlockState playerWillDestroy(Level level,BlockPos pos,BlockState state,Player player){
  if(!level.isClientSide()&&level.getBlockEntity(pos) instanceof DeckboxRackEntity rack){
   ItemStack stored=new ItemStack(this);
   stored.set(DataComponents.CONTAINER,ItemContainerContents.fromItems(rack.contents()));
   popResource(level,pos,stored);
  }
  return super.playerWillDestroy(level,pos,state,player);
 }
}
