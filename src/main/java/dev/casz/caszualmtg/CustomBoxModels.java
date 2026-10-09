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
 public static void register(){ModelLoadingPlugin.register(context->{
  context.modifyBlockModelAfterBake().register((model,ctx)->ctx.state().is(CaszualMtg.CUSTOM_BOX)?new WorldModel(model):model);
  context.modifyItemModelAfterBake().register((model,ctx)->ctx.itemId().equals(CaszualMtg.id("custom_deckbox"))?new ItemModel(model):model);
 });}
 static Material.Baked material(String id){return Minecraft.getInstance().getModelManager().getBlockStateModelSet().getParticleMaterial(BoxMaterial.block(id).defaultBlockState());}
 static String skin(BlockAndTintGetter level,BlockPos pos){Object data=level.getBlockEntityRenderData(pos);return data instanceof String id?BoxMaterial.safe(id):BoxMaterial.DEFAULT;}
 public static BakedQuad remap(BakedQuad quad,Material.Baked material){var info=quad.materialInfo();var old=info.sprite();if(!old.contents().name().equals(PANELS))return quad;TextureAtlasSprite next=material.sprite();
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
 static final class ItemModel extends WrapperBakedItemModel {
  ItemModel(net.minecraft.client.renderer.item.ItemModel model){super(model);}
  @Override public void update(ItemStackRenderState state,ItemStack stack,ItemModelResolver resolver,ItemDisplayContext display,net.minecraft.client.multiplayer.ClientLevel level,net.minecraft.world.entity.ItemOwner owner,int seed){int first=((ItemLayersAccess)state).companion$layerCount();wrapped.update(state,stack,resolver,display,level,owner,seed);String id=BoxMaterial.safe(stack.getOrDefault(CaszualMtg.BOX_MATERIAL,BoxMaterial.DEFAULT));var material=material(id);var access=(ItemLayersAccess)state;for(int i=first;i<access.companion$layerCount();i++){var layer=access.companion$layers()[i];var quads=layer.prepareQuadList();quads.replaceAll(q->remap(q,material));layer.setParticleMaterial(material);}state.appendModelIdentityElement(id);if(material.sprite().isAnimated())state.setAnimated();}
 }
}
