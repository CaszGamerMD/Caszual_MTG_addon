package dev.casz.mtg;

import net.minecraft.core.BlockPos;
import net.minecraft.network.RegistryFriendlyByteBuf;
import net.minecraft.network.codec.StreamCodec;
import net.minecraft.network.protocol.common.custom.CustomPacketPayload;
import net.minecraft.world.item.ItemStack;
import java.util.*;

public final class HandWire {
 public record Request(BlockPos pos,String action,String text) implements CustomPacketPayload {
  public static final Type<Request> TYPE=new Type<>(Companion.id("hand_request"));
  public static final StreamCodec<RegistryFriendlyByteBuf,Request> CODEC=StreamCodec.of(
   (b,p)->{b.writeBlockPos(p.pos);b.writeUtf(p.action,32);b.writeUtf(p.text,128);},
   b->new Request(b.readBlockPos(),b.readUtf(32),b.readUtf(128))
  );
  public Type<Request> type(){return TYPE;}
 }
 public record Reply(BlockPos pos,String message,boolean visible,boolean canManage,boolean revealAll,int count,String linked,List<String> viewers,List<ItemStack> cards) implements CustomPacketPayload {
  public static final Type<Reply> TYPE=new Type<>(Companion.id("hand_reply"));
  public static final StreamCodec<RegistryFriendlyByteBuf,Reply> CODEC=StreamCodec.of(
   (b,p)->{b.writeBlockPos(p.pos);b.writeUtf(p.message,512);b.writeBoolean(p.visible);b.writeBoolean(p.canManage);b.writeBoolean(p.revealAll);b.writeVarInt(p.count);b.writeUtf(p.linked,128);b.writeVarInt(p.viewers.size());for(String s:p.viewers)b.writeUtf(s,64);b.writeVarInt(p.cards.size());for(ItemStack s:p.cards)ItemStack.OPTIONAL_STREAM_CODEC.encode(b,s);},
   b->{BlockPos pos=b.readBlockPos();String msg=b.readUtf(512);boolean visible=b.readBoolean(),manage=b.readBoolean(),reveal=b.readBoolean();int count=b.readVarInt();String linked=b.readUtf(128);int vn=b.readVarInt();List<String> viewers=new ArrayList<>();for(int i=0;i<vn&&i<64;i++)viewers.add(b.readUtf(64));int cn=b.readVarInt();List<ItemStack> cards=new ArrayList<>();for(int i=0;i<cn&&i<HandBlockEntity.SIZE;i++)cards.add(ItemStack.OPTIONAL_STREAM_CODEC.decode(b));return new Reply(pos,msg,visible,manage,reveal,count,linked,List.copyOf(viewers),List.copyOf(cards));}
  );
  public Type<Reply> type(){return TYPE;}
 }
 private HandWire(){}
}
