package dev.casz.caszualmtg;
import com.spider.mtgcard.api.*;
import com.spider.mtgcard.util.*;
import com.spider.mtgcard.cards.CardNbt;
import com.spider.mtgcard.content.pack.cache.*;
import com.spider.mtgcard.deckbox.DeckboxBlockEntity;
import com.spider.mtgcard.cardstore.CardStoreBlockEntity;
import com.spider.mtgcard.cardstore.CardStoreScreenHandler;
import com.spider.mtgcard.cardstore.CardStorePrice;
import com.spider.mtgcard.display.CardDisplayEntity;
import net.fabricmc.fabric.api.networking.v1.ServerPlayNetworking;
import net.minecraft.core.*;
import net.minecraft.resources.ResourceKey;
import net.minecraft.world.level.Level;
import net.minecraft.world.item.ItemStack;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.phys.Vec3;
import java.util.*;
import java.util.concurrent.*;
public final class ServerLogic {
 static final class Session {
  final BlockPos pos;final int kind;final ResourceKey<Level> dimension;UUID entity,cardId;String deck="",report="";List<Wire.Row> statuses=List.of(),catalogueRows=List.of();List<DeckList.Line> missingLines=List.of();String query="",oracle="",stats="",artKey="";boolean artwork=false;int mana=0;int page=0,revision=0;long last=0;boolean busy;
  Session(ServerPlayer p,BlockPos pos,int kind){this.pos=pos.immutable();this.kind=kind;dimension=p.level().dimension();}
 }
 static final Map<UUID,Session> sessions=new HashMap<>();
 public static void close(ServerPlayer p){sessions.remove(p.getUUID());}
 static boolean valid(ServerPlayer p,Session s){if(sessions.get(p.getUUID())!=s||p.isRemoved()||!p.level().dimension().equals(s.dimension)||p.distanceToSqr(Vec3.atCenterOf(s.pos))>64||!p.level().hasChunkAt(s.pos))return false;if(s.kind==2&&(!(p.containerMenu instanceof CommunityMenu m)||!m.pos.equals(s.pos)))return false;return s.kind==4?counter(p,s)!=null:CaszualMtg.kind(p.level().getBlockState(s.pos).getBlock())==s.kind;}
 static CardDisplayEntity counter(ServerPlayer p,Session s){var e=p.level().getEntity(s.entity);return e instanceof CardDisplayEntity c&&!c.isRemoved()&&p.distanceToSqr(c)<64&&(p.getMainHandItem().is(CaszualMtg.COUNTER)||p.getOffhandItem().is(CaszualMtg.COUNTER))&&!c.getDisplayCardStack(s.cardId).isEmpty()?c:null;}
 public static void open(ServerPlayer p,BlockPos pos,int kind){if(kind==2)p.openMenu(CommunityMenu.provider(pos));Session s=new Session(p,pos,kind);sessions.put(p.getUUID(),s);seed(p);reply(p,s,kind==3?"Import a decklist, then review availability.":"Shared across this server. Search by name or type.","");if(kind<2)search(p,s,"",0,0);}
 public static void openCounter(ServerPlayer p,CardDisplayEntity c){if(p.distanceToSqr(c)>64)return;Session s=new Session(p,c.blockPosition(),4);s.entity=c.getUUID();s.cardId=c.getDisplayCardId(c.findSelectedDisplayIndex(p));if(s.cardId==null)return;sessions.put(p.getUUID(),s);reply(p,s,"Edit counters on this card.","");}
 static void seed(ServerPlayer p){Banks b=Banks.get(p.level().getServer());for(var c:PersistentCardStore.load(p.level()).snapshot()){ItemStack card=CardStackBuilders.buildScryfallStackFromModel(c,false);int kind=Banks.kind(card);if(kind<2&&!b.entries.containsKey(Banks.key(kind,card)))b.add(card,kind,1);}}
 public static void handle(ServerPlayer p,Wire.Request req){Session s=sessions.get(p.getUUID());if(s==null||!s.pos.equals(req.pos())||!valid(p,s))return;if(req.action().equals("close")){close(p);return;}long now=System.currentTimeMillis();if(now-s.last<150)return;s.last=now;if(s.busy&&!req.action().equals("search")&&!req.action().equals("arts")){reply(p,s,"Working on the previous request…",s.report);return;}s.revision++;
  try{
   switch(req.action()){
    case "search" -> {if(s.kind<3)search(p,s,req.text(),req.amount(),req.filter(),req.oracle(),req.stats());}
    case "arts" -> {if(s.kind<2)artworks(p,s,req.text(),req.amount());}
    case "deposit" -> {if(s.kind<3)deposit(p,s);}
    case "deposit_inventory" -> {if(s.kind==2)depositInventory(p,s);}
    case "deposit_loose" -> {if(s.kind==2&&p.containerMenu instanceof CommunityMenu menu)depositLoose(p,s,menu);}
    case "withdraw" -> {if(s.kind<3)withdraw(p,s,req.text(),req.amount());}
    case "box_deposit", "box_withdraw", "box_fill" -> {if(s.kind==2&&p.containerMenu instanceof CommunityMenu menu){Banks bank=Banks.get(p.level().getServer());int count=req.action().equals("box_deposit")?DeckboxTransfer.deposit(p,menu.deckbox(),bank):DeckboxTransfer.withdraw(p,menu.deckbox(),bank,req.action().equals("box_fill")?null:req.text(),s.query,Math.clamp(req.amount(),1,99));menu.broadcastChanges();reply(p,s,"Transferred "+count+" cards. Lands and tokens stay in the box during deposits.","");}}
    case "import" -> {if(s.kind==3){var list=DeckList.parse(req.text());if(!list.errors().isEmpty()){reply(p,s,"Import rejected: "+list.errors().getFirst(),String.join("\n",list.errors()));return;}if(list.lines().isEmpty()){reply(p,s,"No cards in the list.","");return;}s.deck=req.text();s.statuses=list.lines().stream().map(line->new Wire.Row(line.label(),ItemStack.EMPTY,-1,line.quantity())).toList();reply(p,s,"Loaded "+list.lines().size()+" card entries. Checking availability…","");resolveLands(p,s,()->plan(p,s,false,req.amount()));}}
    case "import_url" -> {if(s.kind==3)importArchidekt(p,s,req.text(),req.amount());}
    case "plan" -> {if(s.kind==3)plan(p,s,false,req.amount());}
    case "build" -> {if(s.kind==3)plan(p,s,true,req.amount());}
    case "shop" -> {if(s.kind==3)shopMissing(p,s);}
    case "counter" -> {if(s.kind==4)editCounter(p,s,req.text(),req.amount());}
   }
  }catch(Exception e){s.busy=false;org.slf4j.LoggerFactory.getLogger("caszual_mtg").error("Request failed",e);reply(p,s,"Request failed: "+e.getMessage(),s.report);}
 }
 static void reply(ServerPlayer p,Session s,String msg,String report){replyRows(p,s,msg,s.kind<2&&s.artwork?"art":report,s.kind==3?s.statuses:s.kind<2?s.catalogueRows:rows(p,s,s.query,s.page));}
 static void replyRows(ServerPlayer p,Session s,String msg,String report,List<Wire.Row> rows){if(valid(p,s))ServerPlayNetworking.send(p,new Wire.Reply(s.pos,s.kind,msg.length()>1900?msg.substring(0,1900):msg,report.length()>32000?report.substring(0,32000):report,rows));}
 static List<Wire.Row> rows(ServerPlayer p,Session s,String q,int page){if(s.kind==4){var c=counter(p,s);if(c==null)return List.of();ItemStack stack=c.getDisplayCardStack(s.cardId);return CardCounterNbt.readCounterMap(stack).entrySet().stream().limit(40).map(e->new Wire.Row(e.getKey(),stack.copy(),e.getValue())).toList();}if(s.kind==3)return List.of();return Banks.get(p.level().getServer()).search(s.kind,q).stream().filter(e->s.kind!=0||Catalogue.matchesMana(e.getValue().card(),s.mana)).filter(e->s.kind!=1||Catalogue.matchesToken(e.getValue().card(),s.oracle,s.stats)).skip((long)page*40).limit(40).map(e->new Wire.Row(e.getKey(),e.getValue().card().copy(),s.kind==2?e.getValue().count():-1)).toList();}
 static void search(ServerPlayer p,Session s,String q,int page,int mask){search(p,s,q,page,mask,"","");}
 static void search(ServerPlayer p,Session s,String q,int requestedPage,int mask,String oracle,String stats){s.busy=false;if(q.length()>200||oracle.length()>200||stats.length()>40)throw new IllegalArgumentException("Search fields are too long.");if(s.kind==1)Catalogue.stats(stats);int page=Math.clamp(requestedPage,0,1000);s.page=page;s.query=q;s.mana=mask&511;s.oracle=oracle;s.stats=stats;s.artwork=false;s.catalogueRows=List.of();
  if(s.kind==2){replyRows(p,s,"Community collection — page "+(page+1),"",rows(p,s,q,page));return;}
  catalogue(p,s,Catalogue.search(s.kind,q,s.mana,page,s.oracle,s.stats),page,null);
 }
 static boolean matching(Session s,ItemStack card){return Banks.kind(card)==s.kind&&(s.kind==0?Catalogue.matchesMana(card,s.mana):Catalogue.matchesToken(card,s.oracle,s.stats));}
 static boolean sameArtFamily(ItemStack a,ItemStack b){String ai=StackData.readCustom(a).getString("caszual_mtg_oracle_id").orElse(""),bi=StackData.readCustom(b).getString("caszual_mtg_oracle_id").orElse("");if(!ai.isBlank()&&!bi.isBlank())return ai.equals(bi);var am=TcgCardMeta.read(a);var bm=TcgCardMeta.read(b);return am.name().equals(bm.name())&&am.typeLine().equals(bm.typeLine())&&am.oracleText().equals(bm.oracleText())&&am.power().equals(bm.power())&&am.toughness().equals(bm.toughness());}
 static void artworks(ServerPlayer p,Session s,String key,int requestedPage){
  s.busy=false;
  ItemStack family=s.catalogueRows.stream().filter(row->row.key().equals(key)).map(Wire.Row::card).filter(card->!card.isEmpty()).findFirst().map(ItemStack::copy).orElse(ItemStack.EMPTY);
  if(family.isEmpty()){var entry=Banks.get(p.level().getServer()).entries.get(key);if(entry!=null)family=entry.card().copy();}
  if(family.isEmpty()||Banks.kind(family)!=s.kind){reply(p,s,"Select a matching land or token first.","");return;}
  s.artwork=true;s.artKey=key;int page=Math.clamp(requestedPage,0,1000);
  catalogue(p,s,Catalogue.artworks(s.kind,family,page),page,family);
 }
 static void catalogue(ServerPlayer p,Session s,CompletableFuture<Catalogue.Page> future,int page,ItemStack family){s.busy=true;int revision=s.revision;future.whenComplete((result,error)->p.level().getServer().execute(()->{
   if(!valid(p,s)||s.revision!=revision)return;s.busy=false;
   if(error!=null){List<Wire.Row> cached=family==null?rows(p,s,s.query,page):Banks.get(p.level().getServer()).search(s.kind,"").stream().filter(e->sameArtFamily(family,e.getValue().card())).skip((long)page*40).limit(40).map(e->new Wire.Row(e.getKey(),e.getValue().card().copy(),-1)).toList();s.catalogueRows=cached;replyRows(p,s,"Online search unavailable; showing saved matching cards.",family==null?"":"art",cached);return;}
   Banks bank=Banks.get(p.level().getServer());List<Wire.Row> found=new ArrayList<>();for(var hit:result.cards()){ItemStack card=CardStackBuilders.buildScryfallStackFromModel(hit.model(),false);Catalogue.metadata(card,hit.model(),hit.mana(),hit.fullArt());if((family==null&&matching(s,card))||(family!=null&&Banks.kind(card)==s.kind&&sameArtFamily(family,card))){bank.add(card,s.kind,1);found.add(new Wire.Row(Banks.key(s.kind,card),card,-1));}}
   s.catalogueRows=List.copyOf(found);replyRows(p,s,(family==null?"Free catalogue":"Artwork choices")+" — page "+(page+1)+" · "+result.total()+" matches"+(result.hasMore()?" · more pages":""),family==null?"":"art",found);
  }));
 }
 static boolean eligibleLoose(ItemStack stack){
  return !stack.isEmpty()&&CardItemRegistry.isCard(stack)&&CardDatabaseCards.canStore(stack)&&Banks.kind(stack)==2;
 }
 static void deposit(ServerPlayer p,Session s){
  ItemStack held=p.getMainHandItem();
  if(held.isEmpty()||!CardItemRegistry.isCard(held)||!CardDatabaseCards.canStore(held)||Banks.kind(held)!=s.kind){reply(p,s,"Hold a matching, storable MTG card.","");return;}
  int count=held.getCount();
  Banks.get(p.level().getServer()).add(held,s.kind,count);
  held.shrink(count);p.getInventory().setChanged();p.inventoryMenu.broadcastChanges();
  reply(p,s,s.kind==2?"Deposited "+count+" cards.":"Card added to unlimited catalogue.","");
 }
 static void depositInventory(ServerPlayer p,Session s){
  Banks bank=Banks.get(p.level().getServer());int moved=0;
  for(int slot=0;slot<36;slot++){
   ItemStack card=p.getInventory().getItem(slot);
   if(!eligibleLoose(card))continue;
   int count=card.getCount();
   bank.add(card,2,count);
   card.shrink(count);
   moved+=count;
  }
  if(moved>0){p.getInventory().setChanged();p.inventoryMenu.broadcastChanges();}
  reply(p,s,moved>0?"Deposited "+moved+" regular cards from your inventory.":"No regular MTG cards found in your inventory.","");
 }
 static void depositLoose(ServerPlayer p,Session s,CommunityMenu menu){
  ItemStack stack=menu.looseCard();
  if(!eligibleLoose(stack)){reply(p,s,"Put regular MTG cards in the loose-card input slot.","");return;}
  int count=stack.getCount();
  Banks.get(p.level().getServer()).add(stack,2,count);
  menu.consumeLoose();
  reply(p,s,"Deposited "+count+" loose card"+(count==1?"":"s")+" into the shared collection.","");
 }
 static void withdraw(ServerPlayer p,Session s,String key,int qty){if(qty<1||qty>64)return;Banks b=Banks.get(p.level().getServer());Banks.Entry entry=b.entries.get(key);if(entry==null||entry.kind()!=s.kind||Banks.kind(entry.card())!=s.kind){reply(p,s,"Card is no longer available.","");return;}if(s.kind<2&&(!matching(s,entry.card())||s.catalogueRows.stream().noneMatch(row->row.key().equals(key)))){reply(p,s,"Choose a card from the current results.","");return;}int count=s.kind==2?(int)Math.min(qty,entry.count()):qty;
  // Check empty inventory slots first; cards have individual UIDs and must not merge.
  List<Integer> free=new ArrayList<>();for(int i=0;i<36;i++)if(p.getInventory().getItem(i).isEmpty())free.add(i);if(free.size()<count){reply(p,s,"Need "+count+" empty inventory slots; try a smaller quantity.","");return;}
  for(int i=0;i<count;i++){ItemStack card=CardDatabaseCards.copyForExtraction(entry.card());card.setCount(1);CardDatabaseCards.ensureUniqueUid(card);p.getInventory().setItem(free.get(i),card);}if(s.kind==2)b.take(key,count);p.inventoryMenu.broadcastChanges();reply(p,s,"Received "+count+" cards.","");
 }
 static Set<Integer> links(ServerPlayer p,Session s){Set<Integer> kinds=new HashSet<>();for(BlockPos at:BlockPos.betweenClosed(s.pos.offset(-4,-4,-4),s.pos.offset(4,4,4)))if(p.level().hasChunkAt(at)){int kind=CaszualMtg.kind(p.level().getBlockState(at).getBlock());if(kind>=0&&kind<3)kinds.add(kind);}return kinds;}
 static DeckboxBlockEntity output(ServerPlayer p,Session s){for(Direction d:Direction.values()){BlockPos at=s.pos.relative(d);if(p.level().hasChunkAt(at)&&p.level().getBlockEntity(at) instanceof DeckboxBlockEntity db)return db;}return null;}
 static void importArchidekt(ServerPlayer p,Session s,String url,int flags){
  if(s.busy){reply(p,s,"Working on the previous request…",s.report);return;}
  long revision=s.revision;s.busy=true;reply(p,s,"Loading Archidekt main deck…","");
  ArchidektImport.fetch(url).whenComplete((result,error)->p.level().getServer().execute(()->{
   if(!valid(p,s)||s.revision!=revision)return;s.busy=false;
   if(error!=null){Throwable cause=error instanceof CompletionException&&error.getCause()!=null?error.getCause():error;reply(p,s,"Archidekt import failed: "+cause.getMessage(),"");return;}
   var parsed=DeckList.parse(result.text());if(!parsed.errors().isEmpty()){reply(p,s,"Archidekt import rejected: "+parsed.errors().getFirst(),"");return;}
   s.deck=result.text();s.statuses=parsed.lines().stream().map(line->new Wire.Row(line.label(),ItemStack.EMPTY,-1,line.quantity())).toList();
   reply(p,s,"Loaded "+result.cards()+" main-deck cards from "+(result.deckName().isBlank()?"Archidekt":result.deckName())+". Sideboard and Maybeboard ignored.","");
   resolveLands(p,s,()->plan(p,s,false,flags));
  }));
 }

 static void resolveLands(ServerPlayer p,Session s,Runnable done){Set<Integer> linked=links(p,s);if(!linked.contains(0)&&!linked.contains(1)){done.run();return;}
  Banks b=Banks.get(p.level().getServer());List<String> unknown=DeckList.parse(s.deck).lines().stream().map(DeckList.Line::name).distinct().filter(name->b.entries.values().stream().noneMatch(e->DeckList.normalize(TcgCardMeta.displayName(e.card())).equals(DeckList.normalize(name)))).limit(100).toList();
  if(unknown.isEmpty()){done.run();return;}s.busy=true;reply(p,s,"Resolving land/token names…","");int revision=s.revision;
  List<CompletableFuture<ScryfallModels.Card>> requests=unknown.stream().map(name->ScryfallNamedFetch.fetchNamedFuzzyAsync(name)
   .thenCompose(hit->{if(hit==null||!DeckList.normalize(hit.name()).equals(DeckList.normalize(name)))return CompletableFuture.<ScryfallModels.Card>completedFuture(null);return ScryfallExactFetch.fetchBySetCollectorAsync(p.level(),hit.set(),hit.collectorNumber());})
   .exceptionally(error->null)).toList();
  CompletableFuture.allOf(requests.toArray(CompletableFuture[]::new)).whenComplete((ignored,error)->p.level().getServer().execute(()->{
   if(!valid(p,s)||s.revision!=revision)return;s.busy=false;
   for(var request:requests){var model=request.getNow(null);if(model==null)continue;ItemStack card=CardStackBuilders.buildScryfallStackFromModel(model,false);int kind=Banks.kind(card);if(kind<2&&linked.contains(kind))b.add(card,kind,1);}
   done.run();
  }));
 }
 record Pick(String key,ItemStack card,boolean commander){}
 static boolean exactPrinting(DeckList.Line line,ItemStack card){if(!line.hasPrinting())return true;var meta=TcgCardMeta.read(card);return line.exactPrinting(meta.set(),meta.collectorNumber());}
 static void plan(ServerPlayer p,Session s,boolean build,int flags){if(s.deck.isBlank()){reply(p,s,"Import a decklist first.","");return;}Set<Integer> linked=links(p,s);
  Banks b=Banks.get(p.level().getServer());var lines=DeckList.parse(s.deck).lines();Map<String,Long> available=new HashMap<>();for(var e:b.entries.entrySet())available.put(e.getKey(),e.getValue().count());List<Pick> picks=new ArrayList<>();List<String> missing=new ArrayList<>();List<DeckList.Line> missingLines=new ArrayList<>();List<Wire.Row> statuses=new ArrayList<>();StringBuilder summary=new StringBuilder();int requested=0,missingCount=0;
  boolean commanderFirst=(flags&2)!=0;
  int alternateArtCount=0;
  for(int i=0;i<lines.size();i++){
   var line=lines.get(i);int need=line.quantity();requested+=need;String name=DeckList.normalize(line.name());ItemStack preview=ItemStack.EMPTY;int alternateForLine=0;
   List<Map.Entry<String,Banks.Entry>> candidates=b.entries.entrySet().stream().filter(e->linked.contains(e.getValue().kind())&&DeckList.normalize(TcgCardMeta.displayName(e.getValue().card())).equals(name)).sorted((a,z)->Boolean.compare(line.exactPrinting(TcgCardMeta.read(z.getValue().card()).set(),TcgCardMeta.read(z.getValue().card()).collectorNumber()),line.exactPrinting(TcgCardMeta.read(a.getValue().card()).set(),TcgCardMeta.read(a.getValue().card()).collectorNumber()))).toList();
   for(var e:candidates){var entry=e.getValue();int amount=entry.kind()<2?need:(int)Math.min(need,available.getOrDefault(e.getKey(),0L));if(amount<=0)continue;if(preview.isEmpty())preview=entry.card().copy();boolean alternate=line.hasPrinting()&&!line.exactPrinting(TcgCardMeta.read(entry.card()).set(),TcgCardMeta.read(entry.card()).collectorNumber());if(alternate){alternateForLine+=amount;alternateArtCount+=amount;}for(int j=0;j<amount;j++)picks.add(new Pick(e.getKey(),entry.card(),commanderFirst&&i==0&&j==0));if(entry.kind()==2)available.put(e.getKey(),available.get(e.getKey())-amount);need-=amount;if(need==0)break;}
   if(need>0){missing.add(line.shopLine(need));missingLines.add(new DeckList.Line(line.name(),need,line.set(),line.collector()));missingCount+=need;}
   String label=line.label()+(alternateForLine>0?" · alternate art":"");statuses.add(new Wire.Row(label,preview.copy(),line.quantity()-need,line.quantity()));summary.append(line.quantity()-need).append('/').append(line.quantity()).append(" ").append(label).append('\n');
  }
  s.statuses=statuses;s.missingLines=List.copyOf(missingLines);s.report=String.join("\n",missing)+(missing.isEmpty()?"":"\n");String msg="Requested "+requested+" | available "+picks.size()+" | missing "+missingCount+(alternateArtCount>0?" | alternate art "+alternateArtCount:"")+". Linked: "+linked.stream().sorted().map(k->k==0?"lands":k==1?"tokens":"community").toList();
  if(!build){replyRows(p,s,msg,s.report,statuses);return;}
  if(missingCount>0&&(flags&1)==0){replyRows(p,s,"Missing cards. Choose Build available to assemble a partial deck.",s.report,statuses);return;}
  if(picks.isEmpty()){reply(p,s,"No available cards to build.",s.report);return;}
  DeckboxBlockEntity box=output(p,s);if(box==null){reply(p,s,"Place an MTGCard deckbox touching the builder.",s.report);return;}
  int commanders=(int)picks.stream().filter(Pick::commander).count(),main=picks.size()-commanders;
  if(main>DeckboxBlockEntity.MAIN_SLOTS){reply(p,s,"Deckbox has 99 main slots. Use First = commander for a 100-card deck.",s.report);return;}
  if(commanders>0&&!CardNbt.isCommanderLegal(picks.stream().filter(Pick::commander).findFirst().get().card)){reply(p,s,"The first card is not commander-legal.",s.report);return;}
  for(int i=0;i<box.getContainerSize();i++)if(!box.getStack(i).isEmpty()){reply(p,s,"Output deckbox must be empty.",s.report);return;}
  // All availability checks and both inventory mutations run on the server thread.
  int slot=0;Map<String,Long> consumed=new HashMap<>();for(Pick pick:picks){ItemStack card=CardDatabaseCards.copyForExtraction(pick.card);card.setCount(1);CardDatabaseCards.ensureUniqueUid(card);box.setStack(pick.commander?DeckboxBlockEntity.FIRST_SIDE_SLOT:slot++,card);if(b.entries.get(pick.key).kind()==2)consumed.merge(pick.key,1L,Long::sum);}
  consumed.forEach(b::take);box.markDirty();box.persistExternalRecord();box.sync();replyRows(p,s,"Built "+picks.size()+" cards into the adjacent deckbox.",s.report,statuses);
 }
 static CardStoreBlockEntity nearbyStore(ServerPlayer p,Session s){
  CardStoreBlockEntity best=null;double bestDistance=Double.MAX_VALUE;
  for(BlockPos at:BlockPos.betweenClosed(s.pos.offset(-4,-4,-4),s.pos.offset(4,4,4))){
   if(!p.level().hasChunkAt(at))continue;
   if(p.level().getBlockEntity(at) instanceof CardStoreBlockEntity store){
    double distance=at.distSqr(s.pos);
    if(distance<bestDistance){best=store;bestDistance=distance;}
   }
  }
  return best;
 }
 static CompletableFuture<CardStoreScreenHandler.CartEntryData> resolveStoreLine(ServerPlayer p,DeckList.Line line){
  CompletableFuture<ScryfallModels.Card> future;
  if(line.hasPrinting())future=ScryfallExactFetch.fetchBySetCollectorAsync(p.level(),line.set(),line.collector());
  else future=ScryfallNamedFetch.fetchNamedFuzzyAsync(line.name()).thenCompose(hit->hit==null?CompletableFuture.<ScryfallModels.Card>completedFuture(null):ScryfallExactFetch.fetchBySetCollectorAsync(p.level(),hit.set(),hit.collectorNumber()));
  return future.handle((model,error)->{
   if(error!=null||model==null)return null;
   ItemStack card=CardStackBuilders.buildScryfallStackFromModel(model,false);
   if(card==null||card.isEmpty())return null;
   long price=1L;
   if(model.price!=null)price=CardStorePrice.toCurrencyItemsFromStrings(false,model.price.usd,model.price.usdFoil,model.price.usdEtched,model.price.eur,model.price.eurFoil,model.price.tix);
   return new CardStoreScreenHandler.CartEntryData(TcgGameRegistry.MTG,model.set,model.collectorNumber,card,price,line.quantity());
  });
 }
 static void shopMissing(ServerPlayer p,Session s){
  if(s.missingLines.isEmpty()){reply(p,s,"No missing cards to send to the Card Store.",s.report);return;}
  CardStoreBlockEntity store=nearbyStore(p,s);
  if(store==null){reply(p,s,"No Card Store found within 4 blocks of the Deck Builder.",s.report);return;}
  s.busy=true;int revision=s.revision;reply(p,s,"Preparing "+s.missingLines.size()+" missing card lines for the nearby Card Store…",s.report);
  List<CompletableFuture<CardStoreScreenHandler.CartEntryData>> requests=s.missingLines.stream().map(line->resolveStoreLine(p,line)).toList();
  CompletableFuture.allOf(requests.toArray(CompletableFuture[]::new)).whenComplete((ignored,error)->p.level().getServer().execute(()->{
   if(!valid(p,s)||s.revision!=revision)return;s.busy=false;
   List<CardStoreScreenHandler.CartEntryData> cart=requests.stream().map(r->r.getNow(null)).filter(Objects::nonNull).toList();
   if(cart.isEmpty()){reply(p,s,"The Card Store could not resolve any missing cards.",s.report);return;}
   store.setSelectedGame(p.getUUID(),TcgGameRegistry.MTG);
   store.setSavedCart(p.getUUID(),cart);
   reply(p,s,"Sent "+cart.size()+" missing card lines to the nearby Card Store.",s.report);
   p.openMenu(store);
  }));
 }
 static void editCounter(ServerPlayer p,Session s,String name,int value){if(name.isBlank()||name.length()>48||name.chars().anyMatch(c->Character.isISOControl(c))||value<0||value>1000000)return;CardDisplayEntity c=counter(p,s);if(c==null)return;var map=CardCounterNbt.readCounterMap(c.getDisplayCardStack(s.cardId));if(!map.containsKey(name)&&map.size()>=16){reply(p,s,"Maximum 16 counter types per card.","");return;}c.mutateDisplayCardStack(s.cardId,stack->{if(value==0)CardCounterNbt.removeCounter(stack,name);else CardCounterNbt.setCounter(stack,name,value);});reply(p,s,"Counters saved.","");}
}
