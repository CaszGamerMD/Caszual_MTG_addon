package dev.casz.caszualmtg;
import dev.casz.caszualmtg.mixin.ItemLayersAccess;
import net.fabricmc.fabric.api.client.model.loading.v1.ModelLoadingPlugin;
import net.fabricmc.fabric.api.client.model.loading.v1.wrapper.*;
import net.fabricmc.fabric.api.client.renderer.v1.mesh.QuadEmitter;
import net.minecraft.client.Minecraft;
import net.minecraft.client.model.geom.builders.UVPair;
import net.minecraft.client.renderer.block.BlockAndTintGetter;
import net.minecraft.client.renderer.block.dispatch.*;
import net.minecraft.client.renderer.item.*;
import net.minecraft.client.renderer.texture.TextureAtlasSprite;
import net.minecraft.client.resources.model.geometry.BakedQuad;
import net.minecraft.client.resources.model.sprite.Material;
import net.minecraft.core.*;
import net.minecraft.resources.Identifier;
import net.minecraft.util.RandomSource;
import net.minecraft.world.item.*;
import net.minecraft.world.level.block.state.BlockState;
import java.util.*;
import java.util.function.Predicate;

/** Retarget only spruce-panel quads. MTGCard's original geometry, trim and gold stay intact. */
public final class CustomBoxModels {
 static final Identifier PANELS=Identifier.fromNamespaceAndPath("minecraft","block/spruce_planks");
 static final Identifier CHAIR_SOURCE=Identifier.fromNamespaceAndPath("minecraft","block/oak_planks");
 static final Identifier TABLE_SOURCE=Identifier.fromNamespaceAndPath("minecraft","block/dark_oak_planks");
 public static void register(){ModelLoadingPlugin.register(context->{
  context.modifyBlockModelAfterBake().register((model,ctx)->ctx.state().is(CaszualMtg.CUSTOM_BOX)?new WorldModel(model)
    :ctx.state().is(CaszualMtg.CUSTOM_DECK_CONTROL)||ctx.state().is(CaszualMtg.CUSTOM_GRAVEYARD)?new DeviceWorldModel(model)
    :ctx.state().is(CaszualMtg.MATERIAL_CHAIR)?new ChairWorldModel(model):ctx.state().is(CaszualMtg.TABLETOP)?new TableWorldModel(model):model);
  context.modifyItemModelAfterBake().register((model,ctx)->ctx.itemId().equals(CaszualMtg.id("custom_deckbox"))?new ItemModel(model)
    :ctx.itemId().equals(CaszualMtg.id("custom_deck_control"))||ctx.itemId().equals(CaszualMtg.id("custom_graveyard"))?new DeviceItemModel(model)
    :ctx.itemId().equals(CaszualMtg.id("material_chair"))?new ChairItemModel(model):ctx.itemId().equals(CaszualMtg.id("tabletop"))?new TableItemModel(model):model);
 });}
 static Material.Baked material(String id){return Minecraft.getInstance().getModelManager().getBlockStateModelSet().getParticleMaterial(BoxMaterial.block(id).defaultBlockState());}
 static Material.Baked chairMaterial(String id){return Minecraft.getInstance().getModelManager().getBlockStateModelSet().getParticleMaterial(ChairWood.block(id).defaultBlockState());}
 static String tableSkin(BlockAndTintGetter level,BlockPos pos){
  Object data=level.getBlockEntityRenderData(pos);
  if(data instanceof TabletopBlockEntity.RenderData render)return ChairWood.safe(render.wood());
  return data instanceof String id?ChairWood.safe(id):"minecraft:dark_oak_planks";
 }
 static int chairPaperRgb(BlockAndTintGetter level,BlockPos pos){
  Object data=level.getBlockEntityRenderData(pos);
  return data instanceof ChairBlockEntity.RenderData render?render.paperRgb():0xFFFFFF;
 }
 static String chairSkin(BlockAndTintGetter level,BlockPos pos){
  Object data=level.getBlockEntityRenderData(pos);
  if(data instanceof ChairBlockEntity.RenderData render)return ChairWood.safe(render.wood());
  return data instanceof String id?ChairWood.safe(id):ChairWood.DEFAULT;
 }
 static String skin(BlockAndTintGetter level,BlockPos pos){Object data=level.getBlockEntityRenderData(pos);return data instanceof String id?BoxMaterial.safe(id):BoxMaterial.DEFAULT;}
 public static BakedQuad remap(BakedQuad quad,Material.Baked material){return remap(quad,material,PANELS);}
 public static BakedQuad remap(BakedQuad quad,Material.Baked material,Identifier source){
  var info=quad.materialInfo();var old=info.sprite();if(!old.contents().name().equals(source))return quad;TextureAtlasSprite next=material.sprite();
  long[] uv=new long[4];for(int i=0;i<4;i++){long p=quad.packedUV(i);float u=(UVPair.unpackU(p)-old.getU0())/(old.getU1()-old.getU0()),v=(UVPair.unpackV(p)-old.getV0())/(old.getV1()-old.getV0());uv[i]=UVPair.pack(next.getU(u),next.getV(v));}
  var newInfo=BakedQuad.MaterialInfo.of(material,next.transparency(),-1,info.shade(),info.lightEmission());
  return new BakedQuad(quad.position0(),quad.position1(),quad.position2(),quad.position3(),uv[0],uv[1],uv[2],uv[3],quad.direction(),newInfo);
 }
 static int flags(Material.Baked material){return BakedQuad.MaterialInfo.of(material,material.sprite().transparency(),-1,true,0).flags();}
 static final class Part implements BlockStateModelPart {
  final BlockStateModelPart parent;final Material.Baked material;
  Part(BlockStateModelPart parent,Material.Baked material){this.parent=parent;this.material=material;}
  public List<BakedQuad> getQuads(Direction direction){return parent.getQuads(direction).stream().map(q->remap(q,material)).toList();}
  public boolean useAmbientOcclusion(){return parent.useAmbientOcclusion();}
  public Material.Baked particleMaterial(){return material;}
  public int materialFlags(){return parent.materialFlags()|flags(material);}
 }
 static final class WorldModel extends WrapperBlockStateModel {
  WorldModel(BlockStateModel model){super(model);}
  @Override public void emitQuads(QuadEmitter emitter,BlockAndTintGetter level,BlockPos pos,BlockState state,RandomSource random,Predicate<Direction> cull){Material.Baked skin=material(skin(level,pos));List<BlockStateModelPart> parts=new ArrayList<>();wrapped.collectParts(random,parts);for(var part:parts)new Part(part,skin).emitQuads(emitter,cull);}
  @Override public boolean hasMaterialFlag(BlockAndTintGetter level,BlockPos pos,BlockState state,RandomSource random,int flag){return (materialFlags(level,pos,state,random)&flag)!=0;}
  @Override public Object createGeometryKey(BlockAndTintGetter level,BlockPos pos,BlockState state,RandomSource random){return List.of(state,skin(level,pos));}
  @Override public Material.Baked particleMaterial(BlockAndTintGetter level,BlockPos pos,BlockState state){return material(skin(level,pos));}
  @Override public int materialFlags(BlockAndTintGetter level,BlockPos pos,BlockState state,RandomSource random){return wrapped.materialFlags()|flags(material(skin(level,pos)));}
 }
 /** Generic chair base uses oak plank quads as a geometry placeholder. Only
  * those quads are reskinned: cushion colors remain untouched. */
 static final class ChairPart implements BlockStateModelPart {
  final BlockStateModelPart parent;final Material.Baked material;
  ChairPart(BlockStateModelPart parent,Material.Baked material){this.parent=parent;this.material=material;}
  public List<BakedQuad> getQuads(Direction side){
   return parent.getQuads(side).stream().map(q->remap(q,material,CHAIR_SOURCE)).toList();
  }
  public boolean useAmbientOcclusion(){return parent.useAmbientOcclusion();}
  public Material.Baked particleMaterial(){return material;}
  public int materialFlags(){return parent.materialFlags()|flags(material);}
 }
 static final class ChairWorldModel extends WrapperBlockStateModel {
  ChairWorldModel(BlockStateModel model){super(model);}
  @Override public void emitQuads(QuadEmitter emitter,BlockAndTintGetter level,BlockPos pos,BlockState state,RandomSource random,Predicate<Direction> cull){
   Material.Baked material=chairMaterial(chairSkin(level,pos));
   List<BlockStateModelPart> parts=new ArrayList<>();
   wrapped.collectParts(random,parts);
   for(var part:parts)new ChairPart(part,material).emitQuads(emitter,cull);
  }
  @Override public Object createGeometryKey(BlockAndTintGetter level,BlockPos pos,BlockState state,RandomSource random){
   return List.of(state,chairSkin(level,pos),
    state.getValue(ChairBlock.CUSHION)==ChairBlock.Cushion.PAPER?chairPaperRgb(level,pos):-1);
  }
  @Override public Material.Baked particleMaterial(BlockAndTintGetter level,BlockPos pos,BlockState state){
   return chairMaterial(chairSkin(level,pos));
  }
  @Override public int materialFlags(BlockAndTintGetter level,BlockPos pos,BlockState state,RandomSource random){
   return wrapped.materialFlags()|flags(chairMaterial(chairSkin(level,pos)));
  }
 }
 /** Only frame planks are retargeted; wool playmat and placed-card markers
  * retain their own textures in the multipart table model. */
 static final class TablePart implements BlockStateModelPart {
  final BlockStateModelPart original;final Material.Baked wood;
  TablePart(BlockStateModelPart original,Material.Baked wood){this.original=original;this.wood=wood;}
  public List<BakedQuad> getQuads(Direction side){
   return original.getQuads(side).stream().map(q->remap(q,wood,TABLE_SOURCE)).toList();
  }
  public boolean useAmbientOcclusion(){return original.useAmbientOcclusion();}
  public Material.Baked particleMaterial(){return wood;}
  public int materialFlags(){return original.materialFlags()|flags(wood);}
 }
 static final class TableWorldModel extends WrapperBlockStateModel {
  TableWorldModel(BlockStateModel model){super(model);}
  @Override public void emitQuads(QuadEmitter emitter,BlockAndTintGetter level,BlockPos pos,BlockState state,RandomSource random,Predicate<Direction> cull){
   Material.Baked wood=chairMaterial(tableSkin(level,pos));
   List<BlockStateModelPart> parts=new ArrayList<>();
   wrapped.collectParts(random,parts);
   for(var part:parts)new TablePart(part,wood).emitQuads(emitter,cull);
  }
  @Override public Object createGeometryKey(BlockAndTintGetter level,BlockPos pos,BlockState state,RandomSource random){
   return List.of(state,tableSkin(level,pos));
  }
  @Override public Material.Baked particleMaterial(BlockAndTintGetter level,BlockPos pos,BlockState state){
   return chairMaterial(tableSkin(level,pos));
  }
  @Override public int materialFlags(BlockAndTintGetter level,BlockPos pos,BlockState state,RandomSource random){
   return wrapped.materialFlags()|flags(chairMaterial(tableSkin(level,pos)));
  }
 }
 /** Retarget only the wooden panels of new native-compatible MTGCard
  * devices. Their original status lights, inked face, hinges and icons stay. */
 static String deviceSkin(BlockAndTintGetter level,BlockPos pos){
  Object data=level.getBlockEntityRenderData(pos);
  return data instanceof String material?BoxMaterial.safe(material):BoxMaterial.DEFAULT;
 }
 static final class DeviceWorldModel extends WrapperBlockStateModel {
  DeviceWorldModel(BlockStateModel model){super(model);}
  @Override public void emitQuads(QuadEmitter emitter,BlockAndTintGetter level,BlockPos pos,BlockState state,RandomSource random,Predicate<Direction> cull){
   Material.Baked skin=material(deviceSkin(level,pos));
   List<BlockStateModelPart> parts=new ArrayList<>();
   wrapped.collectParts(random,parts);
   for(var part:parts)new ChairPart(part,skin).emitQuads(emitter,cull);
  }
  @Override public Object createGeometryKey(BlockAndTintGetter level,BlockPos pos,BlockState state,RandomSource random){
   return List.of(state,deviceSkin(level,pos));
  }
  @Override public Material.Baked particleMaterial(BlockAndTintGetter level,BlockPos pos,BlockState state){
   return material(deviceSkin(level,pos));
  }
  @Override public int materialFlags(BlockAndTintGetter level,BlockPos pos,BlockState state,RandomSource random){
   return wrapped.materialFlags()|flags(material(deviceSkin(level,pos)));
  }
 }
 static final class DeviceItemModel extends WrapperBakedItemModel {
  DeviceItemModel(net.minecraft.client.renderer.item.ItemModel model){super(model);}
  @Override public void update(ItemStackRenderState state,ItemStack stack,ItemModelResolver resolver,ItemDisplayContext display,
       net.minecraft.client.multiplayer.ClientLevel level,net.minecraft.world.entity.ItemOwner owner,int seed){
   int first=((ItemLayersAccess)state).companion$layerCount();
   wrapped.update(state,stack,resolver,display,level,owner,seed);
   String selected=BoxMaterial.safe(stack.getOrDefault(CaszualMtg.BOX_MATERIAL,BoxMaterial.DEFAULT));
   Material.Baked skin=material(selected);
   var access=(ItemLayersAccess)state;
   for(int i=first;i<access.companion$layerCount();i++){
    var layer=access.companion$layers()[i];
    layer.prepareQuadList().replaceAll(q->remap(q,skin,CHAIR_SOURCE));
    layer.setParticleMaterial(skin);
   }
   state.appendModelIdentityElement(selected);
   if(skin.sprite().isAnimated())state.setAnimated();
  }
 }
 static final class TableItemModel extends WrapperBakedItemModel {
  TableItemModel(net.minecraft.client.renderer.item.ItemModel model){super(model);}
  @Override public void update(ItemStackRenderState state,ItemStack stack,ItemModelResolver resolver,ItemDisplayContext display,
      net.minecraft.client.multiplayer.ClientLevel level,net.minecraft.world.entity.ItemOwner owner,int seed){
   int first=((ItemLayersAccess)state).companion$layerCount();
   wrapped.update(state,stack,resolver,display,level,owner,seed);
   String id=ChairWood.safe(stack.getOrDefault(CaszualMtg.TABLE_MATERIAL,"minecraft:dark_oak_planks"));
   Material.Baked wood=chairMaterial(id);
   var access=(ItemLayersAccess)state;
   for(int i=first;i<access.companion$layerCount();i++){
    var layer=access.companion$layers()[i];
    layer.prepareQuadList().replaceAll(q->remap(q,wood,TABLE_SOURCE));
    layer.setParticleMaterial(wood);
   }
   state.appendModelIdentityElement(id);
   if(wood.sprite().isAnimated())state.setAnimated();
  }
 }
 static final class ChairItemModel extends WrapperBakedItemModel {
  ChairItemModel(net.minecraft.client.renderer.item.ItemModel model){super(model);}
  @Override public void update(ItemStackRenderState state,ItemStack stack,ItemModelResolver resolver,ItemDisplayContext display,
     net.minecraft.client.multiplayer.ClientLevel level,net.minecraft.world.entity.ItemOwner owner,int seed){
   int first=((ItemLayersAccess)state).companion$layerCount();
   wrapped.update(state,stack,resolver,display,level,owner,seed);
   String id=ChairWood.safe(stack.getOrDefault(CaszualMtg.CHAIR_MATERIAL,ChairWood.DEFAULT));
   Material.Baked material=chairMaterial(id);
   var access=(ItemLayersAccess)state;
   for(int i=first;i<access.companion$layerCount();i++){
    var layer=access.companion$layers()[i];
    var quads=layer.prepareQuadList();
    quads.replaceAll(q->remap(q,material,CHAIR_SOURCE));
    layer.setParticleMaterial(material);
   }
   state.appendModelIdentityElement(id);
   if(material.sprite().isAnimated())state.setAnimated();
  }
 }
 static final class ItemModel extends WrapperBakedItemModel {
  ItemModel(net.minecraft.client.renderer.item.ItemModel model){super(model);}
  @Override public void update(ItemStackRenderState state,ItemStack stack,ItemModelResolver resolver,ItemDisplayContext display,net.minecraft.client.multiplayer.ClientLevel level,net.minecraft.world.entity.ItemOwner owner,int seed){int first=((ItemLayersAccess)state).companion$layerCount();wrapped.update(state,stack,resolver,display,level,owner,seed);String id=BoxMaterial.safe(stack.getOrDefault(CaszualMtg.BOX_MATERIAL,BoxMaterial.DEFAULT));var material=material(id);var access=(ItemLayersAccess)state;for(int i=first;i<access.companion$layerCount();i++){var layer=access.companion$layers()[i];var quads=layer.prepareQuadList();quads.replaceAll(q->remap(q,material));layer.setParticleMaterial(material);}state.appendModelIdentityElement(id);if(material.sprite().isAnimated())state.setAnimated();}
 }
}
