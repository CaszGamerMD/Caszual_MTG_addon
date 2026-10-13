package dev.casz.caszualmtg;

import com.spider.mtgcard.api.*;
import com.spider.mtgcard.cards.CardNbt;
import com.spider.mtgcard.cardstore.*;
import com.spider.mtgcard.content.pack.cache.*;
import com.spider.mtgcard.deckbox.*;
import com.spider.mtgcard.util.*;
import net.minecraft.core.*;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.item.ItemStack;
import java.util.*;
import java.util.concurrent.*;

/**
 * Autonomous, world-saved Deck Builder pipeline.
 *
 * URL fetch -> network/card status scan -> fill target -> shop missing.
 * No menu, player entity or open GUI is needed after the request is queued.
 * Every mutation is performed on the server thread and checkpointed on the
 * Builder block entity; callbacks are guarded by the block's generation token.
 */
public final class AutoDeckBuilder {
 private AutoDeckBuilder(){}
 private static final org.slf4j.Logger LOG=org.slf4j.LoggerFactory.getLogger("caszual_mtg");
 private record Pick(String key,ItemStack card,int slot){}
 private record Target(ItemStack portable,DeckboxBlockEntity placed,DeckboxTransfer.Loaded contents) {
  boolean slotted(){return placed==null;}
  String name(){return slotted()?"slotted deckbox":"adjacent deckbox";}
 }
 public static void start(BuilderBlockEntity be,UUID player,String url,int flags){
  String address=url.trim();
  ArchidektImport.deckId(address); // validate before cancelling the previous job
  boolean cached=be.cached(address);
  String saved=cached?be.deck():"";
  long token=be.beginAuto(player,address,flags);
  if(cached){
   be.loaded(token,saved,address,flags);
   be.autoStage(token,"scan","Using saved URL list. Scanning connected card network…");
  }
 }
 public static void tick(ServerLevel level,BuilderBlockEntity be){
  if(!be.autoActive()||be.autoInFlight()||level.getGameTime()%20!=0||level.getGameTime()<be.autoRetryAt())return;
  long token=be.revision();
  try{
   switch(be.autoStage()){
    case "fetch" -> fetch(level,be,token);
    case "scan" -> scan(level,be,token);
    case "fill" -> fill(level,be,token);
    case "shop" -> shop(level,be,token);
    case "wait_box" -> {
     if(target(level,be)!=null)be.autoStage(token,"fill","Deckbox detected. Loading available cards…");
    }
    case "wait_store" -> {
     if(nearbyStore(level,be.getBlockPos())!=null)be.autoStage(token,"shop","Card Store found. Preparing missing cards…");
    }
    case "wait_shop_box" -> {
     CardStoreBlockEntity store=nearbyStore(level,be.getBlockPos());
     if(store==null)be.autoStage(token,"wait_store","Waiting for a Card Store within four blocks.");
     else if(((CardStoreBoxAccess)store).caszual$getDeckbox().isEmpty())
      be.autoStage(token,"shop","Card Store output is clear. Preparing cart and deckbox transfer…");
    }
   }
  }catch(RuntimeException e){
   LOG.error("Auto Deck Builder failed at {} stage {} ({}).",be.getBlockPos(),be.autoStage(),token,e);
   be.autoError(token,"Auto-build stopped safely: "+safe(e)+". Reset/re-import to retry.");
  }
 }
 private static boolean current(ServerLevel level,BuilderBlockEntity be,long token){
  return level.hasChunkAt(be.getBlockPos())&&level.getBlockEntity(be.getBlockPos())==be&&be.autoValid(token);
 }
 private static String safe(Throwable t){
  Throwable cause=t instanceof CompletionException&&t.getCause()!=null?t.getCause():t;
  return cause.getMessage()==null?cause.getClass().getSimpleName():cause.getMessage();
 }
 private static void fetch(ServerLevel level,BuilderBlockEntity be,long token){
  String url=be.url();
  be.autoInFlight(true);
  ArchidektImport.fetch(url).whenComplete((result,error)->level.getServer().execute(()->{
   if(!current(level,be,token))return;
   be.autoInFlight(false);
   if(error!=null){be.autoError(token,"Archidekt import failed: "+safe(error));return;}
   DeckList.Parsed parsed=DeckList.parse(result.text());
   if(!parsed.errors().isEmpty()||parsed.lines().isEmpty()){
    be.autoError(token,"Archidekt returned an empty or invalid main deck.");return;
   }
   be.loaded(token,result.text(),url,be.flags());
   be.autoStage(token,"scan","Imported "+result.cards()+" cards. Scanning card network and resolving status…");
  }));
 }
 static Set<Integer> links(ServerLevel level,BlockPos pos){
  Set<Integer> out=new HashSet<>();
  for(BlockPos at:BlockPos.betweenClosed(pos.offset(-4,-4,-4),pos.offset(4,4,4))){
   if(!level.hasChunkAt(at))continue;
   int kind=CaszualMtg.kind(level.getBlockState(at).getBlock());
   if(kind>=0&&kind<3)out.add(kind);
  }
  return out;
 }
 static CardStoreBlockEntity nearbyStore(ServerLevel level,BlockPos pos){
  CardStoreBlockEntity nearest=null;double distance=Double.MAX_VALUE;
  for(BlockPos at:BlockPos.betweenClosed(pos.offset(-4,-4,-4),pos.offset(4,4,4))){
   if(!level.hasChunkAt(at))continue;
   if(level.getBlockEntity(at) instanceof CardStoreBlockEntity store){
    double d=at.distSqr(pos);if(d<distance){nearest=store;distance=d;}
   }
  }
  return nearest;
 }
 private static void seed(ServerLevel level,Banks bank){
  for(var c:PersistentCardStore.load(level).snapshot()){
   ItemStack card=CardStackBuilders.buildScryfallStackFromModel(c,false);
   int kind=Banks.kind(card);
   if(kind<2&&!bank.entries.containsKey(Banks.key(kind,card)))bank.add(card,kind,1);
  }
 }
 private static void scan(ServerLevel level,BuilderBlockEntity be,long token){
  Banks bank=Banks.get(level.getServer());seed(level,bank);
  Set<Integer> linked=links(level,be.getBlockPos());
  List<DeckList.Line> lines=DeckList.parse(be.deck()).lines();
  if(lines.isEmpty()){be.autoError(token,"No saved decklist to scan.");return;}
  // Resolve missing land/token metadata before counting and loading. No
  // inventory mutation occurs until the scan finishes successfully.
  List<String> unknown=(!linked.contains(0)&&!linked.contains(1))?List.of():
   lines.stream().map(DeckList.Line::name).distinct()
    .filter(name->bank.entries.values().stream().noneMatch(e->
      DeckList.normalize(TcgCardMeta.displayName(e.card())).equals(DeckList.normalize(name))))
    .limit(100).toList();
  if(unknown.isEmpty()){scanDone(level,be,token,bank,linked,lines);return;}
  be.autoInFlight(true);
  List<CompletableFuture<ScryfallModels.Card>> futures=unknown.stream().map(name->
   ScryfallNamedFetch.fetchNamedFuzzyAsync(name).thenCompose(hit->{
    if(hit==null||!DeckList.normalize(hit.name()).equals(DeckList.normalize(name)))
     return CompletableFuture.<ScryfallModels.Card>completedFuture(null);
    return ScryfallExactFetch.fetchBySetCollectorAsync(level,hit.set(),hit.collectorNumber());
   }).exceptionally(e->null)).toList();
  CompletableFuture.allOf(futures.toArray(CompletableFuture[]::new)).whenComplete((ignored,error)->
   level.getServer().execute(()->{
    if(!current(level,be,token))return;
    be.autoInFlight(false);
    try{
     for(var future:futures){
      var model=future.getNow(null);if(model==null)continue;
      ItemStack card=CardStackBuilders.buildScryfallStackFromModel(model,false);
      int kind=Banks.kind(card);
      if(kind<2&&linked.contains(kind))bank.add(card,kind,1);
     }
     scanDone(level,be,token,bank,linked,lines);
    }catch(RuntimeException e){be.autoError(token,"Network scan failed: "+safe(e));}
   }));
 }
 static List<Map.Entry<String,Banks.Entry>> candidates(Banks bank,Set<Integer> linked,DeckList.Line line){
  String name=DeckList.normalize(line.name());
  return bank.entries.entrySet().stream()
   .filter(e->linked.contains(e.getValue().kind()))
   .filter(e->DeckList.normalize(TcgCardMeta.displayName(e.getValue().card())).equals(name))
   .sorted((a,b)->Boolean.compare(
      line.exactPrinting(TcgCardMeta.read(b.getValue().card()).set(),TcgCardMeta.read(b.getValue().card()).collectorNumber()),
      line.exactPrinting(TcgCardMeta.read(a.getValue().card()).set(),TcgCardMeta.read(a.getValue().card()).collectorNumber())))
   .toList();
 }
 private static void scanDone(ServerLevel level,BuilderBlockEntity be,long token,Banks bank,Set<Integer> linked,List<DeckList.Line> lines){
  if(!current(level,be,token))return;
  Map<String,Long> stock=new HashMap<>();
  for(var entry:bank.entries.entrySet())stock.put(entry.getKey(),entry.getValue().count());
  List<Wire.Row> status=new ArrayList<>();
  List<String> summary=new ArrayList<>();
  for(DeckList.Line line:lines){
   int need=line.quantity(),found=0;ItemStack preview=ItemStack.EMPTY;
   for(var item:candidates(bank,linked,line)){
    var entry=item.getValue();
    long available=entry.kind()<2?need:stock.getOrDefault(item.getKey(),0L);
    int count=(int)Math.min(need,available);
    if(count<=0)continue;
    if(preview.isEmpty())preview=entry.card().copy();
    need-=count;found+=count;
    if(entry.kind()==2)stock.put(item.getKey(),available-count);
    if(need==0)break;
   }
   status.add(new Wire.Row(line.label(),preview,found,line.quantity()));
   summary.add(found+"/"+line.quantity()+" "+line.label());
  }
  be.autoScan(token,status,String.join("\n",summary));
 }
 private static Target target(ServerLevel level,BuilderBlockEntity be){
  if(!be.getItem(0).isEmpty())
   return new Target(be.getItem(0),null,DeckboxTransfer.load(level.getServer(),be.getItem(0)));
  for(Direction direction:Direction.values()){
   BlockPos at=be.getBlockPos().relative(direction);
   if(level.hasChunkAt(at)&&level.getBlockEntity(at) instanceof DeckboxBlockEntity placed)
    return new Target(ItemStack.EMPTY,placed,
     new DeckboxTransfer.Loaded(placed.getStorageId()==null?new UUID(0,0):placed.getStorageId(),
      "placed","",DeckboxTransfer.copy(
       java.util.stream.IntStream.range(0,DeckboxBlockEntity.INVENTORY_SIZE).mapToObj(placed::getItem).toList())));
  }
  return null;
 }
 private static void fill(ServerLevel level,BuilderBlockEntity be,long token){
  Target target=target(level,be);
  if(target==null){be.autoStage(token,"wait_box","Network scan complete. Waiting for a deckbox in the Builder slot or directly adjacent.");return;}
  Banks bank=Banks.get(level.getServer());
  Set<Integer> linked=links(level,be.getBlockPos());
  List<DeckList.Line> lines=DeckList.parse(be.deck()).lines();
  List<ItemStack> items=target.contents().items();
  Map<String,Long> stock=new HashMap<>();
  for(var entry:bank.entries.entrySet())stock.put(entry.getKey(),entry.getValue().count());
  // Recognize any cards already inside the target, so reloaded/retried jobs
  // cannot silently duplicate them. Each existing card is counted only once.
  boolean[] accounted=new boolean[items.size()];
  Map<Integer,ItemStack> insertions=new LinkedHashMap<>();
  Map<String,Long> consumed=new LinkedHashMap<>();
  List<DeckList.Line> missing=new ArrayList<>();
  List<Wire.Row> statuses=new ArrayList<>();
  int added=0;
  for(int lineNo=0;lineNo<lines.size();lineNo++){
   DeckList.Line line=lines.get(lineNo);
   int need=line.quantity(),present=0;ItemStack preview=ItemStack.EMPTY;
   for(int index=0;index<items.size();index++){
    ItemStack item=items.get(index);
    if(accounted[index]||item.isEmpty()||!DeckList.normalize(TcgCardMeta.displayName(item)).equals(DeckList.normalize(line.name())))continue;
    if(!line.exactPrinting(TcgCardMeta.read(item).set(),TcgCardMeta.read(item).collectorNumber()))continue;
    accounted[index]=true;need-=1;present+=1;preview=item.copy();
    if(need==0)break;
   }
   for(var entry:candidates(bank,linked,line)){
    if(need<=0)break;
    Banks.Entry found=entry.getValue();
    long available=found.kind()<2?need:stock.getOrDefault(entry.getKey(),0L);
    int count=(int)Math.min(need,available);
    for(int n=0;n<count;n++){
     int index=-1;
     // MTGCard's commander slot is the SECOND_SIDE_SLOT (100).
     if((be.flags()&2)!=0&&lineNo==0&&present==0
         &&CardNbt.isCommanderLegal(found.card())
         &&items.get(DeckboxBlockEntity.SECOND_SIDE_SLOT).isEmpty()
         &&!insertions.containsKey(DeckboxBlockEntity.SECOND_SIDE_SLOT))index=DeckboxBlockEntity.SECOND_SIDE_SLOT;
     else for(int i=0;i<DeckboxBlockEntity.MAIN_SLOTS;i++)
      if(items.get(i).isEmpty()&&!insertions.containsKey(i)){index=i;break;}
     if(index<0)break;
     ItemStack card=CardDatabaseCards.copyForExtraction(found.card());card.setCount(1);
     CardDatabaseCards.ensureUniqueUid(card);
     insertions.put(index,card);
     if(preview.isEmpty())preview=found.card().copy();
     present++;need--;added++;
     if(found.kind()==2){stock.compute(entry.getKey(),(k,v)->v==null?0:v-1);consumed.merge(entry.getKey(),1L,Long::sum);}
    }
   }
   if(need>0)missing.add(new DeckList.Line(line.name(),need,line.set(),line.collector()));
   statuses.add(new Wire.Row(line.label(),preview,present,line.quantity()));
  }
  if(!insertions.isEmpty()){
   if(target.slotted()){
    // External deckbox storage is authoritative: save the populated record
    // successfully before removing finite community stock.
    for(var insertion:insertions.entrySet())items.set(insertion.getKey(),insertion.getValue());
    DeckboxTransfer.save(level.getServer(),target.portable(),target.contents());
    be.setChanged();
   }else{
    for(var insertion:insertions.entrySet())target.placed().setItem(insertion.getKey(),insertion.getValue());
    target.placed().sync();
   }
   consumed.forEach(bank::take);
  }
  be.autoFilled(token,statuses,missing,added,target.name());
 }
 private static CompletableFuture<CardStoreScreenHandler.CartEntryData> storeLine(ServerLevel level,DeckList.Line line){
  CompletableFuture<ScryfallModels.Card> future;
  if(line.hasPrinting())future=ScryfallExactFetch.fetchBySetCollectorAsync(level,line.set(),line.collector());
  else future=ScryfallNamedFetch.fetchNamedFuzzyAsync(line.name()).thenCompose(hit->
   hit==null?CompletableFuture.<ScryfallModels.Card>completedFuture(null):
    ScryfallExactFetch.fetchBySetCollectorAsync(level,hit.set(),hit.collectorNumber()));
  return future.handle((model,error)->{
   if(error!=null||model==null)return null;
   ItemStack card=CardStackBuilders.buildScryfallStackFromModel(model,false);
   if(card==null||card.isEmpty())return null;
   long price=1L;
   if(model.price!=null)price=CardStorePrice.toCurrencyItemsFromStrings(false,model.price.usd,
    model.price.usdFoil,model.price.usdEtched,model.price.eur,model.price.eurFoil,model.price.tix);
   return new CardStoreScreenHandler.CartEntryData(TcgGameRegistry.MTG,model.set,model.collectorNumber,card,price,line.quantity());
  });
 }
 private static void shop(ServerLevel level,BuilderBlockEntity be,long token){
  List<DeckList.Line> missing=be.autoMissing();
  if(missing.isEmpty()){be.autoDone(token,"Deck assembled. No cards to shop.");return;}
  CardStoreBlockEntity store=nearbyStore(level,be.getBlockPos());
  if(store==null){be.autoStage(token,"wait_store","Loaded available cards. Waiting for a Card Store within four blocks to send "+missing.size()+" missing lines.");return;}
  if(be.autoOwner()==null){be.autoError(token,"No player owner saved; cannot assign a private Card Store cart.");return;}
  ItemStack inserted=be.getItem(0);
  if(!inserted.isEmpty()&&!((CardStoreBoxAccess)store).caszual$getDeckbox().isEmpty()){
   be.autoStage(token,"wait_shop_box","Card Store already has a deckbox. Empty its output slot to transfer this Builder's deckbox safely.");return;
  }
  be.autoInFlight(true);
  List<CompletableFuture<CardStoreScreenHandler.CartEntryData>> futures=missing.stream().map(line->storeLine(level,line)).toList();
  CompletableFuture.allOf(futures.toArray(CompletableFuture[]::new)).whenComplete((ignored,error)->
   level.getServer().execute(()->{
    if(!current(level,be,token))return;
    be.autoInFlight(false);
    CardStoreBlockEntity destination=nearbyStore(level,be.getBlockPos());
    if(destination==null){be.autoStage(token,"wait_store","Card Store unloaded during preparation; waiting to retry.");return;}
    if(!be.getItem(0).isEmpty()&&!((CardStoreBoxAccess)destination).caszual$getDeckbox().isEmpty()){
     be.autoStage(token,"wait_shop_box","Card Store output occupied. Remove its deckbox to continue.");return;
    }
    List<CardStoreScreenHandler.CartEntryData> cart=futures.stream().map(f->f.getNow(null)).filter(Objects::nonNull).toList();
    if(cart.isEmpty()){be.autoError(token,"No missing card lines could be resolved for the Card Store.");return;}
    try{
     // Handoff only the Builder's inserted box, never an adjacent placed box.
     // Never replace a box already inserted in the Card Store.
     boolean moved=false;
     if(!be.getItem(0).isEmpty()){
      ItemStack outgoing=be.getItem(0).copy();
      ((CardStoreBoxAccess)destination).caszual$setDeckbox(outgoing);
      be.setItem(0,ItemStack.EMPTY);
      moved=true;
     }
     destination.setSelectedGame(be.autoOwner(),TcgGameRegistry.MTG);
     destination.setSavedCart(be.autoOwner(),cart);
     be.autoDone(token,"Loaded available cards. Sent "+cart.size()+" missing card lines to Card Store"
       +(moved?" and moved the filled deckbox to its output slot.":".")
       +(cart.size()<missing.size()?" Some missing entries could not be resolved.":""));
    }catch(RuntimeException e){LOG.error("Deck Builder Card Store handoff failed",e);
     be.autoError(token,"Could not submit shopping cart: "+safe(e));}
   }));
 }
}
