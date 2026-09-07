from pathlib import Path
import re
ROOT=Path(__file__).resolve().parents[3]
MASTER=ROOT/"volume08_schrodinger_hamiltonian_physics_development.tex"
CH62=ROOT/"book/development/volume08_schrodinger_hamiltonian_physics/chapters/chapter62_geometric_and_topological_hamiltonians"
DESIRED="book/development/volume08_schrodinger_hamiltonian_physics/chapters/chapter62_geometric_and_topological_hamiltonians/chapter62"
RX=re.compile(r'^\s*(?P<comment>%\s*)?\\(?:input|include)\{(?P<target>[^}]+)\}',re.I)

def test_master_has_exactly_one_active_developed_chapter62():
    hits=[]
    for line in MASTER.read_text(encoding="utf-8-sig").splitlines():
        m=RX.match(line)
        if m and not m.group("comment") and "chapter62" in m.group("target").lower():
            hits.append(m.group("target").replace("\\","/").lstrip("./"))
    assert hits==[DESIRED]

def test_developed_driver_references_all_60_sections():
    s=(CH62/"chapter62.tex").read_text(encoding="utf-8-sig")
    assert len(re.findall(r'\\input\{[^}]*sections/62_',s))>=60
    assert len(list((CH62/"sections").glob("62_*.tex")))==60
