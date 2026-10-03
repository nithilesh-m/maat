from maat.catalog.loader import load_catalog
from maat.catalog.regimes import load_regimes  # place load_regimes in src/maat/catalog/regimes.py


def test_regimes_cover_catalog():
    regs = load_regimes()
    used = {r for c in load_catalog().controls.values() for r in c.regimes}
    assert used <= set(regs) and regs["ISO"].licence == "reference-only"
