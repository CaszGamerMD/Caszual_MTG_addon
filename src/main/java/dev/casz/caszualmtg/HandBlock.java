package dev.casz.caszualmtg;

import com.mojang.serialization.MapCodec;
import com.spider.mtgcard.item.ModItemTags;
import net.minecraft.core.BlockPos;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.*;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.level.*;
import net.minecraft.world.level.block.*;
import net.minecraft.world.level.block.entity.BlockEntity;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.block.state.BlockBehaviour;
import net.minecraft.world.level.block.state.StateDefinition;
import net.minecraft.world.level.block.state.properties.IntegerProperty;
import net.minecraft.world.phys.BlockHitResult;
import net.minecraft.world.phys.shapes.CollisionContext;
import net.minecraft.world.phys.shapes.Shapes;
import net.minecraft.world.phys.shapes.VoxelShape;
import org.jetbrains.annotations.Nullable;

public final class HandBlock extends BaseEntityBlock {
 public static final MapCodec<HandBlock> CODEC=MapCodec.unit(()->new HandBlock(BlockBehaviour.Properties.of()));
 public static final IntegerProperty CARDS=IntegerProperty.create("cards",0,20);
 private static final VoxelShape SHAPE=Shapes.or(
  Block.box(2,0,2,14,3,14),
  Block.box(4,3,4,12,12,12),
  Block.box(1,12,1,15,16,15)
 );
 public HandBlock(Properties p){super(p);registerDefaultState(stateDefinition.any().setValue(CARDS,0));}
 public static int visualStage(int count){
  if(count<=13)return Math.max(0,count);
  return Math.clamp(14+(Math.max(14,count)-14)/13,14,20);
 }
 @Override protected void createBlockStateDefinition(StateDefinition.Builder<Block,BlockState> builder){builder.add(CARDS);}
 @Override protected MapCodec<? extends BaseEntityBlock> codec(){return CODEC;}
 @Override public RenderShape getRenderShape(BlockState state){return RenderShape.MODEL;}
 @Override protected VoxelShape getShape(BlockState state,BlockGetter level,BlockPos pos,CollisionContext context){return SHAPE;}
 @Override protected VoxelShape getCollisionShape(BlockState state,BlockGetter level,BlockPos pos,CollisionContext context){return SHAPE;}
 @Override protected boolean useShapeForLightOcclusion(BlockState state){return true;}
 @Override public @Nullable BlockEntity newBlockEntity(BlockPos pos,BlockState state){return new HandBlockEntity(pos,state);}

 @Override protected InteractionResult useItemOn(ItemStack held,BlockState state,Level level,BlockPos pos,Player player,InteractionHand hand,BlockHitResult hit){
  if(!held.is(ModItemTags.TCG_CARD))return useWithoutItem(state,level,pos,player,hit);
  if(player instanceof ServerPlayer sp)HandLogic.depositHeld(sp,pos,held);
  return InteractionResult.SUCCESS;
 }

 @Override protected InteractionResult useWithoutItem(BlockState state,Level level,BlockPos pos,Player player,BlockHitResult hit){
  if(player instanceof ServerPlayer sp)HandLogic.open(sp,pos);
  return InteractionResult.SUCCESS;
 }
 @Override public void setPlacedBy(Level level,BlockPos pos,BlockState state,@Nullable LivingEntity placer,ItemStack stack){
  super.setPlacedBy(level,pos,state,placer,stack);
  if(placer instanceof Player p&&level.getBlockEntity(pos) instanceof HandBlockEntity hand)hand.ensureOwner(p);
 }
 @Override protected void affectNeighborsAfterRemoval(BlockState state,ServerLevel level,BlockPos pos,boolean moved){
  if(level.getBlockState(pos).getBlock()!=this&&level.getBlockEntity(pos) instanceof HandBlockEntity hand)Containers.dropContents(level,pos,hand);
  super.affectNeighborsAfterRemoval(state,level,pos,moved);
 }
}
