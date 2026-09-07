from pathlib import Path
def test_reference_generator_has_all_models():
    s=Path(__file__).with_name("generate_commit660_reference_visuals.py").read_text(encoding="utf-8")
    for m in ["SSH","Rice–Mele","QWZ","BHZ","BBH","Kitaev","Weyl","Nodal line"]:
        assert m in s
def test_reference_generator_has_five_visual_columns():
    s=Path(__file__).with_name("generate_commit660_reference_visuals.py").read_text(encoding="utf-8")
    for x in ["physical setup","basis/couplings","Hamiltonian","spectrum/invariant","boundary/response"]:
        assert x in s
