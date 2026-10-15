package dev.casz.caszualmtg;

import com.mojang.serialization.Codec;
import com.mojang.serialization.codecs.RecordCodecBuilder;
import net.minecraft.core.BlockPos;
import net.minecraft.core.HolderLookup;
import net.minecraft.core.component.DataComponentMap;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.network.protocol.Packet;
import net.minecraft.network.protocol.game.ClientGamePacketListener;
import net.minecraft.network.protocol.game.ClientboundBlockEntityDataPacket;
import org.jetbrains.annotations.Nullable;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.level.block.entity.BlockEntity;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.storage.ValueInput;
import net.minecraft.world.level.storage.ValueOutput;
import java.util.*;

/** One persistent seat / tabletop tile. Cards stay in the tile under their location. */
public final class TabletopBlockEntity extends BlockEntity {
 public static final int MAX_CARDS=96;
 public record PlayedCard(String id,String owner,ItemStack stack,int x,int y,boolean tapped,boolean faceDown) {
  public static final Codec<PlayedCard> CODEC=RecordCodecBuilder.create(i->i.group(
   Codec.STRING.fieldOf("Id").forGetter(PlayedCard::id),
   Codec.STRING.fieldOf("Owner").forGetter(PlayedCard::owner),
   ItemStack.CODEC.fieldOf("Card").forGetter(PlayedCard::stack),
   Codec.INT.fieldOf("X").forGetter(PlayedCard::x),
   Codec.INT.fieldOf("Y").forGetter(PlayedCard::y),
   Codec.BOOL.optionalFieldOf("Tapped",false).forGetter(PlayedCard::tapped),
   Codec.BOOL.optionalFieldOf("FaceDown",false).forGetter(PlayedCard::faceDown)
  ).apply(i,PlayedCard::new));
  public PlayedCard moved(int nx,int ny){return new PlayedCard(id,owner,stack,Math.clamp(nx,0,1000),Math.clamp(ny,0,1000),tapped,faceDown);}
  public PlayedCard tapped(boolean value){return new PlayedCard(id,owner,stack,x,y,value,faceDown);}
  public PlayedCard hidden(boolean value){return new PlayedCard(id,owner,stack,x,y,tapped,value);}
 }
 // Keep dark oak as the fallback for tables placed before material selection existed.
 private String material="minecraft:dark_oak_planks";
 // Exact 24-bit color from the owning player's Card Hand. No wool palette.
 private int matRgb=0x315348;
 public record RenderData(String wood,int rgb) {}
 public int matRgb(){return matRgb;}
 public void matRgb(int rgb){
  int next=rgb&0xFFFFFF;
  if(matRgb==next)return;
  matRgb=next;
  setChanged();
  if(level!=null){
   BlockState state=getBlockState();
   level.sendBlockUpdated(worldPosition,state,state,3);
  }
 }
 public String material(){return material;}
 public void material(String wood){
  String next=ChairWood.safe(wood);
  if(next.equals(material))return;
  material=next;setChanged();
  if(level!=null){
   BlockState state=getBlockState();
   level.sendBlockUpdated(worldPosition,state,state,3);
  }
 }
 public Object getRenderData(){return new RenderData(material,matRgb);}
 @Override protected void collectImplicitComponents(DataComponentMap.Builder builder){
  super.collectImplicitComponents(builder);
  builder.set(CaszualMtg.TABLE_MATERIAL,material);
 }
 @Override public CompoundTag getUpdateTag(HolderLookup.Provider lookup){
  CompoundTag tag=super.getUpdateTag(lookup);
  tag.putString("TableWood",material);
  tag.putInt("MatRgb",matRgb);
  return tag;
 }
 @Override public @Nullable Packet<ClientGamePacketListener> getUpdatePacket(){
  return ClientboundBlockEntityDataPacket.create(this);
 }
 private UUID seatOwner;
 private String seatName="";
 /** Original commander identity is preserved even when the physical card moves zones. */
 private ItemStack commanderReference=ItemStack.EMPTY;
 public ItemStack commanderReference(){return commanderReference.copy();}
 public void rememberCommander(ItemStack card){if(card!=null&&!card.isEmpty()){commanderReference=card.copyWithCount(1);setChanged();}}

 private final List<PlayedCard> cards=new ArrayList<>();
 public TabletopBlockEntity(BlockPos pos,BlockState state){super(CaszualMtg.TABLETOP_BE,pos,state);}
 public UUID seatOwner(){return seatOwner;}
 public String seatName(){return seatName;}
 public boolean ownedBy(Player p){return seatOwner!=null&&seatOwner.equals(p.getUUID());}
 public boolean claim(Player p){
  if(seatOwner==null){seatOwner=p.getUUID();seatName=p.getGameProfile().name();setChanged();return true;}
  return ownedBy(p);
 }
 public List<PlayedCard> cards(){return List.copyOf(cards);}
 public boolean add(PlayedCard card){
  if(cards.size()>=MAX_CARDS||card.stack().isEmpty()||!card.stack().is(com.spider.mtgcard.item.ModItemTags.TCG_CARD))return false;
  cards.add(card);changed();return true;
 }
 public PlayedCard find(String id){for(var c:cards)if(c.id().equals(id))return c;return null;}
 public PlayedCard remove(String id){
  for(int i=0;i<cards.size();i++)if(cards.get(i).id().equals(id)){PlayedCard c=cards.remove(i);changed();return c;}
  return null;
 }
 public void replace(PlayedCard card){
  for(int i=0;i<cards.size();i++)if(cards.get(i).id().equals(card.id())){cards.set(i,card);changed();return;}
 }
 public void changed(){
  setChanged();
  if(level!=null&&!level.isClientSide()){
   BlockState state=getBlockState();
   int stage=Math.min(4,cards.size());
   if(state.hasProperty(TabletopBlock.CARDS)&&state.getValue(TabletopBlock.CARDS)!=stage)
    level.setBlock(worldPosition,state.setValue(TabletopBlock.CARDS,stage),3);
   else level.sendBlockUpdated(worldPosition,state,state,3);
  }
 }
 public List<ItemStack> drain(){
  List<ItemStack> out=new ArrayList<>();for(var c:cards)out.add(c.stack().copy());cards.clear();changed();return out;
 }
 @Override protected void saveAdditional(ValueOutput out){
  super.saveAdditional(out);
  if(seatOwner!=null)out.putString("SeatOwner",seatOwner.toString());
  out.putString("SeatName",seatName);
  out.putString("TableWood",material);
  out.putInt("MatRgb",matRgb);
  if(!commanderReference.isEmpty())out.store("CommanderReference",ItemStack.CODEC,commanderReference);
  out.store("PlayedCards",PlayedCard.CODEC.listOf(),cards);
 }
 @Override protected void loadAdditional(ValueInput in){
  super.loadAdditional(in);seatOwner=null;
  try{String s=in.getStringOr("SeatOwner","");if(!s.isBlank())seatOwner=UUID.fromString(s);}catch(IllegalArgumentException ignored){}
  seatName=in.getStringOr("SeatName","");
  material=ChairWood.safe(in.getStringOr("TableWood","minecraft:dark_oak_planks"));
  matRgb=in.getIntOr("MatRgb",0x315348)&0xFFFFFF;
  commanderReference=in.read("CommanderReference",ItemStack.CODEC).orElse(ItemStack.EMPTY);
  cards.clear();
  for(PlayedCard c:in.read("PlayedCards",PlayedCard.CODEC.listOf()).orElse(List.of())){
   if(cards.size()<MAX_CARDS&&!c.stack().isEmpty()&&c.stack().is(com.spider.mtgcard.item.ModItemTags.TCG_CARD))
    cards.add(c.moved(c.x(),c.y()));
  }
 }
}
