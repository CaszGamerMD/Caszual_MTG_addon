"""Regression checks for the offline match-theater viewer and compact public replay."""
import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import sys
HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import simulator as s


class MatchTheaterChecks(unittest.TestCase):
    def test_public_stack_priority_exile_mana_survive_replay_packing(self):
        card = dict(id="c-1", name="Unknown scout", kind="creature",
                    power=2, toughness=3, traits="2;3;flying", tapped=True, fresh=False,
                    counters=1, isCreature=True, attachedTo=None, wardCosts=[])
        p0 = dict(seat=0, life=38, handCount=3, libraryCount=42, manaPool=[0, 1, 0, 0, 0, 2],
                  battlefield=[card], graveyard=[dict(id="g-1",name="Lost spell")],
                  exile=[dict(id="x-1",name="Exiled spell")],commanderInZone=True,
                  commanderDamage={"enemy":4})
        p1 = dict(seat=1, life=31, handCount=5, libraryCount=47, manaPool=[0]*6,
                  battlefield=[], graveyard=[],exile=[],commanderInZone=False,commanderDamage={})
        state=dict(active=0,turn=4,phase="main",priority=1,
                   stack=[dict(id=3,controller=0,label="Unknown scout"),
                          dict(id=4,controller=1,label="Responding spell")],
                   players=[p0,p1])
        report=dict(schemaVersion=1,kind="turn-replay",events=[
            dict(index=0,turn=4,phase="main",actor=0,kind="stack_push",
                 message="A spell goes on the stack.",details={},state=state)])
        packed=s.pack_replay(report)
        self.assertEqual(packed["packedReplay"],1)
        self.assertEqual(len(packed["compactEvents"]),1)
        event=packed["compactEvents"][0]
        self.assertEqual(event[7][4],state["stack"])
        self.assertEqual(event[7][5],1)
        self.assertEqual(event[7][3][0][8],p0["manaPool"])
        self.assertEqual(len(event[7][3][0][7]),1)
        self.assertEqual(packed["cardCatalog"][event[7][3][0][7][0]]["name"],"Exiled spell")
        self.assertEqual(packed["cardCatalog"][event[7][3][0][3][0][0]]["name"],"Unknown scout")
        self.assertTrue(event[7][3][0][3][0][1])
        self.assertEqual(event[7][3][0][3][0][7],1)
        # Hidden hand identities and library order must not be serialized.
        self.assertNotIn("hand", event[7][3][0])
        self.assertNotIn("handCards", json.dumps(packed))
        self.assertEqual(s.pack_replay(report),packed)

    def test_spectator_hand_snapshots_preserve_ids_without_entering_public_state(self):
        from types import SimpleNamespace
        simulator=s.Simulator.__new__(s.Simulator)
        simulator.events=[];simulator.turn=2;simulator.active=0
        simulator.phase="main";simulator.diagnostic=True
        simulator.players=[
            SimpleNamespace(hand=[s.Card("hand-a","Thorn Weaver","creature")]),
            SimpleNamespace(hand=[s.Card("hand-b","Misty Tunnel","land")])]
        simulator.invariant=lambda:None
        simulator.state=lambda:dict(active=0,turn=2,phase="main",stack=[],priority=0,
              players=[dict(seat=k,life=40,handCount=1,libraryCount=3,
                            battlefield=[],graveyard=[],exile=[]) for k in (0,1)])
        simulator.log("draw","Draws",actor=0)
        event=simulator.events[0]
        self.assertNotIn("hand-a",str(event["state"]))
        self.assertEqual(event["spectatorHands"][0][0]["name"],"Thorn Weaver")
        packed=s.pack_replay(dict(schemaVersion=1,kind="turn-replay",events=[event]))
        self.assertEqual(packed["cardCatalog"][packed["compactEvents"][0][8][1][0]]["name"],"Misty Tunnel")
        self.assertEqual(len(packed["compactEvents"][0][8]),2)

    def test_scryfall_artwork_is_paced_and_supports_multiple_faces(self):
        html=(HERE/"viewer.html").read_text(encoding="utf-8")
        self.assertIn("api.scryfall.com/cards/named?exact=",html)
        self.assertIn("scryfallDelay=600",html)
        self.assertIn("card.card_faces",html)
        self.assertIn("function trustedImage(url)",html)
        self.assertIn('id="toggleArt"',html)
        self.assertIn('id="toggleHands"',html)
        self.assertIn("spectatorHands",html)
        self.assertIn("Face ",html)
        self.assertNotIn("innerHTML",html)

    def test_original_viewer_uses_only_local_css_and_javascript(self):
        html=(HERE/"viewer.html").read_text(encoding="utf-8")
        self.assertEqual(html.count("/*EMBEDDED_REPLAY*/null"),1)
        self.assertEqual(html.count("<script>"),1)
        self.assertNotRegex(html,r"<script[^>]+src=")
        self.assertNotRegex(html,r"<link[^>]+href=")
        for required in ("class=\"arena\"","id=\"stack\"","id=\"speed\"",
                         "id=\"highlights\"","id=\"slider\"","id=\"questionList\"",
                         "function unpack(value)","function showZones(seat)",
                         "function renderPhase(phase)"):
            self.assertIn(required,html)
        self.assertIn("p[7]||[]",html)
        self.assertIn("p[8]||[]",html)

    def test_embedded_real_deck_sample_has_actual_nonempty_replay(self):
        text=(HERE/"examples/match-theater-real-decks.html").read_text(encoding="utf-8")
        self.assertNotIn("/*EMBEDDED_REPLAY*/null",text)
        start=text.index("let data=")+len("let data=")
        end=text.index(";\nlet position=",start)
        report=json.loads(text[start:end])
        self.assertEqual(report["schemaVersion"],1)
        self.assertEqual(report["kind"],"turn-replay")
        self.assertTrue(report.get("packedReplay")==1)
        self.assertGreater(len(report.get("compactEvents",[])),20)
        self.assertEqual(len(report["deckNames"]),2)
        self.assertEqual(report["learningEligible"],False)
        self.assertNotRegex(text,r"<script[^>]+src=")

    def test_raw_replay_name_index_and_stack_inspection_exist(self):
        html=(HERE/"viewer.html").read_text(encoding="utf-8")
        self.assertIn('for(const event of data?.events||[])',html)
        self.assertIn('for(const hand of event.spectatorHands||[])',html)
        self.assertIn('preview.onclick=()=>inspectCard(',html)

    def test_both_sample_htmls_share_new_spectator_controls(self):
        for sample in ("examples/match-theater-real-decks.html",
                       "examples/budget-vs-goblins-spectator-20261029.html"):
            text=(HERE/sample).read_text(encoding="utf-8")
            for marker in ('id="swapSeats"', 'id="nextCombat"', "COMMAND ZONE",
                           "renderSpotlight", "stackPrintedName"):
                self.assertIn(marker,text)
            start=text.index("let data=")+len("let data=")
            end=text.index(";\nlet position=",start)
            report=json.loads(text[start:end])
            self.assertGreater(len(report["compactEvents"]),100)
        latest=(HERE/"examples/budget-vs-goblins-spectator-20261029.html").read_text(encoding="utf-8")
        start=latest.index("let data=")+len("let data=")
        report=json.loads(latest[start:latest.index(";\nlet position=",start)])
        self.assertTrue(report["spectatorReplay"])
        self.assertEqual(len(report["compactEvents"]),458)

    def test_html_export_still_embeds_without_script_injection(self):
        report=dict(schemaVersion=1,kind="rules-review",
                    notice="Cards: </script><script>alert('x')</script>",
                    status="blocked",questions=[dict(id="unknown",card="<danger>",
                                                     question="What happens?",answer=None)])
        with tempfile.TemporaryDirectory() as td:
            dest=Path(td)/"review.json"
            s.export_review(dest,report)
            html=dest.with_suffix(".html").read_text(encoding="utf-8")
            self.assertNotIn("</script><script>alert",html)
            self.assertIn("\\u003c/script>",html)
            self.assertNotIn("/*EMBEDDED_REPLAY*/null",html)
            self.assertIn("let data=",html)

    def test_viewer_script_syntax_is_valid_if_node_is_available(self):
        node=shutil.which("node")
        if node is None:self.skipTest("Node.js unavailable")
        html=(HERE/"viewer.html").read_text(encoding="utf-8")
        script=html.split("<script>",1)[1].split("</script>",1)[0]
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/"viewer.js"
            path.write_text(script,encoding="utf-8")
            result=subprocess.run([node,"--check",str(path)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
