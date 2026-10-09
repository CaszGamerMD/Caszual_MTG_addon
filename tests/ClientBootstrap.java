import net.fabricmc.loader.impl.launch.knot.Knot;
import net.fabricmc.api.EnvType;
import java.lang.reflect.*;
public final class ClientBootstrap {
 public static void main(String[] args)throws Exception {
  ClassLoader cl=new Knot(EnvType.CLIENT).init(new String[]{"--version","26.2","--gameDir","."});
  Thread.currentThread().setContextClassLoader(cl);
  Class.forName("net.minecraft.SharedConstants",true,cl).getMethod("tryDetectVersion").invoke(null);
  Class.forName("net.minecraft.server.Bootstrap",true,cl).getMethod("bootStrap").invoke(null);
  Class.forName("dev.casz.caszualmtg.CaszualMtg",true,cl).getConstructor().newInstance();
  Class.forName("dev.casz.caszualmtg.CaszualMtgClient",true,cl).getConstructor().newInstance();
  Class.forName("dev.casz.caszualmtg.CommunityScreen",true,cl);
  Class.forName("dev.casz.caszualmtg.CustomBoxModels",true,cl);Class.forName("net.minecraft.client.renderer.item.ItemStackRenderState",true,cl);
  Class.forName("com.spider.mtgcard.deckbox.DeckboxBlockEntity",true,cl);
  Class<?> renderer=Class.forName("com.spider.mtgcard.client.display.CardDisplayEntityRenderer",true,cl);
  Class<?> tag=Class.forName("net.minecraft.nbt.CompoundTag",true,cl);Object meta=tag.getConstructor().newInstance(), counters=tag.getConstructor().newInstance();tag.getMethod("putInt",String.class,int.class).invoke(counters,"charge",5);tag.getMethod("put",String.class,Class.forName("net.minecraft.nbt.Tag",true,cl)).invoke(meta,"counters",counters);
  Method build=renderer.getDeclaredMethod("buildCounterIcons",tag);build.setAccessible(true);var icons=(java.util.List<?>)build.invoke(null,meta);if(icons.size()!=5)throw new AssertionError("Counter mixin did not supply five markers");tag.getMethod("putInt",String.class,int.class).invoke(counters,"charge",50);if(((java.util.List<?>)build.invoke(null,meta)).size()!=12)throw new AssertionError("Visual marker cap");
  Class.forName("dev.casz.caszualmtg.CustomModelChecks",true,cl).getMethod("run").invoke(null);
  System.out.println("MTGCOMPANION_CLIENT_BOOTSTRAP_PASS: entrypoints, menu screen, renderer mixins, counter growth and cap");
 }
}
