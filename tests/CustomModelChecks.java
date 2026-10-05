package dev.casz.mtg;
import com.mojang.blaze3d.platform.NativeImage;
import net.minecraft.client.renderer.texture.*;
import net.minecraft.client.resources.metadata.animation.FrameSize;
import net.minecraft.client.resources.model.sprite.Material;
import net.minecraft.client.resources.model.geometry.BakedQuad;
import net.minecraft.client.model.geom.builders.UVPair;
import net.minecraft.core.Direction;
import net.minecraft.resources.Identifier;
import org.joml.Vector3f;
public final class CustomModelChecks {
 static TextureAtlasSprite sprite(String name,int x)throws Exception {
  var image=new NativeImage(16,16,true);for(int px=0;px<16;px++)for(int py=0;py<16;py++)image.setPixel(px,py,0xffffffff);
  var contents=new SpriteContents(Identifier.parse(name),new FrameSize(16,16),image);
  var constructor=TextureAtlasSprite.class.getDeclaredConstructor(Identifier.class,SpriteContents.class,int.class,int.class,int.class,int.class,int.class);constructor.setAccessible(true);return constructor.newInstance(Identifier.parse("minecraft:textures/atlas/blocks.png"),contents,128,128,x,0,0);
 }
 static BakedQuad quad(TextureAtlasSprite sprite){long a=UVPair.pack(sprite.getU(.2f),sprite.getV(.3f)),b=UVPair.pack(sprite.getU(.8f),sprite.getV(.9f));var info=BakedQuad.MaterialInfo.of(new Material.Baked(sprite,false),sprite.transparency(),-1,true,0);return new BakedQuad(new Vector3f(0,0,0),new Vector3f(0,1,0),new Vector3f(1,1,0),new Vector3f(1,0,0),a,a,b,b,Direction.NORTH,info);}
 public static void run()throws Exception{var panel=sprite("minecraft:block/spruce_planks",0);var gold=sprite("mtgcard:block/deckbox",32);var diamond=sprite("minecraft:block/diamond_block",64);try{var target=new Material.Baked(diamond,false);var original=quad(panel);var changed=CustomBoxModels.remap(original,target);if(changed.materialInfo().sprite()!=diamond||!changed.position0().equals(original.position0()))throw new AssertionError("Retexture must preserve shape and replace panel material");float u=(UVPair.unpackU(changed.packedUV0())-diamond.getU0())/(diamond.getU1()-diamond.getU0());if(Math.abs(u-.2f)>.00001f)throw new AssertionError("UV coordinates preserved within selected texture");var trim=quad(gold);if(CustomBoxModels.remap(trim,target)!=trim)throw new AssertionError("Brown edging/gold geometry must remain unchanged");System.out.println("MTGCOMPANION_MODEL_CHECK_PASS: panel substitution, UVs, geometry, original brown/gold trim");}finally{panel.contents().close();gold.contents().close();diamond.contents().close();}}
}
