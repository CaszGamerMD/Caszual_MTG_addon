package dev.casz.caszualmtg;

import net.minecraft.core.BlockPos;
import net.minecraft.network.RegistryFriendlyByteBuf;
import net.minecraft.network.codec.StreamCodec;
import net.minecraft.network.protocol.common.custom.CustomPacketPayload;
import net.minecraft.world.item.ItemStack;
import java.util.*;

public final class TabletopWire {
 /** Standard card IDs are UUIDs (36 chars); commanders include a "commander:"
  * prefix (46 chars). Old worlds already contain those longer IDs, so the
  * network format must handle them without truncation or remapping. */
 public static final int MAX_CARD_ID_LENGTH=64;
 public record Request(BlockPos pos,String action,String ref,BlockPos target,int x,int y,int amount) implements CustomPacketPayload {
  public static final Type<Request> TYPE=new Type<>(CaszualMtg.id("tabletop_request"));
  public static final StreamCodec<RegistryFriendlyByteBuf,Request> CODEC=StreamCodec.of(
   (b,p)->{b.writeBlockPos(p.pos);b.writeUtf(p.action,24);b.writeUtf(p.ref,256);b.writeBlockPos(p.target);b.writeInt(p.x);b.writeInt(p.y);b.writeVarInt(p.amount);},
   b->new Request(b.readBlockPos(),b.readUtf(24),b.readUtf(256),b.readBlockPos(),b.readInt(),b.readInt(),b.readVarInt()));
  public Type<Request> type(){return TYPE;}
 }
 /** Public seat metadata only: never exposes a private Hand's card contents. */
 public record Tile(BlockPos pos,String owner,int color,int life,boolean hasLife,
                    boolean active,int cardScale,int handCount,int libraryCount,Map<String,Integer> counters) {}
 public record Card(BlockPos pos,String id,String owner,ItemStack stack,int x,int y,boolean tapped,boolean hidden) {}
 public record ZoneCard(int slot,ItemStack stack) {}
 public record TokenResult(String key,ItemStack stack) {}
 public record ShownHand(BlockPos seat,String owner,List<ItemStack> cards) {}
 public record PublicReveal(BlockPos seat,String owner,List<ItemStack> cards) {}
 /** Public graveyard/exile contents: never includes a player's private deck or hand. */
 public record PublicZone(BlockPos seat,List<ZoneCard> grave,List<ZoneCard> exile) {}
 public record TargetMark(BlockPos fromSeat,String fromName,String sourceCard,BlockPos targetSeat,String targetCard,String kind) {}
 public record Reply(BlockPos pos,String message,BlockPos seat,List<Tile> tiles,List<Card> cards,List<ItemStack> hand,int libraryCount,List<ZoneCard> grave,List<ZoneCard> exile,List<ItemStack> scry,List<ItemStack> reveal,ItemStack commander,List<ItemStack> tray,List<TokenResult> tokenResults,int tokenPage,boolean tokenMore,boolean ownHandRevealed,List<ShownHand> shownHands,List<PublicReveal> publicReveals,List<PublicZone> publicZones,List<TargetMark> targets) implements CustomPacketPayload {
  public static final Type<Reply> TYPE=new Type<>(CaszualMtg.id("tabletop_reply"));
  public static final StreamCodec<RegistryFriendlyByteBuf,Reply> CODEC=StreamCodec.of((b,p)->{
   b.writeBlockPos(p.pos);b.writeUtf(p.message,512);b.writeBlockPos(p.seat);
   b.writeVarInt(p.tiles.size());for(Tile t:p.tiles){b.writeBlockPos(t.pos);b.writeUtf(t.owner,64);b.writeInt(t.color);b.writeInt(t.life);b.writeBoolean(t.hasLife);b.writeBoolean(t.active);b.writeVarInt(t.cardScale);
     b.writeVarInt(t.handCount);b.writeVarInt(t.libraryCount);
     b.writeVarInt(t.counters.size());
     for(var counter:t.counters.entrySet()){b.writeUtf(counter.getKey(),40);b.writeInt(counter.getValue());}
    }
   b.writeVarInt(p.cards.size());for(Card c:p.cards){
    b.writeBlockPos(c.pos);b.writeUtf(c.id,MAX_CARD_ID_LENGTH);b.writeUtf(c.owner,40);
    ItemStack.OPTIONAL_STREAM_CODEC.encode(b,c.stack);
    b.writeVarInt(c.x);b.writeVarInt(c.y);b.writeBoolean(c.tapped);b.writeBoolean(c.hidden);
   }
   b.writeVarInt(p.hand.size());for(ItemStack s:p.hand)ItemStack.OPTIONAL_STREAM_CODEC.encode(b,s);
   b.writeVarInt(p.libraryCount);
   for(List<ZoneCard> zone:List.of(p.grave,p.exile)){
    b.writeVarInt(zone.size());for(ZoneCard c:zone){b.writeVarInt(c.slot);ItemStack.OPTIONAL_STREAM_CODEC.encode(b,c.stack);}
   }
   b.writeVarInt(p.scry.size());for(ItemStack s:p.scry)ItemStack.OPTIONAL_STREAM_CODEC.encode(b,s);
   b.writeVarInt(p.reveal.size());for(ItemStack s:p.reveal)ItemStack.OPTIONAL_STREAM_CODEC.encode(b,s);
   ItemStack.OPTIONAL_STREAM_CODEC.encode(b,p.commander);
   b.writeVarInt(p.tray.size());for(ItemStack t:p.tray)ItemStack.OPTIONAL_STREAM_CODEC.encode(b,t);
   b.writeVarInt(p.tokenResults.size());for(TokenResult t:p.tokenResults){b.writeUtf(t.key,512);ItemStack.OPTIONAL_STREAM_CODEC.encode(b,t.stack);}
   b.writeVarInt(p.tokenPage);b.writeBoolean(p.tokenMore);
   b.writeBoolean(p.ownHandRevealed);
   b.writeVarInt(p.shownHands.size());
   for(ShownHand shown:p.shownHands){
    b.writeBlockPos(shown.seat);b.writeUtf(shown.owner,64);
    b.writeVarInt(shown.cards.size());
    for(ItemStack card:shown.cards)ItemStack.OPTIONAL_STREAM_CODEC.encode(b,card);
   }
   b.writeVarInt(p.publicReveals.size());
   for(PublicReveal reveal:p.publicReveals){
    b.writeBlockPos(reveal.seat);b.writeUtf(reveal.owner,64);
    b.writeVarInt(reveal.cards.size());
    for(ItemStack card:reveal.cards)ItemStack.OPTIONAL_STREAM_CODEC.encode(b,card);
   }
   b.writeVarInt(p.publicZones.size());
    for(PublicZone z:p.publicZones){
     b.writeBlockPos(z.seat);
     for(List<ZoneCard> cards:List.of(z.grave,z.exile)){
      b.writeVarInt(cards.size());
      for(ZoneCard card:cards){b.writeVarInt(card.slot);ItemStack.OPTIONAL_STREAM_CODEC.encode(b,card.stack);}
     }
    }
    b.writeVarInt(p.targets.size());
   for(TargetMark target:p.targets){
    b.writeBlockPos(target.fromSeat);b.writeUtf(target.fromName,64);
    b.writeUtf(target.sourceCard,MAX_CARD_ID_LENGTH);
    b.writeBlockPos(target.targetSeat);b.writeUtf(target.targetCard,MAX_CARD_ID_LENGTH);
    b.writeUtf(target.kind,16);
   }
  },b->{
   BlockPos pos=b.readBlockPos();String message=b.readUtf(512);BlockPos seat=b.readBlockPos();
   int n=b.readVarInt();if(n<0||n>32)throw new IllegalArgumentException("Table too large");
   List<Tile> tiles=new ArrayList<>();
    for(int i=0;i<n;i++){
     BlockPos tilePos=b.readBlockPos();String owner=b.readUtf(64);int color=b.readInt(),life=b.readInt();
     boolean hasLife=b.readBoolean(),active=b.readBoolean();int scale=b.readVarInt();
     int handCount=b.readVarInt();if(handCount< -1||handCount>100)throw new IllegalArgumentException("Invalid hand count");
     int libraryCount=b.readVarInt();if(libraryCount< -1||libraryCount>1000)throw new IllegalArgumentException("Invalid library count");
     int counterCount=b.readVarInt();if(counterCount<0||counterCount>32)throw new IllegalArgumentException("Too many life counters");
     Map<String,Integer> counters=new LinkedHashMap<>();
     for(int j=0;j<counterCount;j++)counters.put(b.readUtf(40),b.readInt());
     tiles.add(new Tile(tilePos,owner,color,life,hasLife,active,scale,handCount,libraryCount,Map.copyOf(counters)));
    }
   n=b.readVarInt();if(n<0||n>3072)throw new IllegalArgumentException("Too many played cards");
   List<Card> cards=new ArrayList<>();for(int i=0;i<n;i++)cards.add(new Card(b.readBlockPos(),b.readUtf(MAX_CARD_ID_LENGTH),b.readUtf(40),ItemStack.OPTIONAL_STREAM_CODEC.decode(b),b.readVarInt(),b.readVarInt(),b.readBoolean(),b.readBoolean()));
   n=b.readVarInt();if(n<0||n>100)throw new IllegalArgumentException("Too many hand cards");
   List<ItemStack> hand=new ArrayList<>();for(int i=0;i<n;i++)hand.add(ItemStack.OPTIONAL_STREAM_CODEC.decode(b));
   int library=b.readVarInt();
   List<List<ZoneCard>> zones=new ArrayList<>();
   for(int j=0;j<2;j++){
    n=b.readVarInt();if(n<0||n>100)throw new IllegalArgumentException("Too many zone cards");
    List<ZoneCard> zone=new ArrayList<>();for(int i=0;i<n;i++)zone.add(new ZoneCard(b.readVarInt(),ItemStack.OPTIONAL_STREAM_CODEC.decode(b)));zones.add(zone);
   }
   n=b.readVarInt();if(n<0||n>20)throw new IllegalArgumentException("Too many scry cards");
   List<ItemStack> scry=new ArrayList<>();for(int i=0;i<n;i++)scry.add(ItemStack.OPTIONAL_STREAM_CODEC.decode(b));
   n=b.readVarInt();if(n<0||n>20)throw new IllegalArgumentException("Too many revealed cards");
   List<ItemStack> reveal=new ArrayList<>();for(int i=0;i<n;i++)reveal.add(ItemStack.OPTIONAL_STREAM_CODEC.decode(b));
   ItemStack commander=ItemStack.OPTIONAL_STREAM_CODEC.decode(b);
   n=b.readVarInt();if(n<0||n>32)throw new IllegalArgumentException("Token tray too large");
   List<ItemStack> tray=new ArrayList<>();for(int i=0;i<n;i++)tray.add(ItemStack.OPTIONAL_STREAM_CODEC.decode(b));
   n=b.readVarInt();if(n<0||n>12)throw new IllegalArgumentException("Token search page too large");
   List<TokenResult> tokenResults=new ArrayList<>();for(int i=0;i<n;i++)tokenResults.add(new TokenResult(b.readUtf(512),ItemStack.OPTIONAL_STREAM_CODEC.decode(b)));
   int tokenPage=b.readVarInt();if(tokenPage<0||tokenPage>50)throw new IllegalArgumentException("Invalid token page");
   boolean tokenMore=b.readBoolean();
   boolean ownHandRevealed=b.readBoolean();
   n=b.readVarInt();if(n<0||n>32)throw new IllegalArgumentException("Too many public hands");
   List<ShownHand> shownHands=new ArrayList<>();
   for(int i=0;i<n;i++){
    BlockPos shownSeat=b.readBlockPos();String owner=b.readUtf(64);
    int count=b.readVarInt();if(count<0||count>100)throw new IllegalArgumentException("Too many public hand cards");
    List<ItemStack> publicCards=new ArrayList<>();
    for(int j=0;j<count;j++)publicCards.add(ItemStack.OPTIONAL_STREAM_CODEC.decode(b));
    shownHands.add(new ShownHand(shownSeat,owner,List.copyOf(publicCards)));
   }
   n=b.readVarInt();if(n<0||n>32)throw new IllegalArgumentException("Too many revealed decks");
   List<PublicReveal> publicReveals=new ArrayList<>();
   for(int i=0;i<n;i++){
    BlockPos revealSeat=b.readBlockPos();String owner=b.readUtf(64);
    int count=b.readVarInt();if(count<0||count>20)throw new IllegalArgumentException("Too many publicly revealed cards");
    List<ItemStack> revealed=new ArrayList<>();
    for(int j=0;j<count;j++)revealed.add(ItemStack.OPTIONAL_STREAM_CODEC.decode(b));
    publicReveals.add(new PublicReveal(revealSeat,owner,List.copyOf(revealed)));
   }
   n=b.readVarInt();if(n<0||n>32)throw new IllegalArgumentException("Too many public zones");
    List<PublicZone> publicZones=new ArrayList<>();
    for(int i=0;i<n;i++){
     BlockPos seatPos=b.readBlockPos();
     List<List<ZoneCard>> zonesPublic=new ArrayList<>();
     for(int z=0;z<2;z++){
      int count=b.readVarInt();if(count<0||count>100)throw new IllegalArgumentException("Too many public zone cards");
      List<ZoneCard> publicCards=new ArrayList<>();
      for(int j=0;j<count;j++)publicCards.add(new ZoneCard(b.readVarInt(),ItemStack.OPTIONAL_STREAM_CODEC.decode(b)));
      zonesPublic.add(List.copyOf(publicCards));
     }
     publicZones.add(new PublicZone(seatPos,zonesPublic.get(0),zonesPublic.get(1)));
    }
    n=b.readVarInt();if(n<0||n>64)throw new IllegalArgumentException("Too many target markers");
   List<TargetMark> targets=new ArrayList<>();
   for(int i=0;i<n;i++)targets.add(new TargetMark(b.readBlockPos(),b.readUtf(64),
      b.readUtf(MAX_CARD_ID_LENGTH),b.readBlockPos(),b.readUtf(MAX_CARD_ID_LENGTH),b.readUtf(16)));
   return new Reply(pos,message,seat,List.copyOf(tiles),List.copyOf(cards),List.copyOf(hand),library,List.copyOf(zones.get(0)),List.copyOf(zones.get(1)),List.copyOf(scry),List.copyOf(reveal),commander,List.copyOf(tray),List.copyOf(tokenResults),tokenPage,tokenMore,ownHandRevealed,List.copyOf(shownHands),List.copyOf(publicReveals),List.copyOf(publicZones),List.copyOf(targets));
  });
  public Type<Reply> type(){return TYPE;}
 }
 private TabletopWire(){}
}
