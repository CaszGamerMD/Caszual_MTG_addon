package dev.casz.caszualmtg;

import net.minecraft.core.BlockPos;
import net.minecraft.network.RegistryFriendlyByteBuf;
import net.minecraft.network.codec.StreamCodec;
import net.minecraft.network.protocol.common.custom.CustomPacketPayload;
import net.minecraft.world.item.ItemStack;
import java.util.*;

public final class TabletopWire {
 public record Request(BlockPos pos,String action,String ref,BlockPos target,int x,int y,int amount) implements CustomPacketPayload {
  public static final Type<Request> TYPE=new Type<>(CaszualMtg.id("tabletop_request"));
  public static final StreamCodec<RegistryFriendlyByteBuf,Request> CODEC=StreamCodec.of(
   (b,p)->{b.writeBlockPos(p.pos);b.writeUtf(p.action,24);b.writeUtf(p.ref,256);b.writeBlockPos(p.target);b.writeInt(p.x);b.writeInt(p.y);b.writeVarInt(p.amount);},
   b->new Request(b.readBlockPos(),b.readUtf(24),b.readUtf(256),b.readBlockPos(),b.readInt(),b.readInt(),b.readVarInt()));
  public Type<Request> type(){return TYPE;}
 }
 public record Tile(BlockPos pos,String owner,int color,int life,boolean hasLife,boolean active) {}
 public record Card(BlockPos pos,String id,String owner,ItemStack stack,int x,int y,boolean tapped,boolean hidden) {}
 public record ZoneCard(int slot,ItemStack stack) {}
 public record Reply(BlockPos pos,String message,BlockPos seat,List<Tile> tiles,List<Card> cards,List<ItemStack> hand,int libraryCount,List<ZoneCard> grave,List<ZoneCard> exile,List<ItemStack> scry,ItemStack commander) implements CustomPacketPayload {
  public static final Type<Reply> TYPE=new Type<>(CaszualMtg.id("tabletop_reply"));
  public static final StreamCodec<RegistryFriendlyByteBuf,Reply> CODEC=StreamCodec.of((b,p)->{
   b.writeBlockPos(p.pos);b.writeUtf(p.message,512);b.writeBlockPos(p.seat);
   b.writeVarInt(p.tiles.size());for(Tile t:p.tiles){b.writeBlockPos(t.pos);b.writeUtf(t.owner,64);b.writeInt(t.color);b.writeInt(t.life);b.writeBoolean(t.hasLife);b.writeBoolean(t.active);}
   b.writeVarInt(p.cards.size());for(Card c:p.cards){
    b.writeBlockPos(c.pos);b.writeUtf(c.id,40);b.writeUtf(c.owner,40);
    ItemStack.OPTIONAL_STREAM_CODEC.encode(b,c.stack);
    b.writeVarInt(c.x);b.writeVarInt(c.y);b.writeBoolean(c.tapped);b.writeBoolean(c.hidden);
   }
   b.writeVarInt(p.hand.size());for(ItemStack s:p.hand)ItemStack.OPTIONAL_STREAM_CODEC.encode(b,s);
   b.writeVarInt(p.libraryCount);
   for(List<ZoneCard> zone:List.of(p.grave,p.exile)){
    b.writeVarInt(zone.size());for(ZoneCard c:zone){b.writeVarInt(c.slot);ItemStack.OPTIONAL_STREAM_CODEC.encode(b,c.stack);}
   }
   b.writeVarInt(p.scry.size());for(ItemStack s:p.scry)ItemStack.OPTIONAL_STREAM_CODEC.encode(b,s);
   ItemStack.OPTIONAL_STREAM_CODEC.encode(b,p.commander);
  },b->{
   BlockPos pos=b.readBlockPos();String message=b.readUtf(512);BlockPos seat=b.readBlockPos();
   int n=b.readVarInt();if(n<0||n>32)throw new IllegalArgumentException("Table too large");
   List<Tile> tiles=new ArrayList<>();for(int i=0;i<n;i++)tiles.add(new Tile(b.readBlockPos(),b.readUtf(64),b.readInt(),b.readInt(),b.readBoolean(),b.readBoolean()));
   n=b.readVarInt();if(n<0||n>3072)throw new IllegalArgumentException("Too many played cards");
   List<Card> cards=new ArrayList<>();for(int i=0;i<n;i++)cards.add(new Card(b.readBlockPos(),b.readUtf(40),b.readUtf(40),ItemStack.OPTIONAL_STREAM_CODEC.decode(b),b.readVarInt(),b.readVarInt(),b.readBoolean(),b.readBoolean()));
   n=b.readVarInt();if(n<0||n>100)throw new IllegalArgumentException("Too many hand cards");
   List<ItemStack> hand=new ArrayList<>();for(int i=0;i<n;i++)hand.add(ItemStack.OPTIONAL_STREAM_CODEC.decode(b));
   int library=b.readVarInt();
   List<List<ZoneCard>> zones=new ArrayList<>();
   for(int j=0;j<2;j++){
    n=b.readVarInt();if(n<0||n>100)throw new IllegalArgumentException("Too many zone cards");
    List<ZoneCard> zone=new ArrayList<>();for(int i=0;i<n;i++)zone.add(new ZoneCard(b.readVarInt(),ItemStack.OPTIONAL_STREAM_CODEC.decode(b)));zones.add(zone);
   }
   n=b.readVarInt();if(n<0||n>7)throw new IllegalArgumentException("Too many scry cards");
   List<ItemStack> scry=new ArrayList<>();for(int i=0;i<n;i++)scry.add(ItemStack.OPTIONAL_STREAM_CODEC.decode(b));
   ItemStack commander=ItemStack.OPTIONAL_STREAM_CODEC.decode(b);
   return new Reply(pos,message,seat,List.copyOf(tiles),List.copyOf(cards),List.copyOf(hand),library,List.copyOf(zones.get(0)),List.copyOf(zones.get(1)),List.copyOf(scry),commander);
  });
  public Type<Reply> type(){return TYPE;}
 }
 private TabletopWire(){}
}
