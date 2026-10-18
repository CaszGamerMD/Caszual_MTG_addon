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
import net.minecraft.world.item.context.BlockPlaceContext;
import net.minecraft.world.level.block.state.properties.BlockStateProperties;
import net.minecraft.world.level.block.state.properties.EnumProperty;
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
 public static final Block LANDS=block("land_database",0),TOKENS=block("token_database",1),CARDS=block("community_database",2);
 public static final BuilderBlock BUILDER=builderBlock();
 public static final BlockEntityType<BuilderBlockEntity> BUILDER_BE=Registry.register(BuiltInRegistries.BLOCK_ENTITY_TYPE,id("deck_builder"),FabricBlockEntityTypeBuilder.create(BuilderBlockEntity::new,BUILDER).build());
 static BuilderBlock builderBlock(){var key=ResourceKey.create(Registries.BLOCK,id("deck_builder"));var block=Registry.register(BuiltInRegistries.BLOCK,key,new BuilderBlock(BlockBehaviour.Properties.of().setId(key).strength(2.5f)));var itemKey=ResourceKey.create(Registries.ITEM,id("deck_builder"));Registry.register(BuiltInRegistries.ITEM,itemKey,new BlockItem(block,new Item.Properties().setId(itemKey).useBlockDescriptionPrefix()));return block;}
 public static final net.minecraft.core.component.DataComponentType<String> BOX_MATERIAL=Registry.register(BuiltInRegistries.DATA_COMPONENT_TYPE,id("box_material"),net.minecraft.core.component.DataComponentType.<String>builder().persistent(com.mojang.serialization.Codec.STRING).networkSynchronized(net.minecraft.network.codec.StreamCodec.of((b,v)->b.writeUtf(v,256),b->b.readUtf(256))).build());
 public static final CustomDeckbox CUSTOM_BOX=customBox();
 public static final CustomDeckControl CUSTOM_DECK_CONTROL=customDeckControl();
 public static final CustomGraveyard CUSTOM_GRAVEYARD=customGraveyard();
 public static final net.minecraft.core.component.DataComponentType<String> TABLE_MATERIAL=Registry.register(
  BuiltInRegistries.DATA_COMPONENT_TYPE,id("table_material"),
  net.minecraft.core.component.DataComponentType.<String>builder()
   .persistent(com.mojang.serialization.Codec.STRING)
   .networkSynchronized(net.minecraft.network.codec.StreamCodec.of((b,v)->b.writeUtf(v,256),b->b.readUtf(256)))
   .build());
 public static final TabletopBlock TABLETOP=tabletopBlock();
 public static final BlockEntityType<TabletopBlockEntity> TABLETOP_BE=Registry.register(
  BuiltInRegistries.BLOCK_ENTITY_TYPE,id("tabletop"),
  FabricBlockEntityTypeBuilder.create(TabletopBlockEntity::new,TABLETOP).build());
 static TabletopBlock tabletopBlock(){
  var key=ResourceKey.create(Registries.BLOCK,id("tabletop"));
  var block=Registry.register(BuiltInRegistries.BLOCK,key,
   new TabletopBlock(BlockBehaviour.Properties.of().setId(key).strength(2.5f).noOcclusion().sound(net.minecraft.world.level.block.SoundType.WOOD)));
  var ik=ResourceKey.create(Registries.ITEM,id("tabletop"));
  Registry.register(BuiltInRegistries.ITEM,ik,new TabletopBlockItem(block,new Item.Properties().setId(ik).useBlockDescriptionPrefix().stacksTo(1)));
  return block;
 }
 public static final net.minecraft.core.component.DataComponentType<String> CHAIR_MATERIAL=Registry.register(
  BuiltInRegistries.DATA_COMPONENT_TYPE,id("chair_material"),
  net.minecraft.core.component.DataComponentType.<String>builder()
   .persistent(com.mojang.serialization.Codec.STRING)
   .networkSynchronized(net.minecraft.network.codec.StreamCodec.of((b,v)->b.writeUtf(v,256),b->b.readUtf(256)))
   .build());
 public static final ChairBlock MATERIAL_CHAIR=materialChair();
 static ChairBlock materialChair(){
  var key=ResourceKey.create(Registries.BLOCK,id("material_chair"));
  ChairBlock block=Registry.register(BuiltInRegistries.BLOCK,key,
    new ChairBlock(BlockBehaviour.Properties.of().setId(key).strength(2.0f).noOcclusion().sound(net.minecraft.world.level.block.SoundType.WOOD)));
  var itemKey=ResourceKey.create(Registries.ITEM,id("material_chair"));
  Registry.register(BuiltInRegistries.ITEM,itemKey,new ChairBlockItem(block,new Item.Properties().setId(itemKey).useBlockDescriptionPrefix()));
  return block;
 }
 public static final BlockEntityType<ChairBlockEntity> CHAIR_BE=chairEntityType();
 static BlockEntityType<ChairBlockEntity> chairEntityType(){
  return Registry.register(BuiltInRegistries.BLOCK_ENTITY_TYPE,id("chair"),
   FabricBlockEntityTypeBuilder.create(ChairBlockEntity::new,MATERIAL_CHAIR).build());
 }
 public static final net.minecraft.world.item.crafting.RecipeSerializer<ChairRecipe> CHAIR_RECIPE=
  Registry.register(BuiltInRegistries.RECIPE_SERIALIZER,id("chair_material"),ChairRecipe.SERIALIZER);
 public static final net.minecraft.world.item.crafting.RecipeSerializer<TabletopRecipe> TABLE_RECIPE=
  Registry.register(BuiltInRegistries.RECIPE_SERIALIZER,id("tabletop_material"),TabletopRecipe.SERIALIZER);
 public static final HandBlock HAND=handBlock();
 public static final BlockEntityType<HandBlockEntity> HAND_BE=Registry.register(BuiltInRegistries.BLOCK_ENTITY_TYPE,id("hand_block"),FabricBlockEntityTypeBuilder.create(HandBlockEntity::new,HAND).build());
 static HandBlock handBlock(){var key=ResourceKey.create(Registries.BLOCK,id("hand_block"));var block=Registry.register(BuiltInRegistries.BLOCK,key,new HandBlock(BlockBehaviour.Properties.of().setId(key).strength(2.0f).sound(net.minecraft.world.level.block.SoundType.WOOD)));var itemKey=ResourceKey.create(Registries.ITEM,id("hand_block"));Registry.register(BuiltInRegistries.ITEM,itemKey,new BlockItem(block,new Item.Properties().setId(itemKey).useBlockDescriptionPrefix()));return block;}
  static CustomDeckbox customBox(){var key=ResourceKey.create(Registries.BLOCK,id("custom_deckbox"));var block=Registry.register(BuiltInRegistries.BLOCK,key,new CustomDeckbox(BlockBehaviour.Properties.of().setId(key).strength(2.5f).noOcclusion().sound(net.minecraft.world.level.block.SoundType.WOOD)));var itemKey=ResourceKey.create(Registries.ITEM,id("custom_deckbox"));Registry.register(BuiltInRegistries.ITEM,itemKey,new CustomDeckbox.Item(block,new Item.Properties().setId(itemKey).stacksTo(1).useBlockDescriptionPrefix()));return block;}
 static CustomDeckControl customDeckControl(){
  var key=ResourceKey.create(Registries.BLOCK,id("custom_deck_control"));
  CustomDeckControl block=Registry.register(BuiltInRegistries.BLOCK,key,
   new CustomDeckControl(BlockBehaviour.Properties.of().setId(key)
    .strength(2.0f).noOcclusion().isRedstoneConductor((s,w,p)->false)
    .isSuffocating((s,w,p)->false).lightLevel(s->s.getValue(com.spider.mtgcard.deckcontrol.DeckControlBlock.LIT)?14:0)));
  var item=ResourceKey.create(Registries.ITEM,id("custom_deck_control"));
  Registry.register(BuiltInRegistries.ITEM,item,new BlockItem(block,
   new Item.Properties().setId(item).useBlockDescriptionPrefix()));
  return block;
 }
 static CustomGraveyard customGraveyard(){
  var key=ResourceKey.create(Registries.BLOCK,id("custom_graveyard"));
  CustomGraveyard block=Registry.register(BuiltInRegistries.BLOCK,key,
   new CustomGraveyard(BlockBehaviour.Properties.of().setId(key)
    .strength(2.5f).noOcclusion().sound(net.minecraft.world.level.block.SoundType.WOOD)));
  var item=ResourceKey.create(Registries.ITEM,id("custom_graveyard"));
  Registry.register(BuiltInRegistries.ITEM,item,new BlockItem(block,
   new Item.Properties().setId(item).useBlockDescriptionPrefix()));
  return block;
 }
 public static final DeckboxRackBlock RACK=rackBlock();
 public static final BlockEntityType<DeckboxRackEntity> RACK_BE=Registry.register(BuiltInRegistries.BLOCK_ENTITY_TYPE,id("deckbox_rack"),FabricBlockEntityTypeBuilder.create(DeckboxRackEntity::new,RACK).build());
 static DeckboxRackBlock rackBlock(){var key=ResourceKey.create(Registries.BLOCK,id("deckbox_rack"));var block=Registry.register(BuiltInRegistries.BLOCK,key,new DeckboxRackBlock(BlockBehaviour.Properties.of().setId(key).strength(2.0f).noOcclusion().sound(net.minecraft.world.level.block.SoundType.WOOD)));var ik=ResourceKey.create(Registries.ITEM,id("deckbox_rack"));Registry.register(BuiltInRegistries.ITEM,ik,new BlockItem(block,new Item.Properties().setId(ik).useBlockDescriptionPrefix().stacksTo(1)));return block;}
 public static final StaffRackBlock STAFF_RACK=staffRackBlock();
 public static final BlockEntityType<StaffRackEntity> STAFF_RACK_BE=Registry.register(
   BuiltInRegistries.BLOCK_ENTITY_TYPE,id("staff_rack"),
   FabricBlockEntityTypeBuilder.create(StaffRackEntity::new,STAFF_RACK).build());
 static StaffRackBlock staffRackBlock(){
  var key=ResourceKey.create(Registries.BLOCK,id("staff_rack"));
  var block=Registry.register(BuiltInRegistries.BLOCK,key,
    new StaffRackBlock(BlockBehaviour.Properties.of().setId(key).strength(2.0f).noOcclusion()
      .sound(net.minecraft.world.level.block.SoundType.WOOD)));
  var itemKey=ResourceKey.create(Registries.ITEM,id("staff_rack"));
  Registry.register(BuiltInRegistries.ITEM,itemKey,new BlockItem(block,
    new Item.Properties().setId(itemKey).useBlockDescriptionPrefix().stacksTo(1)));
  return block;
 }
 public static final Item COUNTER=Registry.register(BuiltInRegistries.ITEM,id("counter"),new Item(new Item.Properties().setId(ResourceKey.create(Registries.ITEM,id("counter"))).stacksTo(1)));
 public static final Item TARGETING_STAFF=Registry.register(BuiltInRegistries.ITEM,id("targeting_staff"),new Item(new Item.Properties().setId(ResourceKey.create(Registries.ITEM,id("targeting_staff"))).stacksTo(1)));
 public static final Item COMMANDER_GOLEM=Registry.register(BuiltInRegistries.ITEM,id("commander_golem"),new CommanderGolemItem(new Item.Properties().setId(ResourceKey.create(Registries.ITEM,id("commander_golem"))).stacksTo(1)));
 static Block block(String name,int kind){var key=ResourceKey.create(Registries.BLOCK,id(name));Block b=Registry.register(BuiltInRegistries.BLOCK,key,new BankBlock(BlockBehaviour.Properties.of().setId(key).strength(2.5f),kind));var ik=ResourceKey.create(Registries.ITEM,id(name));Registry.register(BuiltInRegistries.ITEM,ik,new BlockItem(b,new Item.Properties().setId(ik).useBlockDescriptionPrefix()));return b;}
 public static int kind(Block b){return b==LANDS?0:b==TOKENS?1:b==CARDS?2:b==BUILDER?3:-1;}
 public static final ExtendedMenuType<CommunityMenu,CommunityMenu.OpenData> COMMUNITY_MENU=Registry.register(BuiltInRegistries.MENU,id("community"),new ExtendedMenuType<>(CommunityMenu::new,CommunityMenu.OpenData.CODEC));
 public static final ExtendedMenuType<BuilderMenu,BuilderMenu.OpenData> BUILDER_MENU=Registry.register(BuiltInRegistries.MENU,id("builder"),new ExtendedMenuType<>(BuilderMenu::new,BuilderMenu.OpenData.CODEC));
 public static final ExtendedMenuType<DeckboxRackMenu,DeckboxRackMenu.OpenData> RACK_MENU=Registry.register(BuiltInRegistries.MENU,id("deckbox_rack"),new ExtendedMenuType<>(DeckboxRackMenu::new,DeckboxRackMenu.OpenData.CODEC));
 public static final ExtendedMenuType<StaffRackMenu,StaffRackMenu.OpenData> STAFF_RACK_MENU=
   Registry.register(BuiltInRegistries.MENU,id("staff_rack"),
     new ExtendedMenuType<>(StaffRackMenu::new,StaffRackMenu.OpenData.CODEC));
 public void onInitialize(){
  net.fabricmc.fabric.api.event.lifecycle.v1.ServerTickEvents.END_LEVEL_TICK.register(ChairSeats::tick);
   net.fabricmc.fabric.api.event.lifecycle.v1.ServerTickEvents.END_LEVEL_TICK.register(CommanderGolems::tick);
  // Do not inspect MTGCard's block-entity fields in our main entrypoint:
  // MTGCard's initializer can run later in the same Fabric initialization pass.
  net.fabricmc.fabric.api.event.lifecycle.v1.ServerLifecycleEvents.SERVER_STARTING
      .register(server -> MtgBlockEntitySafety.verifyAtLifecycle("server startup"));
  PayloadTypeRegistry.clientboundPlay().register(CardStoreStatusWire.Progress.TYPE,CardStoreStatusWire.Progress.CODEC);
  PayloadTypeRegistry.serverboundPlay().register(TabletopWire.Request.TYPE,TabletopWire.Request.CODEC);
  PayloadTypeRegistry.clientboundPlay().register(TabletopWire.Reply.TYPE,TabletopWire.Reply.CODEC);
  ServerPlayNetworking.registerGlobalReceiver(TabletopWire.Request.TYPE,(req,ctx)->TabletopLogic.handle(ctx.player(),req));
  PayloadTypeRegistry.serverboundPlay().register(Wire.Request.TYPE,Wire.Request.CODEC);PayloadTypeRegistry.clientboundPlay().register(Wire.Reply.TYPE,Wire.Reply.CODEC);PayloadTypeRegistry.serverboundPlay().register(HandWire.Request.TYPE,HandWire.Request.CODEC);PayloadTypeRegistry.clientboundPlay().register(HandWire.Reply.TYPE,HandWire.Reply.CODEC);PayloadTypeRegistry.clientboundPlay().register(DeckboxRefreshWire.Refresh.TYPE,DeckboxRefreshWire.Refresh.CODEC);
  ServerPlayNetworking.registerGlobalReceiver(Wire.Request.TYPE,(req,ctx)->ServerLogic.handle(ctx.player(),req));ServerPlayNetworking.registerGlobalReceiver(HandWire.Request.TYPE,(req,ctx)->HandLogic.handle(ctx.player(),req));
  ServerPlayConnectionEvents.DISCONNECT.register((h,s)->{ServerLogic.close(h.player);HandLogic.clearPendingLink(h.player);TabletopLogic.close(h.player);StaffTargets.clearAllForDisconnect(h.player);});
  CreativeModeTabEvents.modifyOutputEvent(CreativeModeTabs.FUNCTIONAL_BLOCKS).register(e->{e.accept(LANDS);e.accept(TOKENS);e.accept(CARDS);e.accept(BUILDER);e.accept(COUNTER);e.accept(TARGETING_STAFF);e.accept(CUSTOM_BOX);e.accept(CUSTOM_DECK_CONTROL);e.accept(CUSTOM_GRAVEYARD);e.accept(HAND);e.accept(RACK);e.accept(STAFF_RACK);e.accept(TABLETOP);e.accept(MATERIAL_CHAIR);e.accept(COMMANDER_GOLEM);});
  UseEntityCallback.EVENT.register((p,l,hand,e,hit)->{
   if(e instanceof net.minecraft.world.entity.animal.golem.IronGolem iron
       &&iron.entityTags().contains(CommanderGolems.TAG)){
    if(p instanceof ServerPlayer sp &&l instanceof net.minecraft.server.level.ServerLevel level)
     sp.sendSystemMessage(Component.literal(CommanderGolems.status(level,iron)));
    return InteractionResult.SUCCESS;
   }
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
  // Drop the inserted Card Store deckbox on normal block destruction, including its
  // MTGCard UUID storage pointer, before vanilla destroys the Card Store block entity.
  net.fabricmc.fabric.api.event.player.PlayerBlockBreakEvents.AFTER.register((world,player,pos,state,be)->{
   if(be instanceof com.spider.mtgcard.cardstore.CardStoreBlockEntity store
       &&store instanceof CardStoreBoxAccess access){
    ItemStack box=access.caszual$getDeckbox();
    if(!box.isEmpty()){
     Block.popResource(world,pos,box.copy());
     access.caszual$setDeckbox(ItemStack.EMPTY);
    }
   }
  });
  UseBlockCallback.EVENT.register((p,l,hand,hit)->{
   if(p instanceof ServerPlayer sp&&l.getBlockEntity(hit.getBlockPos()) instanceof com.spider.mtgcard.life.LifePointBlockEntity&&HandLogic.completePendingLifeLink(sp,hit.getBlockPos()))return InteractionResult.SUCCESS;
   if(p instanceof ServerPlayer sp&&l.getBlockEntity(hit.getBlockPos()) instanceof DeckControlBlockEntity&&HandLogic.completePendingLink(sp,hit.getBlockPos()))return InteractionResult.SUCCESS;
   if(l.getBlockState(hit.getBlockPos()).is(CUSTOM_BOX)&&p.isShiftKeyDown()&&p.getItemInHand(hand).getItem() instanceof BlockItem)return CUSTOM_BOX.applyMaterial(p.getItemInHand(hand),l,hit.getBlockPos(),p);
   return InteractionResult.PASS;
  });
  DeckControlActionRegistry.register(DeckControlActionRegistry.simple(TcgGameRegistry.MTG,id("hand_discard_random"),Component.literal("Discard Random from Hand"),65,ctx->ctx.player().sendSystemMessage(Component.literal(HandLogic.discardRandom(ctx.deckControl())))));
 }
 static final class BankBlock extends Block {
  static final EnumProperty<Direction> FACING=BlockStateProperties.HORIZONTAL_FACING;
  final int kind;
  BankBlock(BlockBehaviour.Properties properties,int kind){
   super(properties);
   this.kind=kind;
   // Existing database blocks from older worlds continue facing north.
   registerDefaultState(stateDefinition.any().setValue(FACING,Direction.NORTH));
  }
  @Override protected void createBlockStateDefinition(StateDefinition.Builder<Block,BlockState> builder){
   builder.add(FACING);
  }
  @Override public BlockState getStateForPlacement(BlockPlaceContext context){
   // The textured control panel is the model's north face.
   return defaultBlockState().setValue(FACING,context.getHorizontalDirection().getOpposite());
  }
  @Override protected InteractionResult useItemOn(ItemStack held,BlockState s,Level l,BlockPos pos,Player p,InteractionHand hand,BlockHitResult hit){return useWithoutItem(s,l,pos,p,hit);}
  @Override protected InteractionResult useWithoutItem(BlockState s,Level l,BlockPos pos,Player p,BlockHitResult hit){if(p instanceof ServerPlayer sp)ServerLogic.open(sp,pos,kind);return InteractionResult.SUCCESS;}
 }
}
