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
 public static final int MAX_TOKEN_TEMPLATES=32;
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
 /** Per-seat size of all battlefield cards, persisted and shared with viewers.
  * Percent: 45..180 (100 = original card size). */
 private int cardScale=100;
 public int cardScale(){return cardScale;}
 public void cardScale(int percent){
  int next=Math.clamp(percent,45,180);
  if(next==cardScale)return;
  cardScale=next;setChanged();
 }
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
 /** One persisted AI attack declaration. Human response is required. */
 public record AiAttack(String attackerId,BlockPos defender) {}
 private String aiAttackerId="";
 private BlockPos aiDefender;
 public AiAttack aiAttack(){return aiAttackerId.isBlank()||aiDefender==null?null:new AiAttack(aiAttackerId,aiDefender);}
 public boolean declareAiAttack(String attackerId,BlockPos defender){
  if(aiAttack()!=null||attackerId==null||attackerId.isBlank()||defender==null)return false;
  aiAttackerId=attackerId;aiDefender=defender.immutable();setChanged();return true;
 }
 public void clearAiAttack(){aiAttackerId="";aiDefender=null;setChanged();}
 /** Casts from this bot seat's command zone. Survives reloads; never resets mid-game. */
 private int aiCommanderCasts;
 public int aiCommanderCasts(){return aiCommanderCasts;}
 public void aiCommanderCast(){aiCommanderCasts=Math.min(100,aiCommanderCasts+1);setChanged();}
 public void resetAiCommanderTax(){aiCommanderCasts=0;setChanged();}
 private String seatName="";
 /** Original commander identity is preserved even when the physical card moves zones. */
 private ItemStack commanderReference=ItemStack.EMPTY;
 public ItemStack commanderReference(){return commanderReference.copy();}
 public void rememberCommander(ItemStack card){if(card!=null&&!card.isEmpty()){commanderReference=card.copyWithCount(1);setChanged();}}

 private final List<PlayedCard> cards=new ArrayList<>();
 // Per-seat persistent virtual token templates. Storing a template does not
 // remove an inventory item and playing one never consumes its source.
 private final List<ItemStack> tokenTray=new ArrayList<>();
 public List<ItemStack> tokenTray(){return tokenTray.stream().map(ItemStack::copy).toList();}
 public boolean addToken(ItemStack original){
  if(original==null||original.isEmpty()||!Catalogue.isToken(com.spider.mtgcard.util.TcgCardMeta.read(original).typeLine()))return false;
  String key=Banks.key(1,original);
  for(ItemStack card:tokenTray)if(Banks.key(1,card).equals(key))return true;
  if(tokenTray.size()>=MAX_TOKEN_TEMPLATES)return false;
  tokenTray.add(com.spider.mtgcard.api.CardDatabaseCards.copyForExtraction(original));
  changed();return true;
 }
 public boolean removeToken(int index){
  if(index<0||index>=tokenTray.size())return false;
  tokenTray.remove(index);changed();return true;
 }
 public ItemStack tokenAt(int index){
  return index<0||index>=tokenTray.size()?ItemStack.EMPTY:tokenTray.get(index).copy();
 }
 public TabletopBlockEntity(BlockPos pos,BlockState state){super(CaszualMtg.TABLETOP_BE,pos,state);}
 public UUID seatOwner(){return seatOwner;}
 public String seatName(){return seatName;}
 public boolean ownedBy(Player p){return seatOwner!=null&&seatOwner.equals(p.getUUID());}
 public boolean claim(UUID id,String name){
  if(id==null||name==null||name.isBlank())return false;
  if(seatOwner==null){
   seatOwner=id;seatName=name.length()>64?name.substring(0,64):name;setChanged();return true;
  }
  return seatOwner.equals(id);
 }
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
  List<ItemStack> out=new ArrayList<>();for(var c:cards)if(!c.id().startsWith("copy:"))
   out.add(TabletopCounters.leavingBattlefield(c.stack()));
  cards.clear();changed();return out;
 }
 @Override protected void saveAdditional(ValueOutput out){
  super.saveAdditional(out);
  if(seatOwner!=null)out.putString("SeatOwner",seatOwner.toString());
  out.putString("SeatName",seatName);
  out.putInt("AiCommanderCasts",aiCommanderCasts);
  if(aiAttack()!=null){
   out.putString("AiAttacker",aiAttackerId);
   out.putString("AiDefender",HandBlockEntity.pos(aiDefender));
  }
  out.putString("TableWood",material);
  out.putInt("MatRgb",matRgb);
  out.putInt("CardScale",cardScale);
  if(!commanderReference.isEmpty())out.store("CommanderReference",ItemStack.CODEC,commanderReference);
  out.store("PlayedCards",PlayedCard.CODEC.listOf(),cards);
  out.store("TokenTray",ItemStack.CODEC.listOf(),tokenTray);
 }
 @Override protected void loadAdditional(ValueInput in){
  super.loadAdditional(in);seatOwner=null;
  try{String s=in.getStringOr("SeatOwner","");if(!s.isBlank())seatOwner=UUID.fromString(s);}catch(IllegalArgumentException ignored){}
  seatName=in.getStringOr("SeatName","");
  aiCommanderCasts=Math.clamp(in.getIntOr("AiCommanderCasts",0),0,100);
  aiAttackerId=in.getStringOr("AiAttacker","");
  aiDefender=HandBlockEntity.parsePos(in.getStringOr("AiDefender",""));
  if(aiAttackerId.length()>TabletopWire.MAX_CARD_ID_LENGTH){aiAttackerId="";aiDefender=null;}
  material=ChairWood.safe(in.getStringOr("TableWood","minecraft:dark_oak_planks"));
  matRgb=in.getIntOr("MatRgb",0x315348)&0xFFFFFF;
  cardScale=Math.clamp(in.getIntOr("CardScale",100),45,180);
  commanderReference=in.read("CommanderReference",ItemStack.CODEC).orElse(ItemStack.EMPTY);
  tokenTray.clear();
  for(ItemStack token:in.read("TokenTray",ItemStack.CODEC.listOf()).orElse(List.of()))
   if(tokenTray.size()<MAX_TOKEN_TEMPLATES&&!token.isEmpty()&&Catalogue.isToken(com.spider.mtgcard.util.TcgCardMeta.read(token).typeLine()))tokenTray.add(token.copyWithCount(1));
  cards.clear();
  for(PlayedCard c:in.read("PlayedCards",PlayedCard.CODEC.listOf()).orElse(List.of())){
   if(cards.size()<MAX_CARDS&&!c.stack().isEmpty()&&c.stack().is(com.spider.mtgcard.item.ModItemTags.TCG_CARD))
    cards.add(c.moved(c.x(),c.y()));
  }
 }
}
