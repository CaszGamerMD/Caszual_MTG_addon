"""Keep the experimental targeting/token UI wired to server validation."""
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
JAVA=ROOT / "src/main/java/dev/casz/caszualmtg"
def read(file): return (JAVA / file).read_text(encoding="utf-8")

class GolemTabletopUiTests(unittest.TestCase):
    def test_both_token_filters_are_sent_to_catalogue(self):
        screen=read("TabletopScreen.java")
        server=read("TabletopLogic.java")
        self.assertIn('tokenOracleText',screen)
        self.assertIn('tokenPtText',screen)
        self.assertIn('send("token_query",tokenText+',screen)
        self.assertIn('tokenOracleText+',screen)
        self.assertIn('tokenPtText,data.seat()',screen)
        self.assertIn('Catalogue.stats(stats)',server)
        self.assertIn('Catalogue.search(1,name,0,page/5,oracle,stats)',server)
        self.assertIn('Catalogue.matchesToken(token,oracle,stats)',server)
        self.assertIn('query.oracle(),query.stats()',server)

    def test_token_art_is_visible_without_alt(self):
        screen=read("TabletopScreen.java")
        self.assertIn('drawArt(g,token,px+7,yy+2,24,34)',screen)
        self.assertIn('drawArt(g,token,px+pw/2+6,yy+2,24,34)',screen)
        self.assertIn('if(tokenTrayOpen&&inTokenPanel(mx,my)',screen)
        self.assertIn('tokenVisibleRows()',screen)
        self.assertGreater(screen.count('void render('),0)
        self.assertGreater(screen.count('void searchTokens('),0)
        self.assertGreater(len(screen.splitlines()),750)

    def test_targets_validate_owner_and_connected_table(self):
        logic=read("TabletopLogic.java")
        targets=read("TabletopTargets.java")
        wire=read("TabletopWire.java")
        screen=read("TabletopScreen.java")
        self.assertIn('case "target_card", "target_player"',logic)
        self.assertIn('!owned(player,source)',logic)
        self.assertIn('destination.seatOwner()==null',logic)
        self.assertIn('TabletopTargets.visible(server,c.tiles)',logic)
        self.assertIn('LinkedHashMap<UUID,Mark>',targets)
        self.assertIn('TTL_TICKS=20*20L',targets)
        self.assertIn('List<TargetMark> targets',wire)
        self.assertIn('mark.targetSeat().equals(view)',screen)
        self.assertIn('mark.sourceCard().equals(c.id())',screen)

    def test_blocking_requires_defender_and_preserves_storage(self):
        combat=read("CommanderCombat.java")
        table=read("TabletopBlockEntity.java")
        server=read("TabletopLogic.java")
        self.assertIn('aiAttack()',table)
        self.assertIn('out.putString("AiAttacker"',table)
        self.assertIn('in.getStringOr("AiAttacker"',table)
        self.assertIn('Only the defending player can choose blockers',combat)
        self.assertIn('CommanderSimpleCards.canBlock',combat)
        self.assertIn('Golem\'s Graveyard is missing or full.',combat)
        self.assertIn('blockGrave=CommanderBattleActions.graveyard',combat)
        self.assertIn('case "ai_damage", "ai_block"',server)

    def test_bot_marks_real_creature_casts(self):
        battle=read("CommanderBattleActions.java")
        self.assertIn('TabletopTargets.mark(',battle)
        self.assertIn('announce(bot,table,played.id(),"cast")',battle)
        self.assertIn('announce(bot,table,table.cards().getLast().id(),"cast")',battle)

if __name__ == "__main__": unittest.main()
