package dev.casz.caszualmtg;

import com.mojang.serialization.Codec;
import com.mojang.serialization.codecs.RecordCodecBuilder;
import com.spider.mtgcard.deckbox.DeckboxBlockItem;
import net.minecraft.core.BlockPos;
import net.minecraft.world.Container;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.level.block.entity.BlockEntity;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.storage.ValueInput;
import net.minecraft.world.level.storage.ValueOutput;
import java.util.*;

/** Block-owned output slot and persistent draft; survives closing the GUI and server restarts. */
public final class BuilderBlockEntity extends BlockEntity implements Container {
 private ItemStack box=ItemStack.EMPTY;
 private String deck="",url="",requestedUrl="",report="",message="";
 private boolean resolving;
 private int flags=2;
 private long cachedAt;
 private long revision;
 private List<Wire.Row> statuses=List.of();
 // The automation is owned by this block entity, never by the player's menu session.
 // Stage and missing cards survive closing the GUI, logouts and server restarts.
 private String autoStage="idle",autoMissing="";
 private UUID autoOwner;
 private transient boolean autoInFlight;
 private transient long autoRetryAt;

 public BuilderBlockEntity(BlockPos at,BlockState state){super(CaszualMtg.BUILDER_BE,at,state);}
 public String deck(){return deck;}
 public String url(){return requestedUrl.isBlank()?url:requestedUrl;}
 public String report(){return report;}
 public String message(){return message;}
 public int flags(){return flags;}
 public boolean resolving(){return resolving;}
 public long revision(){return revision;}
 public List<Wire.Row> statuses(){return statuses;}
 public String autoStage(){return autoStage;}
 public UUID autoOwner(){return autoOwner;}
 public boolean autoInFlight(){return autoInFlight;}
 public void autoInFlight(boolean running){autoInFlight=running;}
 public long autoRetryAt(){return autoRetryAt;}
 public void autoRetryAt(long when){autoRetryAt=when;}
 public List<DeckList.Line> autoMissing(){return DeckList.parse(autoMissing).lines();}
 public boolean autoActive(){return !autoStage.equals("idle")&&!autoStage.equals("done")&&!autoStage.equals("failed");}
 public boolean autoValid(long token){return revision==token&&autoActive();}
 public long beginAuto(UUID owner,String address,int options){
  long token=start(address,options);
  autoOwner=owner;autoStage="fetch";autoMissing="";autoInFlight=false;
  report="";statuses=List.of();autoRetryAt=0;
  setChanged();return token;
 }
 public void autoStage(long token,String stage,String progress){
  if(!autoValid(token))return;
  autoStage=stage;message=progress;resolving=!stage.equals("done")&&!stage.equals("failed");
  autoInFlight=false;setChanged();
 }
 public void autoScan(long token,List<Wire.Row> rows,String text){
  if(!autoValid(token))return;
  statuses=List.copyOf(rows);report=text;
  autoStage="fill";message="Network scan complete. Loading available cards into deckbox…";
  resolving=true;autoInFlight=false;setChanged();
 }
 public void autoFilled(long token,List<Wire.Row> rows,List<DeckList.Line> missing,int added,String destination){
  if(!autoValid(token))return;
  statuses=List.copyOf(rows);
  autoMissing=missing.stream().map(l->l.quantity()+" "+l.label()).collect(java.util.stream.Collectors.joining("\n"));
  report=missing.stream().map(l->l.shopLine(l.quantity())).collect(java.util.stream.Collectors.joining("\n"));
  autoStage=missing.isEmpty()?"done":"shop";
  resolving=!missing.isEmpty();
  message="Loaded "+added+" available cards into "+destination+". "+(missing.isEmpty()?"Deck complete.":"Preparing "+missing.stream().mapToInt(DeckList.Line::quantity).sum()+" remaining cards for Card Store.");
  autoInFlight=false;setChanged();
 }
 public void autoDone(long token,String progress){
  if(!autoValid(token))return;
  autoStage="done";resolving=false;message=progress;autoInFlight=false;setChanged();
 }
 public void autoError(long token,String progress){
  if(!autoValid(token))return;
  autoStage="failed";resolving=false;message=progress;autoInFlight=false;setChanged();
 }
 public boolean cached(String address){return !resolving&&!deck.isBlank()&&url.equals(address)&&cachedAt>0&&System.currentTimeMillis()-cachedAt<6*60*60*1000L;}
 public long start(String address,int flags){revision++;requestedUrl=address;message="Loading decklist…";resolving=true;this.flags=flags;setChanged();return revision;}
 public long reset(){revision++;deck="";url="";requestedUrl="";report="";message="Deck Builder cleared.";statuses=List.of();cachedAt=0;resolving=false;flags=2;autoStage="idle";autoMissing="";autoOwner=null;autoInFlight=false;setChanged();return revision;}
 public void loaded(long token,String deck,String url,int flags){
  if(token!=revision)return;this.deck=deck;this.url=url;this.requestedUrl=url;this.flags=flags;cachedAt=System.currentTimeMillis();resolving=true;
  message="Resolving availability…";setChanged();
 }
 public void complete(long token,String report,String message,List<Wire.Row> statuses){
  if(token!=revision)return;this.report=report;this.message=message;this.statuses=List.copyOf(statuses);this.resolving=false;setChanged();
 }
 public void failed(long token,String message){if(token!=revision)return;this.message=message;requestedUrl=url;resolving=false;setChanged();}
 @Override protected void loadAdditional(ValueInput in){
  super.loadAdditional(in);
  box=in.read("Deckbox",ItemStack.CODEC).orElse(ItemStack.EMPTY);
  if(!box.isEmpty()&&!(box.getItem() instanceof DeckboxBlockItem))box=ItemStack.EMPTY;
  deck=in.getStringOr("Decklist","");url=in.getStringOr("Url","");requestedUrl=in.getStringOr("RequestedUrl",url);
  report=in.getStringOr("Report","");message=in.getStringOr("Message","");
  flags=in.getIntOr("Flags",2);cachedAt=in.getLongOr("CachedAt",0);
  autoStage=in.getStringOr("AutoStage","idle");
  autoMissing=in.getStringOr("AutoMissing","");
  String owner=in.getStringOr("AutoOwner","");
  try{autoOwner=owner.isEmpty()?null:UUID.fromString(owner);}catch(IllegalArgumentException ignored){autoOwner=null;}
  autoInFlight=false;autoRetryAt=0;
  revision=in.getLongOr("Revision",0);resolving=in.getBooleanOr("Resolving",false);
  statuses=in.read("Rows",RowSave.CODEC.listOf()).orElse(List.of()).stream().map(r->new Wire.Row(r.name,r.card,r.count,r.total)).toList();
  // Pending futures don't survive a full server restart. The input remains saved.
  if(resolving&&!autoActive()){resolving=false;requestedUrl=url;message="Draft restored. Press Check cards to update availability.";}
  // Active autoStage takes precedence and resumes from its saved checkpoint on server tick.
  if(autoActive())resolving=true;
 }
 @Override protected void saveAdditional(ValueOutput out){
  super.saveAdditional(out);
  if(!box.isEmpty())out.store("Deckbox",ItemStack.CODEC,box);
  out.putString("Decklist",deck);out.putString("Url",url);out.putString("RequestedUrl",requestedUrl);
  out.putString("Report",report);out.putString("Message",message);
  out.putInt("Flags",flags);out.putLong("CachedAt",cachedAt);
  out.putString("AutoStage",autoStage);out.putString("AutoMissing",autoMissing);
  if(autoOwner!=null)out.putString("AutoOwner",autoOwner.toString());
  out.putLong("Revision",revision);out.putBoolean("Resolving",resolving);
  out.store("Rows",RowSave.CODEC.listOf(),statuses.stream().map(r->new RowSave(r.key(),r.card(),r.count(),r.requested())).toList());
 }
 record RowSave(String name,ItemStack card,long count,int total){
  static final Codec<RowSave> CODEC=RecordCodecBuilder.create(i->i.group(
    Codec.STRING.fieldOf("Name").forGetter(RowSave::name),
    ItemStack.CODEC.fieldOf("Card").forGetter(RowSave::card),
    Codec.LONG.fieldOf("Count").forGetter(RowSave::count),
    Codec.INT.fieldOf("Total").forGetter(RowSave::total)
  ).apply(i,RowSave::new));
 }
 @Override public int getContainerSize(){return 1;}
 @Override public boolean isEmpty(){return box.isEmpty();}
 @Override public ItemStack getItem(int slot){return slot==0?box:ItemStack.EMPTY;}
 @Override public ItemStack removeItem(int slot,int amount){if(slot!=0)return ItemStack.EMPTY;ItemStack result=box.split(amount);if(box.isEmpty())box=ItemStack.EMPTY;setChanged();return result;}
 @Override public ItemStack removeItemNoUpdate(int slot){if(slot!=0)return ItemStack.EMPTY;ItemStack out=box;box=ItemStack.EMPTY;setChanged();return out;}
 @Override public void setItem(int slot,ItemStack item){if(slot==0&&(item.isEmpty()||item.getItem() instanceof DeckboxBlockItem)){box=item.copyWithCount(item.isEmpty()?0:1);setChanged();}}
 @Override public boolean stillValid(Player p){return level!=null&&level.getBlockState(worldPosition).is(CaszualMtg.BUILDER)&&p.distanceToSqr(worldPosition.getX()+.5,worldPosition.getY()+.5,worldPosition.getZ()+.5)<=64;}
 @Override public void clearContent(){box=ItemStack.EMPTY;setChanged();}
}
