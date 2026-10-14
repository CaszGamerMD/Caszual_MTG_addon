package dev.casz.caszualmtg;

import com.mojang.serialization.MapCodec;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.InteractionHand;
import net.minecraft.world.InteractionResult;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.item.*;
import net.minecraft.world.item.context.BlockPlaceContext;
import net.minecraft.world.level.*;
import net.minecraft.world.level.block.*;
import net.minecraft.world.level.block.state.*;
import net.minecraft.world.level.block.state.properties.*;
import net.minecraft.world.phys.BlockHitResult;
import net.minecraft.world.phys.shapes.*;
import org.jetbrains.annotations.Nullable;
import java.util.Locale;

/** Real sitting chair. The seat top is eight model pixels tall (half slab).
 * Material is set by the crafting wood; cushion items are inserted by right-click. */
public final class ChairBlock extends Block {
 public enum Cushion implements net.minecraft.util.StringRepresentable {
  NONE("none"), WOOL("wool"), LEATHER("leather"), PAPER("paper");
  private final String name;Cushion(String name){this.name=name;}
  @Override public String getSerializedName(){return name;}
 }
 public static final DirectionProperty FACING=BlockStateProperties.HORIZONTAL_FACING;
 public static final EnumProperty<Cushion> CUSHION=EnumProperty.create("cushion",Cushion.class);
 public static final EnumProperty<DyeColor> COLOR=EnumProperty.create("color",DyeColor.class);
 public final String wood;
 private final MapCodec<ChairBlock> codec;
 private static final VoxelShape SHAPE=Shapes.or(Block.box(1,0,1,15,8,15),Block.box(1,8,13,15,16,15));
 public ChairBlock(String wood,Properties props){
  super(props);
  this.wood=wood;
  codec=MapCodec.unit(()->new ChairBlock(wood,Properties.of()));
  registerDefaultState(stateDefinition.any().setValue(FACING,Direction.NORTH)
      .setValue(CUSHION,Cushion.NONE).setValue(COLOR,DyeColor.WHITE));
 }
 @Override protected MapCodec<? extends Block> codec(){return codec;}
 @Override protected void createBlockStateDefinition(StateDefinition.Builder<Block,BlockState> b){
  b.add(FACING,CUSHION,COLOR);
 }
 @Override public BlockState getStateForPlacement(BlockPlaceContext c){
  BlockState state=defaultBlockState().setValue(FACING,c.getHorizontalDirection().getOpposite());
  return matchPaper(c.getLevel(),c.getClickedPos(),state);
 }
 @Override protected VoxelShape getShape(BlockState state,BlockGetter level,BlockPos pos,CollisionContext context){return SHAPE;}
 @Override protected InteractionResult useWithoutItem(BlockState state,Level level,BlockPos pos,Player p,BlockHitResult hit){
  if(p instanceof ServerPlayer sp)ChairSeats.sit(sp,pos);
  return InteractionResult.SUCCESS;
 }
 @Override protected InteractionResult useItemOn(ItemStack stack,BlockState state,Level level,BlockPos pos,Player p,InteractionHand hand,BlockHitResult hit){
  BlockState next=null;boolean consumed=false;
  if(stack.is(Items.PAPER)){
   next=state.setValue(CUSHION,Cushion.PAPER);
   next=matchPaper(level,pos,next);consumed=true;
  }else if(stack.is(Items.LEATHER)){
   next=state.setValue(CUSHION,Cushion.LEATHER).setValue(COLOR,DyeColor.BROWN);consumed=true;
  }else if(stack.getItem() instanceof DyeItem dye&&state.getValue(CUSHION)==Cushion.LEATHER){
   // Dyes recolor the leather cushion without replacing it.
   next=state.setValue(COLOR,dye.getDyeColor());consumed=true;
  }else{
   var key=BuiltInRegistries.BLOCK.getKey(Block.byItem(stack.getItem()));
   String name=key==null?"":key.getPath();
   if(name.endsWith("_wool")){
    String color=name.substring(0,name.length()-5);
    try{
     DyeColor dye=DyeColor.valueOf(color.toUpperCase(Locale.ROOT));
     next=state.setValue(CUSHION,Cushion.WOOL).setValue(COLOR,dye);
     consumed=true;
    }catch(IllegalArgumentException ignored){}
   }
  }
  if(next==null)return useWithoutItem(state,level,pos,p,hit);
  if(!level.isClientSide()){
   level.setBlock(pos,next,Block.UPDATE_ALL);
   if(consumed&&!p.getAbilities().instabuild)stack.shrink(1);
  }
  return InteractionResult.SUCCESS;
 }
 public static BlockState matchPaper(LevelReader level,BlockPos pos,BlockState state){
  if(!(state.getBlock() instanceof ChairBlock)||state.getValue(CUSHION)!=Cushion.PAPER)return state;
  for(Direction d:Direction.Plane.HORIZONTAL){
   BlockState neighbor=level.getBlockState(pos.relative(d));
   if(neighbor.getBlock() instanceof TabletopBlock&&neighbor.hasProperty(TabletopBlock.FELT))
    return state.setValue(COLOR,neighbor.getValue(TabletopBlock.FELT));
  }
  return state;
 }
 public static void refreshNextToTable(Level level,BlockPos tablePos){
  if(level.isClientSide())return;
  for(Direction d:Direction.Plane.HORIZONTAL){
   BlockPos chair=tablePos.relative(d);
   BlockState current=level.getBlockState(chair);
   if(!(current.getBlock() instanceof ChairBlock))continue;
   BlockState next=matchPaper(level,chair,current);
   if(next!=current)level.setBlock(chair,next,Block.UPDATE_ALL);
  }
 }
 @Override public void onPlace(BlockState state,Level level,BlockPos pos,BlockState old,boolean moved){
  super.onPlace(state,level,pos,old,moved);
  if(!level.isClientSide()&&state.getValue(CUSHION)==Cushion.PAPER){
   BlockState matched=matchPaper(level,pos,state);
   if(matched!=state)level.setBlock(pos,matched,Block.UPDATE_ALL);
  }
 }
}
