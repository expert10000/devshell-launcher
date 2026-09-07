from pathlib import Path
import re
def test_atlas_generator_declares_all_models():
    p=Path(__file__).with_name("generate_commit659_hamiltonian_atlas.py")
    s=p.read_text(encoding="utf-8")
    for name in ["ssh(","rice(","qwz(","bhz(","bbh(","kitaev(","weyl(","nodal("]:
        assert name in s
def test_atlas_has_eight_output_panels():
    p=Path(__file__).with_name("generate_commit659_hamiltonian_atlas.py")
    s=p.read_text(encoding="utf-8")
    assert len(re.findall(r'hamiltonian_visual_panel\.pdf',s))==8
