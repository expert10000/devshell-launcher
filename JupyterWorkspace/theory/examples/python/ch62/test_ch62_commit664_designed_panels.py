from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
FILES=["berry_two_level_designed_panel.pdf","ssh_designed_panel.pdf","rice_mele_designed_panel.pdf","qwz_designed_panel.pdf","bhz_designed_panel.pdf","bbh_designed_panel.pdf","kitaev_designed_panel.pdf","weyl_designed_panel.pdf"]
def test_commit664_designed_panels_exist():
    d=ROOT/"generated/ch62/designed_hamiltonian_panels"
    for f in FILES:
        p=d/f; assert p.exists() and p.stat().st_size>1000
