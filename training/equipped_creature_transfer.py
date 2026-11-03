"""Reusable whole-card grammar: equipped-creature death/attack transfer."""
import re


def parse(text, name, types):
    if "Creature" not in types:
        return None
    lines=text.splitlines()
    if len(lines)!=2 or lines[0]!="Trample, haste":
        return None
    self_ref=r"(?:this creature|"+re.escape(name)+r")"
    trigger=(r"Whenever an equipped creature you control other than "+self_ref+
             r" attacks or dies, you may attach all Equipment attached to that creature to "+
             self_ref+r"\.")
    if not re.fullmatch(trigger,lines[1]):
        return None
    return frozenset({"trample","haste"})
