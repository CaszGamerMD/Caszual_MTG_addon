package dev.casz.caszualmtg;

public final class ArchidektImportCheck {
 static void check(boolean condition,String label){if(!condition)throw new AssertionError(label);}
 public static void main(String[] args){
  check(ArchidektImport.deckId("https://archidekt.com/decks/27061166/day_one_dino")==27061166L,"deck URL ID");
  String json="""
   {
    "name":"Main Only Test",
    "categories":[
     {"name":"Commander","includedInDeck":true},
     {"name":"Creature","includedInDeck":true},
     {"name":"Sideboard","includedInDeck":false},
     {"name":"Maybeboard","includedInDeck":false}
    ],
    "cards":[
     {"quantity":1,"categories":["Commander"],"card":{"oracleCard":{"name":"Gishath, Sun's Avatar"},"collectorNumber":"222","edition":{"editioncode":"LCI"}}},
     {"quantity":2,"categories":["Creature"],"card":{"oracleCard":{"name":"Kinjalli's Caller"},"collectorNumber":"18","edition":{"editioncode":"XLN"}}},
     {"quantity":1,"categories":["Sideboard"],"card":{"oracleCard":{"name":"Side Card"},"collectorNumber":"1","edition":{"editioncode":"TST"}}},
     {"quantity":1,"categories":["Maybeboard"],"card":{"oracleCard":{"name":"Maybe Card"},"collectorNumber":"2","edition":{"editioncode":"TST"}}},
     {"quantity":1,"categories":["Creature","Maybeboard"],"card":{"oracleCard":{"name":"Mixed Maybe"},"collectorNumber":"3","edition":{"editioncode":"TST"}}}
    ]
   }
   """;
  var result=ArchidektImport.parse(json);
  check(result.entries()==2&&result.cards()==3,"only main deck quantities included");
  check(result.text().contains("1 Gishath, Sun's Avatar (LCI) 222"),"commander retained with printing");
  check(result.text().contains("2 Kinjalli's Caller (XLN) 18"),"main card retained with printing");
  check(!result.text().contains("Side Card")&&!result.text().contains("Maybe Card")&&!result.text().contains("Mixed Maybe"),"sideboard and maybeboard excluded");
  boolean bad=false;try{ArchidektImport.deckId("https://example.com/decks/27061166/nope");}catch(IllegalArgumentException e){bad=true;}check(bad,"foreign URL rejected");
  check(ArchidektImport.deckId("https://www.archidekt.com/decks/27061166/day_one_dino?foo=bar#section")==27061166L,"www/query/fragment URL accepted");
  System.out.println("PASS: Archidekt main-deck-only importer");
 }
}
