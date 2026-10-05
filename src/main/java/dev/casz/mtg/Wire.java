package dev.casz.mtg;
import net.minecraft.network.RegistryFriendlyByteBuf;
import net.minecraft.network.codec.StreamCodec;
import net.minecraft.network.protocol.common.custom.CustomPacketPayload;
import net.minecraft.core.BlockPos;
import net.minecraft.world.item.ItemStack;
import java.util.*;
public final class Wire {
 public record Request(BlockPos pos,String action,String text,int amount,int filter,String oracle,String stats) implements CustomPacketPayload {
  public Request(BlockPos pos,String action,String text,int amount){this(pos,action,text,amount,0,"","");}
  public Request(BlockPos pos,String action,String text,int amount,int filter){this(pos,action,text,amount,filter,"","");}
  public static final Type<Request> TYPE=new Type<>(Companion.id("request"));
  public static final StreamCodec<RegistryFriendlyByteBuf,Request> CODEC=StreamCodec.of((b,p)->{b.writeBlockPos(p.pos);b.writeUtf(p.action,32);b.writeUtf(p.text,24000);b.writeInt(p.amount);b.writeInt(p.filter);b.writeUtf(p.oracle,200);b.writeUtf(p.stats,40);},b->new Request(b.readBlockPos(),b.readUtf(32),b.readUtf(24000),b.readInt(),b.readInt(),b.readUtf(200),b.readUtf(40)));
  public Type<Request> type(){return TYPE;}
 }
 public record Row(String key,ItemStack card,long count,int requested) {public Row(String key,ItemStack card,long count){this(key,card,count,0);}}
 public record Reply(BlockPos pos,int kind,String message,String report,List<Row> rows) implements CustomPacketPayload {
  public static final Type<Reply> TYPE=new Type<>(Companion.id("reply"));
  public static final StreamCodec<RegistryFriendlyByteBuf,Reply> CODEC=StreamCodec.of((b,p)->{b.writeBlockPos(p.pos);b.writeInt(p.kind);b.writeUtf(p.message,2000);b.writeUtf(p.report,32767);b.writeVarInt(p.rows.size());for(Row r:p.rows){b.writeUtf(r.key,512);ItemStack.OPTIONAL_STREAM_CODEC.encode(b,r.card);b.writeLong(r.count);b.writeInt(r.requested);}},b->{var pos=b.readBlockPos();int kind=b.readInt();String msg=b.readUtf(2000),report=b.readUtf(32767);int n=b.readVarInt();if(n<0||n>500)throw new IllegalArgumentException("Too many rows");List<Row> rows=new ArrayList<>();for(int i=0;i<n;i++)rows.add(new Row(b.readUtf(512),ItemStack.OPTIONAL_STREAM_CODEC.decode(b),b.readLong(),b.readInt()));return new Reply(pos,kind,msg,report,rows);});
  public Type<Reply> type(){return TYPE;}
 }
}
