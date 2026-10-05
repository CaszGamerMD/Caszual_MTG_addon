package dev.casz.mtg.mixin;
import com.spider.mtgcard.client.display.CardDisplayEntityRenderer;
import com.spider.mtgcard.client.display.CardDisplayEntityRenderer.CounterIcon;
import com.mojang.blaze3d.vertex.*;
import net.minecraft.client.renderer.*;
import net.minecraft.client.renderer.rendertype.RenderTypes;
import net.minecraft.client.renderer.texture.OverlayTexture;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.resources.Identifier;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.*;
import org.spongepowered.asm.mixin.injection.callback.*;
import java.util.*;

/** A pile per counter type, capped visually at 12 markers; exact amounts remain in the HUD. */
@Mixin(CardDisplayEntityRenderer.class)
public abstract class CounterRendererMixin {
 @Inject(method="buildCounterIcons",at=@At("HEAD"),cancellable=true,remap=false)
 private static void companion$icons(CompoundTag meta,CallbackInfoReturnable<List<CounterIcon>> ci){var counters=meta.getCompound("counters").orElse(null);if(counters==null)return;var icons=meta.getCompound("counter_icons").orElse(new CompoundTag());List<CounterIcon> result=new ArrayList<>();counters.keySet().stream().sorted(String.CASE_INSENSITIVE_ORDER).filter(k->counters.getInt(k).orElse(0)>0).limit(6).forEach(k->{String icon=icons.getString(k).orElse("none");Identifier texture=icon.equals("none")?Identifier.fromNamespaceAndPath("mtgcompanion","textures/gui/counter_marker.png"):Identifier.fromNamespaceAndPath("mtgcard","textures/gui/counters/"+icon+".png");for(int i=0;i<Math.min(12,counters.getInt(k).orElse(0));i++)result.add(new CounterIcon(texture));});ci.setReturnValue(List.copyOf(result));}
 @Inject(method="renderCounterStripOnCard",at=@At("HEAD"),cancellable=true,remap=false)
 private void companion$piles(List<CounterIcon> icons,PoseStack pose,SubmitNodeCollector collector,CallbackInfo ci){ci.cancel();if(icons==null||icons.isEmpty())return;int group=-1,level=0;Identifier previous=null;for(var icon:icons){if(!icon.texture().equals(previous)||level>=12){group++;level=0;previous=icon.texture();}float x=-.46f,y=.45f-group*.13f,z=.014f+level*.006f,shift=level*.005f;level++;pose.pushPose();pose.translate(shift,shift,z);collector.submitCustomGeometry(pose,RenderTypes.entityCutout(icon.texture()),(p,v)->{vertex(v,p,x,y-.10f,0,1);vertex(v,p,x,y,0,0);vertex(v,p,x+.10f,y,1,0);vertex(v,p,x+.10f,y-.10f,1,1);});pose.popPose();}}
 private static void vertex(VertexConsumer v,PoseStack.Pose p,float x,float y,float u,float t){v.addVertex(p.pose(),x,y,0).setColor(255,255,255,255).setUv(u,t).setOverlay(OverlayTexture.NO_OVERLAY).setLight(15728880).setNormal(p,0,0,1);}
}
