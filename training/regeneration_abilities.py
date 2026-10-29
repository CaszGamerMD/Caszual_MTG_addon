"""Strict composable tribal anthem + tap-to-regenerate another matching creature."""
import re
from oracle_abilities import compile_abilities


def parse(text,types):
    if 'Creature' not in types:return None
    lines=text.splitlines()
    if len(lines)!=2:return None
    anthem=re.fullmatch(r'Other ([A-Z][a-z]+) creatures you control get \+([0-9]+)/\+([0-9]+)\.',lines[0])
    activation=re.fullmatch(r'\{T\}: Regenerate another target ([A-Z][a-z]+)\.',lines[1])
    if not anthem or not activation or anthem[1]!=activation[1]:return None
    program=compile_abilities(lines[0])
    if program is None or len(program.static_effects)!=1 or program.triggers or program.activations:return None
    return program,activation[1]
