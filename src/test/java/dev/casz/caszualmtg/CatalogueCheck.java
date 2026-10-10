package dev.casz.caszualmtg;
public final class CatalogueCheck {
 static void check(boolean value,String name){if(!value)throw new AssertionError(name);}
 public static void main(String[] args){
  check(Catalogue.acceptsLand(16,16,true,16),"green land eligible");check(!Catalogue.acceptsLand(17,17,true,16),"GW dual excluded for green alone");check(Catalogue.acceptsLand(17,17,true,17),"GW dual eligible when both selected");check(!Catalogue.acceptsLand(17,16,true,16),"produced off-color mana excluded");check(!Catalogue.acceptsLand(16,17,true,16),"off-color identity excluded");check(Catalogue.acceptsLand(48,16,true,16),"colorless production allowed alongside selected green");check(Catalogue.acceptsLand(32,0,true,32),"pure colorless selected");check(!Catalogue.acceptsLand(33,0,true,32),"colored production excluded from colorless-only selection");check(!Catalogue.acceptsLand(16,16,false,0),"nonlegal lands excluded from All");check(Catalogue.acceptsLand(31,31,true,0),"All allows every legal color");
  String green=Catalogue.query(0,"Forest",16);check(green.contains("legal:commander")&&green.contains("id<=G")&&green.contains("-produces:W")&&!green.contains("-produces:G"),"commander query uses allowed colors");check(Catalogue.query(0,"",64).contains("t:basic"),"basic land tab query");check(Catalogue.query(0,"",128).contains("-t:basic"),"nonbasic land tab query");check(Catalogue.query(0,"",256).contains("is:fullart"),"full art land query");String token=Catalogue.query(1,"Soldier",0,"Flying","1/1");check(token.contains("o:\"Flying\"")&&token.contains("pow=1 tou=1"),"combined optional token query");check(Catalogue.stats(" 01 / 02 ")[0].equals("1"),"PT normalized");boolean rejected=false;try{Catalogue.stats("2");}catch(IllegalArgumentException e){rejected=true;}check(rejected,"invalid PT rejected");
  // A basic land has hundreds of distinct artworks but only one Oracle identity.
  // 'unique=cards' hid all but one illustration; 'unique=art' must be used.
  check(Catalogue.searchUniqueness(0,0).equals("cards"),"default catalogue remains unique cards");
  check(Catalogue.searchUniqueness(0,64).equals("art"),"Basic lands return unique artworks");
  check(Catalogue.searchUniqueness(0,320).equals("art"),"Basic + Full Art returns unique artworks");
  check(Catalogue.searchUniqueness(0,256).equals("art"),"Full Art lands return unique artworks");
  check(Catalogue.searchUniqueness(0,128).equals("cards"),"Nonbasic default still unique cards");
  check(Catalogue.searchUniqueness(1,320).equals("cards"),"Token catalogue keeps previous uniqueness");
  check(Catalogue.query(0,"",320).contains("t:basic is:fullart"),"Basic + Full Art query keeps both filters");
  String fullArtForest=Catalogue.artworkQuery(0,"Forest",true);
  check(fullArtForest.contains("is:fullart")&&fullArtForest.contains("!\"Forest\""),"Artwork picker keeps Full Art and exact-name Forest");
  check(!fullArtForest.contains("oracleid:"),"Do not use unsupported oracleid Scryfall search field");
  check(Catalogue.artworkQuery(0,"Snow-Covered Island",true).contains("!\"Snow-Covered Island\""),"Exact-name query handles snow basics");
  check(!Catalogue.artworkQuery(0,"Forest",false).contains("is:fullart"),"Unfiltered artwork chooser still permits ordinary art");
  check(!Catalogue.artworkQuery(1,"Soldier",true).contains("is:fullart"),"Token artwork picker unaffected");
  check(CardBrowser.visible(412,302,true)==8,"community grid shows two rows of four");check(CardBrowser.visible(434,334,true)==8,"free catalogue grid shows two rows of four");check(CardBrowser.hit(320,10,0,0,412,302,0,40,true)==3,"fourth grid card hit");check(CardBrowser.hit(10,160,0,0,412,302,0,40,true)==4,"next grid row hit");check(CardBrowser.clampScroll(999,10,412,302,true)==4,"last partial grid row remains reachable");check(CardBrowser.hit(320,160,0,0,412,302,4,10,true)==-1,"empty grid cell cannot select card");
  System.out.println("PASS: unique basic/full-art land illustrations, persistent artwork filters, strict mana filters, token queries and grid checks");
 }
}
