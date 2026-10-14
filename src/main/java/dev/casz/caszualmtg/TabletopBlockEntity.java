package dev.casz.caszualmtg;

import com.mojang.serialization.Codec;
import com.mojang.serialization.codecs.RecordCodecBuilder;
import net.minecraft.core.BlockPos;
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
 private UUID seatOwner;
 private String seatName="";
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
  cards.add(card);setChanged();return true;
 }
 public PlayedCard find(String id){for(var c:cards)if(c.id().equals(id))return c;return null;}
 public PlayedCard remove(String id){
  for(int i=0;i<cards.size();i++)if(cards.get(i).id().equals(id)){PlayedCard c=cards.remove(i);setChanged();return c;}
  return null;
 }
 public void replace(PlayedCard card){
  for(int i=0;i<cards.size();i++)if(cards.get(i).id().equals(card.id())){cards.set(i,card);setChanged();return;}
 }
 public List<ItemStack> drain(){
  List<ItemStack> out=new ArrayList<>();for(var c:cards)out.add(c.stack().copy());cards.clear();setChanged();return out;
 }
 @Override protected void saveAdditional(ValueOutput out){
  super.saveAdditional(out);
  if(seatOwner!=null)out.putString("SeatOwner",seatOwner.toString());
  out.putString("SeatName",seatName);
  out.store("PlayedCards",PlayedCard.CODEC.listOf(),cards);
 }
 @Override protected void loadAdditional(ValueInput in){
  super.loadAdditional(in);seatOwner=null;
  try{String s=in.getStringOr("SeatOwner","");if(!s.isBlank())seatOwner=UUID.fromString(s);}catch(IllegalArgumentException ignored){}
  seatName=in.getStringOr("SeatName","");
  cards.clear();
  for(PlayedCard c:in.read("PlayedCards",PlayedCard.CODEC.listOf()).orElse(List.of())){
   if(cards.size()<MAX_CARDS&&!c.stack().isEmpty()&&c.stack().is(com.spider.mtgcard.item.ModItemTags.TCG_CARD))
    cards.add(c.moved(c.x(),c.y()));
  }
 }
}
