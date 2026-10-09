package dev.casz.caszualmtg;
import net.fabricmc.api.ModInitializer;
import net.fabricmc.fabric.api.menu.v1.ExtendedMenuType;
import net.fabricmc.fabric.api.creativetab.v1.CreativeModeTabEvents;
import net.fabricmc.fabric.api.networking.v1.*;
import net.fabricmc.fabric.api.object.builder.v1.block.entity.FabricBlockEntityTypeBuilder;
import net.fabricmc.fabric.api.event.player.UseEntityCallback;
import net.fabricmc.fabric.api.event.player.AttackEntityCallback;
import net.fabricmc.fabric.api.event.player.UseItemCallback;
import net.fabricmc.fabric.api.event.player.UseBlockCallback;
import net.minecraft.core.*;
import net.minecraft.core.registries.*;
import net.minecraft.resources.*;
import net.minecraft.world.*;
import net.minecraft.world.item.*;
import net.minecraft.world.level.*;
import net.minecraft.world.level.block.*;
import net.minecraft.world.level.block.state.*;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.phys.BlockHitResult;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.network.chat.Component;
import com.spider.mtgcard.display.CardDisplayEntity;
import com.spider.mtgcard.deckcontrol.DeckControlBlockEntity;
import com.spider.mtgcard.api.DeckControlActionRegistry;
import com.spider.mtgcard.api.TcgGameRegistry;
import net.minecraft.world.level.block.entity.BlockEntityType;
import java.util.*;
public final class CaszualMtg implements ModInitializer {
 public static Identifier id(String path){return Identifier.fromNamespaceAndPath("caszual_mtg",path);}
 public static final Block LANDS=block("land_database",0),TOKENS=block("token_database",1),CARDS=block("community_database",2),BUILDER=block("deck_builder",3);
 public static final net.minecraft.core.component.DataComponentType<String> BOX_MATERIAL=Registry.register(BuiltInRegistries.DATA_COMPONENT_TYPE,id("box_material"),net.minecraft.core.component.DataComponentType.<String>builder().persistent(com.mojang.serialization.Codec.STRING).networkSynchronized(net.minecraft.network.codec.StreamCodec.of((b,v)->b.writeUtf(v,256),b->b.readUtf(256))).build());
 public static final CustomDeckbox CUSTOM_BOX=customBox();
 public static final HandBlock HAND=handBlock();
 public static final BlockEntityType<HandBlockEntity> HAND_BE=Registry.register(BuiltInRegistries.BLOCK_ENTITY_TYPE,id("hand_block"),FabricBlockEntityTypeBuilder.create(HandBlockEntity::new,HAND).build());
 static HandBlock handBlock(){var key=ResourceKey.create(Registries.BLOCK,id("hand_block"));var block=Registry.register(BuiltInRegistries.BLOCK,key,new HandBlock(BlockBehaviour.Properties.of().setId(key).strength(2.0f).sound(net.minecraft.world.level.block.SoundType.WOOD)));var itemKey=ResourceKey.create(Registries.ITEM,id("hand_block"));Registry.register(BuiltInRegistries.ITEM,itemKey,new BlockItem(block,new Item.Properties().setId(itemKey).useBlockDescriptionPrefix()));return block;}
  static CustomDeckbox customBox(){var key=ResourceKey.create(Registries.BLOCK,id("custom_deckbox"));var block=Registry.register(BuiltInRegistries.BLOCK,key,new CustomDeckbox(BlockBehaviour.Properties.of().setId(key).strength(2.5f).noOcclusion().sound(net.minecraft.world.level.block.SoundType.WOOD)));var itemKey=ResourceKey.create(Registries.ITEM,id("custom_deckbox"));Registry.register(BuiltInRegistries.ITEM,itemKey,new CustomDeckbox.Item(block,new Item.Properties().setId(itemKey).stacksTo(1).useBlockDescriptionPrefix()));return block;}
 public static final Item COUNTER=Registry.register(BuiltInRegistries.ITEM,id("counter"),new Item(new Item.Properties().setId(ResourceKey.create(Registries.ITEM,id("counter"))).stacksTo(1)));
 public static final Item TARGETING_STAFF=Registry.register(BuiltInRegistries.ITEM,id("targeting_staff"),new Item(new Item.Properties().setId(ResourceKey.create(Registries.ITEM,id("targeting_staff"))).stacksTo(1)));
 static Block block(String name,int kind){var key=ResourceKey.create(Registries.BLOCK,id(name));Block b=Registry.register(BuiltInRegistries.BLOCK,key,new BankBlock(BlockBehaviour.Properties.of().setId(key).strength(2.5f),kind));var ik=ResourceKey.create(Registries.ITEM,id(name));Registry.register(BuiltInRegistries.ITEM,ik,new BlockItem(b,new Item.Properties().setId(ik).useBlockDescriptionPrefix()));return b;}
 public static int kind(Block b){return b==LANDS?0:b==TOKENS?1:b==CARDS?2:b==BUILDER?3:-1;}
 public static final ExtendedMenuType<CommunityMenu,CommunityMenu.OpenData> COMMUNITY_MENU=Registry.register(BuiltInRegistries.MENU,id("community"),new ExtendedMenuType<>(CommunityMenu::new,CommunityMenu.OpenData.CODEC));
 public void onInitialize(){
  com.spider.mtgcard.registry.ModBlockEntities.init();com.spider.mtgcard.registry.ModBlockEntities.DECKBOX.addValidBlock(CUSTOM_BOX);
  PayloadTypeRegistry.serverboundPlay().register(Wire.Request.TYPE,Wire.Request.CODEC);PayloadTypeRegistry.clientboundPlay().register(Wire.Reply.TYPE,Wire.Reply.CODEC);PayloadTypeRegistry.serverboundPlay().register(HandWire.Request.TYPE,HandWire.Request.CODEC);PayloadTypeRegistry.clientboundPlay().register(HandWire.Reply.TYPE,HandWire.Reply.CODEC);PayloadTypeRegistry.clientboundPlay().register(DeckboxRefreshWire.Refresh.TYPE,DeckboxRefreshWire.Refresh.CODEC);
  ServerPlayNetworking.registerGlobalReceiver(Wire.Request.TYPE,(req,ctx)->ServerLogic.handle(ctx.player(),req));ServerPlayNetworking.registerGlobalReceiver(HandWire.Request.TYPE,(req,ctx)->HandLogic.handle(ctx.player(),req));
  ServerPlayConnectionEvents.DISCONNECT.register((h,s)->{ServerLogic.close(h.player);HandLogic.clearPendingLink(h.player);StaffTargets.clearAllForDisconnect(h.player);});
  CreativeModeTabEvents.modifyOutputEvent(CreativeModeTabs.FUNCTIONAL_BLOCKS).register(e->{e.accept(LANDS);e.accept(TOKENS);e.accept(CARDS);e.accept(BUILDER);e.accept(COUNTER);e.accept(TARGETING_STAFF);e.accept(CUSTOM_BOX);e.accept(HAND);});
  UseEntityCallback.EVENT.register((p,l,hand,e,hit)->{
   if(p.getItemInHand(hand).is(TARGETING_STAFF)){
    if(!l.isClientSide()&&p instanceof ServerPlayer sp)StaffTargets.mark(sp,e,StaffTargets.Color.ORANGE);
    return InteractionResult.SUCCESS;
   }
   if(e instanceof CardDisplayEntity c&&p.getItemInHand(hand).is(COUNTER)){if(p instanceof ServerPlayer sp)ServerLogic.openCounter(sp,c);return InteractionResult.SUCCESS;}
   return InteractionResult.PASS;
  });
  AttackEntityCallback.EVENT.register((p,l,hand,e,hit)->{
   if(!p.getItemInHand(hand).is(TARGETING_STAFF))return InteractionResult.PASS;
   if(!l.isClientSide()&&p instanceof ServerPlayer sp)StaffTargets.mark(sp,e,StaffTargets.Color.WHITE);
   return InteractionResult.SUCCESS;
  });
  UseItemCallback.EVENT.register((p,l,hand)->{
   if(!p.getItemInHand(hand).is(TARGETING_STAFF))return InteractionResult.PASS;
   if(!l.isClientSide()&&p instanceof ServerPlayer sp)StaffTargets.clear(sp);
   return InteractionResult.SUCCESS;
  });
  UseBlockCallback.EVENT.register((p,l,hand,hit)->{
   if(p instanceof ServerPlayer sp&&l.getBlockEntity(hit.getBlockPos()) instanceof DeckControlBlockEntity&&HandLogic.completePendingLink(sp,hit.getBlockPos()))return InteractionResult.SUCCESS;
   if(l.getBlockState(hit.getBlockPos()).is(CUSTOM_BOX)&&p.isShiftKeyDown()&&p.getItemInHand(hand).getItem() instanceof BlockItem)return CUSTOM_BOX.applyMaterial(p.getItemInHand(hand),l,hit.getBlockPos(),p);
   return InteractionResult.PASS;
  });
  DeckControlActionRegistry.register(DeckControlActionRegistry.simple(TcgGameRegistry.MTG,id("hand_discard_random"),Component.literal("Discard Random from Hand"),65,ctx->ctx.player().sendSystemMessage(Component.literal(HandLogic.discardRandom(ctx.deckControl())))));
 }
 static final class BankBlock extends Block {
  final int kind; BankBlock(BlockBehaviour.Properties p,int kind){super(p);this.kind=kind;}
  @Override protected InteractionResult useItemOn(ItemStack held,BlockState s,Level l,BlockPos pos,Player p,InteractionHand hand,BlockHitResult hit){return useWithoutItem(s,l,pos,p,hit);}
  @Override protected InteractionResult useWithoutItem(BlockState s,Level l,BlockPos pos,Player p,BlockHitResult hit){if(p instanceof ServerPlayer sp)ServerLogic.open(sp,pos,kind);return InteractionResult.SUCCESS;}
 }
}
