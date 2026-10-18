package dev.casz.caszualmtg;

import com.spider.mtgcard.deckbox.DeckboxBlockEntity;
import com.spider.mtgcard.deckcontrol.DeckControlBlockEntity;
import com.spider.mtgcard.graveyard.GraveyardBlockEntity;
import com.spider.mtgcard.util.TcgCardMeta;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.entity.animal.golem.IronGolem;
import net.minecraft.world.item.ItemStack;

import java.util.*;

/** Server-authoritative, conservative subset of a Commander turn.
 * Physical MTGCard cards move exactly once. Unsupported spells stay in hand.
 * This does not implement priority, the stack or replacement effects. */
public final class CommanderBattleActions {
 private CommanderBattleActions(){}
 private static void announce(IronGolem bot,TabletopBlockEntity table,String id,String kind){
  if(table.getLevel() instanceof ServerLevel level)
   TabletopTargets.mark(level,bot.getUUID(),table.getBlockPos(),table.seatName(),
    "",table.getBlockPos(),id,kind);
 }
 public static final String READY="caszual_mtg_ai_ready_";
 public static boolean mine(IronGolem bot,TabletopBlockEntity.PlayedCard c){
  return bot.getUUID().toString().equals(c.owner());
 }
 public static List<TabletopBlockEntity.PlayedCard> owned(IronGolem bot,TabletopBlockEntity table){
  return table.cards().stream().filter(c->mine(bot,c)).toList();
 }
 public static Optional<CommanderSimpleCards.Traits> traits(ItemStack card){
  var meta=TcgCardMeta.read(card);
  return CommanderSimpleCards.creature(meta.typeLine(),meta.oracleText(),meta.power(),meta.toughness());
 }
 public static boolean ready(IronGolem bot,TabletopBlockEntity.PlayedCard c){
  return bot.entityTags().contains(READY+c.id());
 }
 public static void untapAndMarkReady(IronGolem bot,TabletopBlockEntity table){
  for(var c:owned(bot,table)){
   if(traits(c.stack()).isPresent())bot.addTag(READY+c.id());
   if(c.tapped())table.replace(c.tapped(false));
  }
 }
 private static boolean usableLand(ItemStack card){
  var meta=TcgCardMeta.read(card);
  if(!meta.typeLine().toLowerCase(Locale.ROOT).contains("land")||
     meta.typeLine().toLowerCase(Locale.ROOT).contains("creature"))return false;
  // The first prototype can only enter lands without replacement/triggered
  // abilities. Complex land-specific costs are not bypassed.
  return CommanderMana.production(meta.name(),meta.typeLine(),meta.oracleText())>0;
 }
 public static boolean playLand(IronGolem bot,TabletopBlockEntity table,HandBlockEntity hand){
  if(table.cards().size()>=TabletopBlockEntity.MAX_CARDS)return false;
  List<ItemStack> cards=hand.visibleCards();
  for(int index=0;index<cards.size();index++){
   if(!usableLand(cards.get(index)))continue;
   ItemStack moved=hand.removeVisibleIndex(index);
   if(moved.isEmpty())return false;
   if(table.add(new TabletopBlockEntity.PlayedCard(UUID.randomUUID().toString(),
     bot.getUUID().toString(),moved,200+(table.cards().size()%6)*110,800,false,false)))
    return true;
   hand.addCard(moved);return false;
  }
  return false;
 }
 public static List<CommanderMana.Source> mana(IronGolem bot,TabletopBlockEntity table){
  List<CommanderMana.Source> sources=new ArrayList<>();
  for(var played:owned(bot,table)){
   if(played.tapped())continue;
   var meta=TcgCardMeta.read(played.stack());
   int mask=CommanderMana.production(meta.name(),meta.typeLine(),meta.oracleText());
   if(mask>0)sources.add(new CommanderMana.Source(played.id(),mask));
  }
  return sources;
 }
 private static void tapPaid(TabletopBlockEntity table,List<String> manaIds){
  for(String id:manaIds){
   var played=table.find(id);
   if(played!=null&&!played.tapped())table.replace(played.tapped(true));
  }
 }
 /** 0..N creatures can be deployed in the main phase with real mana.
  * The cards supported here have no triggered or activated abilities. */
 public static int castHand(IronGolem bot,TabletopBlockEntity table,HandBlockEntity hand){
  int cast=0;
  while(cast<20&&table.cards().size()<TabletopBlockEntity.MAX_CARDS){
   var available=mana(bot,table);
   List<ItemStack> cards=hand.visibleCards();
   int best=-1,score=-1;
   List<String> payment=List.of();
   for(int i=0;i<cards.size();i++){
    var meta=TcgCardMeta.read(cards.get(i));
    if(traits(cards.get(i)).isEmpty())continue;
    var cost=CommanderMana.parse(meta.manaCost());
    if(cost.isEmpty())continue;
    var plan=CommanderMana.pay(cost.get(),available);
    if(plan.isEmpty())continue;
    int value=cost.get().total()*10+Math.max(0,meta.manaValue());
    if(value>score){score=value;best=i;payment=plan.get();}
   }
   if(best<0)break;
   ItemStack selected=hand.removeVisibleIndex(best);
   if(selected.isEmpty())break;
   var played=new TabletopBlockEntity.PlayedCard(UUID.randomUUID().toString(),
      bot.getUUID().toString(),selected,220+(table.cards().size()%6)*110,250,false,false);
   if(!table.add(played)){
    hand.addCard(selected);break;
   }
   tapPaid(table,payment);
   announce(bot,table,played.id(),"cast");
   cast++;
  }
  return cast;
 }
 /** Commander spell is cast with an additional {2} per previous command-zone
  * cast. Reject any commander abilities not supported by the tiny interpreter. */
 public static boolean castCommander(IronGolem bot,TabletopBlockEntity table,DeckboxBlockEntity box){
  if(table.cards().size()>=TabletopBlockEntity.MAX_CARDS)return false;
  ItemStack stack=box.getStack(DeckboxBlockEntity.SECOND_SIDE_SLOT);
  if(stack.isEmpty()||traits(stack).isEmpty())return false;
  var meta=TcgCardMeta.read(stack);
  var cost=CommanderMana.parse(meta.manaCost());
  if(cost.isEmpty())return false;
  var actualCost=cost.get().taxed(table.aiCommanderCasts()*2);
  var payment=CommanderMana.pay(actualCost,mana(bot,table));
  if(payment.isEmpty())return false;
  ItemStack one=stack.copyWithCount(1);
  if(!table.add(new TabletopBlockEntity.PlayedCard("commander:"+UUID.randomUUID(),
       bot.getUUID().toString(),one,350,300,false,false)))return false;
  box.setStack(DeckboxBlockEntity.SECOND_SIDE_SLOT,ItemStack.EMPTY);
  box.sync();
  table.rememberCommander(one);
  table.aiCommanderCast();
  tapPaid(table,payment.get());
  // The real CardStack is on the table before the target marker is broadcast.
  announce(bot,table,table.cards().getLast().id(),"cast");
  return true;
 }
 /** Find the same physically adjacent Graveyard that MTGCard's Deck Control uses. */
 public static GraveyardBlockEntity graveyard(ServerLevel world,DeckControlBlockEntity deck){
  for(Direction direction:Direction.values()){
   BlockPos pos=deck.getBlockPos().relative(direction);
   if(world.hasChunkAt(pos)&&world.getBlockEntity(pos) instanceof GraveyardBlockEntity grave)
    return grave;
  }
  return null;
 }
 /** Keep max hand size. If storage is missing/full, reject ending the turn
  * rather than deleting cards. Hand remains private to the bot. */
 public static boolean cleanup(ServerLevel world,HandBlockEntity hand,DeckControlBlockEntity deck){
  if(hand.cardCount()<=7)return true;
  GraveyardBlockEntity grave=graveyard(world,deck);
  if(grave==null)return false;
  int missing=hand.cardCount()-7;
  List<Integer> slots=new ArrayList<>();
  for(int i=0;i<100&&slots.size()<missing;i++)if(grave.getStack(i).isEmpty())slots.add(i);
  if(slots.size()<missing)return false;
  for(int slot:slots){
   List<ItemStack> cards=hand.visibleCards();
   if(cards.size()<=7)break;
   // Discard uncastable cards before lands / supported creatures.
   int choice=0,highest=Integer.MIN_VALUE;
   for(int i=0;i<cards.size();i++){
    ItemStack stack=cards.get(i);
    var meta=TcgCardMeta.read(stack);
    int value=(traits(stack).isEmpty()&&!usableLand(stack)?500:0)+Math.max(0,meta.manaValue());
    if(value>highest){highest=value;choice=i;}
   }
   ItemStack discarded=hand.removeVisibleIndex(choice);
   if(discarded.isEmpty())return false;
   grave.setStack(slot,discarded);
  }
  return true;
 }
}
