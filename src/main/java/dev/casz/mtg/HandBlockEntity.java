package dev.casz.mtg;

import com.mojang.serialization.Codec;
import com.mojang.serialization.codecs.RecordCodecBuilder;
import com.spider.mtgcard.item.ModItemTags;
import net.minecraft.core.BlockPos;
import net.minecraft.world.Container;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.level.block.entity.BlockEntity;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.storage.ValueInput;
import net.minecraft.world.level.storage.ValueOutput;
import java.util.*;

public final class HandBlockEntity extends BlockEntity implements Container {
 public static final int SIZE=30;
 private final List<ItemStack> cards=new ArrayList<>(Collections.nCopies(SIZE,ItemStack.EMPTY));
 private UUID owner;
 private final LinkedHashSet<UUID> viewers=new LinkedHashSet<>();
 private final LinkedHashMap<UUID,String> viewerNames=new LinkedHashMap<>();
 private BlockPos linkedControl;
 private boolean revealAll;

 public HandBlockEntity(BlockPos pos,BlockState state){super(Companion.HAND_BE,pos,state);}

 public UUID owner(){return owner;}
 public void ensureOwner(Player player){if(owner==null){owner=player.getUUID();viewers.add(owner);viewerNames.put(owner,player.getGameProfile().name());changed();}}
 public boolean canView(Player player){return revealAll||owner!=null&&(owner.equals(player.getUUID())||viewers.contains(player.getUUID()));}
 public boolean canManage(Player player){return owner!=null&&owner.equals(player.getUUID());}
 public boolean revealAll(){return revealAll;}
 public void revealAll(boolean value){revealAll=value;changed();}
 public BlockPos linkedControl(){return linkedControl==null?null:linkedControl.immutable();}
 public void linkedControl(BlockPos pos){linkedControl=pos==null?null:pos.immutable();changed();}
 public List<String> viewerNames(){return List.copyOf(viewerNames.values());}
 public void addViewer(UUID id,String name){viewers.add(id);viewerNames.put(id,name);changed();}
 public boolean removeViewer(String name){UUID found=null;for(var e:viewerNames.entrySet())if(e.getValue().equalsIgnoreCase(name)&&!e.getKey().equals(owner)){found=e.getKey();break;}if(found==null)return false;viewers.remove(found);viewerNames.remove(found);changed();return true;}
 public int cardCount(){int n=0;for(ItemStack s:cards)if(!s.isEmpty())n++;return n;}
 public List<ItemStack> visibleCards(){List<ItemStack> out=new ArrayList<>();for(ItemStack s:cards)if(!s.isEmpty())out.add(s.copy());return out;}
 public boolean addCard(ItemStack stack){if(stack==null||stack.isEmpty()||!stack.is(ModItemTags.TCG_CARD))return false;for(int i=0;i<SIZE;i++)if(cards.get(i).isEmpty()){ItemStack one=stack.copy();one.setCount(1);cards.set(i,one);changed();return true;}return false;}
 public ItemStack removeRandom(Random random){List<Integer> used=new ArrayList<>();for(int i=0;i<SIZE;i++)if(!cards.get(i).isEmpty())used.add(i);if(used.isEmpty())return ItemStack.EMPTY;int slot=used.get(random.nextInt(used.size()));ItemStack out=cards.get(slot);cards.set(slot,ItemStack.EMPTY);changed();return out;}
 public void restore(ItemStack stack){addCard(stack);}
 public void changed(){setChanged();if(level!=null&&!level.isClientSide())level.sendBlockUpdated(worldPosition,getBlockState(),getBlockState(),3);}

 @Override protected void loadAdditional(ValueInput in){super.loadAdditional(in);for(int i=0;i<SIZE;i++)cards.set(i,ItemStack.EMPTY);for(SlotStack s:in.read("Cards",SlotStack.CODEC.listOf()).orElse(List.of()))if(s.slot>=0&&s.slot<SIZE)cards.set(s.slot,s.stack);String ownerRaw=in.getStringOr("Owner","");try{owner=ownerRaw.isBlank()?null:UUID.fromString(ownerRaw);}catch(Exception e){owner=null;}viewers.clear();viewerNames.clear();for(Viewer v:in.read("Viewers",Viewer.CODEC.listOf()).orElse(List.of())){try{UUID id=UUID.fromString(v.uuid);viewers.add(id);viewerNames.put(id,v.name);}catch(Exception ignored){}}String link=in.getStringOr("LinkedControl","");linkedControl=parsePos(link);revealAll=in.getBooleanOr("RevealAll",false);}
 @Override protected void saveAdditional(ValueOutput out){super.saveAdditional(out);List<SlotStack> saved=new ArrayList<>();for(int i=0;i<SIZE;i++)if(!cards.get(i).isEmpty())saved.add(new SlotStack(i,cards.get(i)));out.store("Cards",SlotStack.CODEC.listOf(),saved);if(owner!=null)out.putString("Owner",owner.toString());List<Viewer> vs=new ArrayList<>();viewerNames.forEach((id,name)->vs.add(new Viewer(id.toString(),name)));out.store("Viewers",Viewer.CODEC.listOf(),vs);if(linkedControl!=null)out.putString("LinkedControl",pos(linkedControl));out.putBoolean("RevealAll",revealAll);}

 static String pos(BlockPos p){return p.getX()+","+p.getY()+","+p.getZ();}
 static BlockPos parsePos(String s){try{String[] p=s.split(",");if(p.length==3)return new BlockPos(Integer.parseInt(p[0]),Integer.parseInt(p[1]),Integer.parseInt(p[2]));}catch(Exception ignored){}return null;}
 private record SlotStack(int slot,ItemStack stack){static final Codec<SlotStack> CODEC=RecordCodecBuilder.create(i->i.group(Codec.INT.fieldOf("Slot").forGetter(SlotStack::slot),ItemStack.CODEC.fieldOf("Stack").forGetter(SlotStack::stack)).apply(i,SlotStack::new));}
 private record Viewer(String uuid,String name){static final Codec<Viewer> CODEC=RecordCodecBuilder.create(i->i.group(Codec.STRING.fieldOf("Uuid").forGetter(Viewer::uuid),Codec.STRING.fieldOf("Name").forGetter(Viewer::name)).apply(i,Viewer::new));}

 @Override public int getContainerSize(){return SIZE;}
 @Override public boolean isEmpty(){return cardCount()==0;}
 @Override public ItemStack getItem(int slot){return slot>=0&&slot<SIZE?cards.get(slot):ItemStack.EMPTY;}
 @Override public ItemStack removeItem(int slot,int amount){if(slot<0||slot>=SIZE)return ItemStack.EMPTY;ItemStack cur=cards.get(slot);if(cur.isEmpty())return ItemStack.EMPTY;ItemStack out=cur.split(amount);if(cur.isEmpty())cards.set(slot,ItemStack.EMPTY);changed();return out;}
 @Override public ItemStack removeItemNoUpdate(int slot){if(slot<0||slot>=SIZE)return ItemStack.EMPTY;ItemStack out=cards.get(slot);cards.set(slot,ItemStack.EMPTY);return out;}
 @Override public void setItem(int slot,ItemStack stack){if(slot>=0&&slot<SIZE){cards.set(slot,stack);changed();}}
 @Override public void setChanged(){super.setChanged();}
 @Override public boolean stillValid(Player player){return level!=null&&player.distanceToSqr(worldPosition.getX()+.5,worldPosition.getY()+.5,worldPosition.getZ()+.5)<=64;}
 @Override public void clearContent(){for(int i=0;i<SIZE;i++)cards.set(i,ItemStack.EMPTY);changed();}
}
