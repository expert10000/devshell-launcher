from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
FILES=["crystalline_topology_designed_panel.pdf","polarization_wannier_designed_panel.pdf","higher_order_hierarchy_designed_panel.pdf","bbh_boundary_hierarchy_designed_panel.pdf","interacting_topology_designed_panel.pdf","many_body_invariant_designed_panel.pdf","fractionalization_designed_panel.pdf","topological_order_designed_panel.pdf"]
def test_commit665_designed_conceptual_panels_exist():
    d=ROOT/"generated/ch62/designed_conceptual_panels"
    for f in FILES:
        p=d/f; assert p.exists() and p.stat().st_size>1000
