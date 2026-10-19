package dev.casz.caszualmtg;

import net.minecraft.core.BlockPos;
import net.minecraft.network.RegistryFriendlyByteBuf;
import net.minecraft.network.codec.StreamCodec;
import net.minecraft.network.protocol.common.custom.CustomPacketPayload;
import net.minecraft.world.item.ItemStack;
import java.util.*;

public final class HandWire {
 public record Request(BlockPos pos,String action,String text) implements CustomPacketPayload {
  public static final Type<Request> TYPE=new Type<>(CaszualMtg.id("hand_request"));
  public static final StreamCodec<RegistryFriendlyByteBuf,Request> CODEC=StreamCodec.of(
   (b,p)->{b.writeBlockPos(p.pos);b.writeUtf(p.action,32);b.writeUtf(p.text,512);},
   b->new Request(b.readBlockPos(),b.readUtf(32),b.readUtf(512))
  );
  public Type<Request> type(){return TYPE;}
 }
 public record Reply(BlockPos pos,String message,boolean visible,boolean authorized,boolean canManage,boolean revealAll,int count,String linked,List<String> viewers,List<ItemStack> cards,int strictMulligans,int pendingDiscards,boolean hasStaff,String staffLeft,String staffRight,String tableColor,String lifeLink,String tableLink,String primaryName,Map<String,Integer> hotkeys) implements CustomPacketPayload {
  public static final Type<Reply> TYPE=new Type<>(CaszualMtg.id("hand_reply"));
  public static final StreamCodec<RegistryFriendlyByteBuf,Reply> CODEC=StreamCodec.of(
   (b,p)->{
    b.writeBlockPos(p.pos);b.writeUtf(p.message,512);b.writeBoolean(p.visible);b.writeBoolean(p.authorized);b.writeBoolean(p.canManage);b.writeBoolean(p.revealAll);
    b.writeVarInt(p.count);b.writeUtf(p.linked,128);
    b.writeVarInt(p.viewers.size());for(String s:p.viewers)b.writeUtf(s,64);
    b.writeVarInt(p.cards.size());for(ItemStack s:p.cards)ItemStack.OPTIONAL_STREAM_CODEC.encode(b,s);
    b.writeVarInt(p.strictMulligans);b.writeVarInt(p.pendingDiscards);
    b.writeBoolean(p.hasStaff);b.writeUtf(p.staffLeft,7);b.writeUtf(p.staffRight,7);b.writeUtf(p.tableColor,7);b.writeUtf(p.lifeLink,128);b.writeUtf(p.tableLink,128);b.writeUtf(p.primaryName,64);
     b.writeVarInt(p.hotkeys.size());for(var key:p.hotkeys.entrySet()){b.writeUtf(key.getKey(),32);b.writeVarInt(key.getValue());}
   },
   b->{
    BlockPos pos=b.readBlockPos();String msg=b.readUtf(512);
    boolean visible=b.readBoolean(),authorized=b.readBoolean(),manage=b.readBoolean(),reveal=b.readBoolean();
    int count=b.readVarInt();String linked=b.readUtf(128);
    int vn=b.readVarInt();if(vn<0||vn>64)throw new IllegalArgumentException("Too many hand viewers");
    List<String> viewers=new ArrayList<>();for(int i=0;i<vn;i++)viewers.add(b.readUtf(64));
    int cn=b.readVarInt();if(cn<0||cn>HandBlockEntity.SIZE)throw new IllegalArgumentException("Too many hand cards");
    List<ItemStack> cards=new ArrayList<>();for(int i=0;i<cn;i++)cards.add(ItemStack.OPTIONAL_STREAM_CODEC.decode(b));
    int strict=b.readVarInt(),pending=b.readVarInt();
    if(strict<0||strict>100||pending<0||pending>HandBlockEntity.SIZE)throw new IllegalArgumentException("Invalid hand mulligan state");
    boolean staff=b.readBoolean();String left=b.readUtf(7),right=b.readUtf(7);
    if(!StaffColors.valid(left)||!StaffColors.valid(right))throw new IllegalArgumentException("Invalid staff color packet");
    String tableColor=b.readUtf(7),lifeLink=b.readUtf(128),tableLink=b.readUtf(128),primaryName=b.readUtf(64);
    if(!StaffColors.valid(tableColor))throw new IllegalArgumentException("Invalid table color");
     int bindings=b.readVarInt();if(bindings<0||bindings>HandHotkeys.ACTIONS.size())throw new IllegalArgumentException("Invalid hotkeys");
     Map<String,Integer> hotkeys=new LinkedHashMap<>();for(int i=0;i<bindings;i++){
      String action=b.readUtf(32);int key=b.readVarInt();
      if(!HandHotkeys.validAction(action)||!HandHotkeys.validKey(key))throw new IllegalArgumentException("Invalid keybind");
      hotkeys.put(action,key);
     }
    return new Reply(pos,msg,visible,authorized,manage,reveal,count,linked,List.copyOf(viewers),List.copyOf(cards),strict,pending,staff,left,right,tableColor,lifeLink,tableLink,primaryName,Map.copyOf(hotkeys));
   }
  );
  public Type<Reply> type(){return TYPE;}
 }
 private HandWire(){}
}
