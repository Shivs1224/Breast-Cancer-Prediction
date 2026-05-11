"""
Shared export paths for PyQt desktop and Flask web (data/ layout).
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
MASKS = DATA / "masks"
POLYGONS = DATA / "polygons"
COORDINATES = DATA / "coordinates"
LABEL_CSV = DATA / "label.csv"


def ensure_data_dirs() -> None:
    for p in (DATA, MASKS, POLYGONS, COORDINATES):
        p.mkdir(parents=True, exist_ok=True)
