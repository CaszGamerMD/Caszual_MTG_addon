package dev.casz.caszualmtg;

import com.mojang.serialization.MapCodec;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.level.block.entity.BlockEntity;
import net.minecraft.world.level.storage.loot.LootParams;
import net.minecraft.world.level.storage.loot.parameters.LootContextParams;
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
public class ChairBlock extends BaseEntityBlock {
 public enum Cushion implements net.minecraft.util.StringRepresentable {
  NONE("none"), WOOL("wool"), LEATHER("leather"), PAPER("paper");
  private final String name;Cushion(String name){this.name=name;}
  @Override public String getSerializedName(){return name;}
 }
 public static final EnumProperty<Direction> FACING=BlockStateProperties.HORIZONTAL_FACING;
 public static final EnumProperty<Cushion> CUSHION=EnumProperty.create("cushion",Cushion.class);
 public static final EnumProperty<DyeColor> COLOR=EnumProperty.create("color",DyeColor.class);
 private final MapCodec<ChairBlock> codec;
 // Follow all eight cuboids in models/block/material_chair.json: four legs,
 // the half-slab seat, two back uprights and the high back crossbar.
 // A VoxelShape never follows a blockstate model's "y" rotation automatically.
 private static final VoxelShape NORTH_SHAPE=Shapes.or(
  Block.box(1,0,1,3,7,3), Block.box(13,0,1,15,7,3),
  Block.box(1,0,13,3,7,15), Block.box(13,0,13,15,7,15),
  Block.box(0,7,0,16,8,16),
  Block.box(0,8,14,2,14,16), Block.box(14,8,14,16,14,16),
  Block.box(0,14,14,16,16,16)
 ).optimize();
 // Blockstate rotations: north=0, east=90, south=180, west=270.
 private static final VoxelShape EAST_SHAPE=rotateClockwise(NORTH_SHAPE);
 private static final VoxelShape SOUTH_SHAPE=rotateClockwise(EAST_SHAPE);
 private static final VoxelShape WEST_SHAPE=rotateClockwise(SOUTH_SHAPE);

 private static VoxelShape rotateClockwise(VoxelShape source){
  VoxelShape rotated=Shapes.empty();
  // Minecraft blockstate model 'y':90 rotates the south/back edge
  // towards WEST, not east. The earlier AABB transform rotated the
  // opposite way, so EAST and WEST chairs had mirrored collision.
  // Map (x,z) -> (1-z,x) and preserve all Y coordinates.
  // NORTH and SOUTH remain unchanged; E/W now match the baked model.
  for(var box:source.toAabbs()){
   rotated=Shapes.or(rotated,Block.box(
    (1-box.maxZ)*16,box.minY*16,box.minX*16,
    (1-box.minZ)*16,box.maxY*16,box.maxX*16
   ));
  }
  return rotated.optimize();
 }
 private static VoxelShape shapeFor(BlockState state){
  return switch(state.getValue(FACING)){
   case NORTH -> NORTH_SHAPE;
   case EAST -> EAST_SHAPE;
   case SOUTH -> SOUTH_SHAPE;
   case WEST -> WEST_SHAPE;
   default -> NORTH_SHAPE;
  };
 }
 public ChairBlock(Properties props){
  super(props);
  codec=MapCodec.unit(()->new ChairBlock(Properties.of()));
  registerDefaultState(stateDefinition.any().setValue(FACING,Direction.NORTH)
      .setValue(CUSHION,Cushion.NONE).setValue(COLOR,DyeColor.WHITE));
 }
 @Override protected MapCodec<? extends BaseEntityBlock> codec(){return codec;}
 @Override public RenderShape getRenderShape(BlockState s){return RenderShape.MODEL;}
 @Override public @Nullable BlockEntity newBlockEntity(BlockPos pos,BlockState state){return new ChairBlockEntity(pos,state);}
 @Override public void setPlacedBy(Level level,BlockPos pos,BlockState state,@Nullable LivingEntity placer,ItemStack stack){
  super.setPlacedBy(level,pos,state,placer,stack);
  if(level.getBlockEntity(pos) instanceof ChairBlockEntity chair)
   chair.material(stack.getOrDefault(CaszualMtg.CHAIR_MATERIAL,ChairWood.DEFAULT));
 }
 @Override protected ItemStack getCloneItemStack(LevelReader level,BlockPos pos,BlockState state,boolean includeData){
  ItemStack stack=new ItemStack(this);
  if(level.getBlockEntity(pos) instanceof ChairBlockEntity chair)
   stack.set(CaszualMtg.CHAIR_MATERIAL,chair.material());
  return stack;
 }
 @Override protected java.util.List<ItemStack> getDrops(BlockState state,LootParams.Builder params){
  ItemStack result=new ItemStack(this);
  BlockEntity entity=params.getOptionalParameter(LootContextParams.BLOCK_ENTITY);
  if(entity instanceof ChairBlockEntity chair)result.set(CaszualMtg.CHAIR_MATERIAL,chair.material());
  return java.util.List.of(result);
 }
 @Override protected void createBlockStateDefinition(StateDefinition.Builder<Block,BlockState> b){
  b.add(FACING,CUSHION,COLOR);
 }
 @Override public BlockState getStateForPlacement(BlockPlaceContext c){
  BlockState state=defaultBlockState().setValue(FACING,c.getHorizontalDirection().getOpposite());
  return state;
 }
 @Override protected VoxelShape getShape(BlockState state,BlockGetter level,BlockPos pos,CollisionContext context){return shapeFor(state);}
 @Override protected VoxelShape getCollisionShape(BlockState state,BlockGetter level,BlockPos pos,CollisionContext context){return shapeFor(state);}
 @Override protected InteractionResult useWithoutItem(BlockState state,Level level,BlockPos pos,Player p,BlockHitResult hit){
  if(p instanceof ServerPlayer sp)ChairSeats.sit(sp,pos);
  return InteractionResult.SUCCESS;
 }
 @Override protected InteractionResult useItemOn(ItemStack stack,BlockState state,Level level,BlockPos pos,Player p,InteractionHand hand,BlockHitResult hit){
  BlockState next=null;boolean consumed=false;
  if(stack.is(Items.PAPER)){
   next=state.setValue(CUSHION,Cushion.PAPER);
   consumed=true;
  }else if(stack.is(Items.LEATHER)){
   next=state.setValue(CUSHION,Cushion.LEATHER).setValue(COLOR,DyeColor.BROWN);consumed=true;
  }else if(stack.getItem() instanceof DyeItem dye&&state.getValue(CUSHION)==Cushion.LEATHER){
   // Dyes recolor the leather cushion without replacing it.
   String dyeId=BuiltInRegistries.ITEM.getKey(stack.getItem()).getPath();
   try{next=state.setValue(COLOR,DyeColor.valueOf(dyeId.replace("_dye","").toUpperCase(Locale.ROOT)));consumed=true;}
   catch(IllegalArgumentException ignored){}
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
  if(next==null&&ChairWood.eligible(stack)){
   if(!level.isClientSide()&&level.getBlockEntity(pos) instanceof ChairBlockEntity chair){
    chair.material(ChairWood.fromItem(stack));
    if(!p.getAbilities().instabuild)stack.shrink(1);
   }
   return InteractionResult.SUCCESS;
  }
  if(next==null)return useWithoutItem(state,level,pos,p,hit);
  if(!level.isClientSide()){
   level.setBlock(pos,next,Block.UPDATE_ALL);
   if(next.getValue(CUSHION)==Cushion.PAPER)refreshPaperColor(level,pos);
   if(consumed&&!p.getAbilities().instabuild)stack.shrink(1);
  }
  return InteractionResult.SUCCESS;
 }
 /** A paper cushion uses the adjacent table's full RGB value, not its old
  * nearest-wool blockstate. It stays independent of the wool/leather colors. */
 public static void refreshPaperColor(Level level,BlockPos chairPos){
  if(level.isClientSide())return;
  BlockState state=level.getBlockState(chairPos);
  if(!(state.getBlock() instanceof ChairBlock)||state.getValue(CUSHION)!=Cushion.PAPER)return;
  int rgb=0xFFFFFF;
  for(Direction d:Direction.Plane.HORIZONTAL){
   if(level.getBlockEntity(chairPos.relative(d)) instanceof TabletopBlockEntity table){
    rgb=table.matRgb();
    break;
   }
  }
  if(level.getBlockEntity(chairPos) instanceof ChairBlockEntity chair)chair.paperRgb(rgb);
 }
 public static void refreshNextToTable(Level level,BlockPos tablePos){
  if(level.isClientSide())return;
  for(Direction d:Direction.Plane.HORIZONTAL)
   refreshPaperColor(level,tablePos.relative(d));
 }
 @Override public void onPlace(BlockState state,Level level,BlockPos pos,BlockState old,boolean moved){
  super.onPlace(state,level,pos,old,moved);
  if(!level.isClientSide()&&state.getValue(CUSHION)==Cushion.PAPER)
   refreshPaperColor(level,pos);
 }
}
