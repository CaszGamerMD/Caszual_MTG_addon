package dev.casz.mtg;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.resources.Identifier;
import net.minecraft.world.level.block.*;
/** Material is a registry ID, so vanilla and modded blocks work without enumerating them. */
public interface BoxMaterial {
 String companion$material();
 void companion$material(String material);
 String DEFAULT="minecraft:spruce_planks";
 static String safe(String id){Identifier parsed=Identifier.tryParse(id);return parsed!=null&&BuiltInRegistries.BLOCK.containsKey(parsed)&&!BuiltInRegistries.BLOCK.getValue(parsed).defaultBlockState().isAir()?parsed.toString():DEFAULT;}
 static Block block(String id){return BuiltInRegistries.BLOCK.getValue(Identifier.parse(safe(id)));}
}
