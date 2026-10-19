package dev.casz.caszualmtg;

import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.entity.Display;
import net.minecraft.world.entity.EntityTypes;
import net.minecraft.world.entity.animal.golem.IronGolem;
import net.minecraft.world.item.ItemDisplayContext;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.phys.AABB;

import java.util.*;

/**
 * One client-rendered, static multi-cube Brass Squire item model per AI seat.
 * Underlying iron golem remains the server-side interaction and game identity.
 * An existing custom-model display is reused after chunk/server reloads.
 */
public final class CommanderGolemVisuals {
 private static final String VISUAL="caszual_mtg_squire_visual";
 private static final String FOR="caszual_mtg_squire_owner_";
 private CommanderGolemVisuals(){}

 public static void ensure(ServerLevel world,IronGolem golem){
  if(!golem.entityTags().contains(CommanderGolems.TAG))return;
  golem.setInvisible(true);
  String id=FOR+golem.getUUID();
  var nearby=world.getEntitiesOfClass(Display.ItemDisplay.class,golem.getBoundingBox().inflate(2.0),
    d->d.entityTags().contains(VISUAL)&&d.entityTags().contains(id));
  Display.ItemDisplay display;
  if(nearby.isEmpty()){
   display=new Display.ItemDisplay(EntityTypes.ITEM_DISPLAY,world);
   display.addTag(VISUAL);
   display.addTag(id);
   display.setItemStack(new ItemStack(CaszualMtg.COMMANDER_GOLEM));
   display.setItemTransform(ItemDisplayContext.FIXED);
   display.setNoGravity(true);
   display.setPos(golem.getX(),golem.getY()+.14,golem.getZ());
   display.setYRot(golem.getYRot());
   world.addFreshEntity(display);
  }else{
   display=nearby.getFirst();
   for(int i=1;i<nearby.size();i++)nearby.get(i).discard();
   if(!display.getItemStack().is(CaszualMtg.COMMANDER_GOLEM))
    display.setItemStack(new ItemStack(CaszualMtg.COMMANDER_GOLEM));
   display.setPos(golem.getX(),golem.getY()+.14,golem.getZ());
   display.setYRot(golem.getYRot());
  }
 }

 /** Remove only detached Caszual model displays. Do not touch other mods'
  * display entities, and don't force-load any chunks to check owners. */
 public static void prune(ServerLevel world,net.minecraft.server.level.ServerPlayer observer){
  if(world.getGameTime()%200!=0)return;
  for(Display.ItemDisplay d:world.getEntitiesOfClass(Display.ItemDisplay.class,
    observer.getBoundingBox().inflate(32),it->it.entityTags().contains(VISUAL))){
   var owners=world.getEntitiesOfClass(IronGolem.class,d.getBoundingBox().inflate(2),
     g->g.entityTags().contains(CommanderGolems.TAG)&&d.entityTags().contains(FOR+g.getUUID()));
   if(owners.isEmpty())d.discard();
  }
 }
}
