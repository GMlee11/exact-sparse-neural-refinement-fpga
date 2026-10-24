"""Fixed exploratory pilot definition; no board access."""
from pathlib import Path
import hashlib
import json
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
C07 = ROOT/'experiments/paper2_architecture_search_20261021/implementation/c07'
BRAM = ROOT/'experiments/paper2_bounded_salvage_20261021/implementation'
GOLDEN = C07/'goldens/G001'
FRAMES = (0, 2)
MASKS = (0, 1, 2, 5, 4, 10)
CASE_IDS = tuple(f*17+m for f in FRAMES for m in MASKS)
RECORD_WORDS = 44
sys.path.insert(0, str(ROOT))
from src.experiments.paper2_conventional_comparison_v1.comparison import Rect, rectangles, union_mask


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def pin(path):
    path = Path(path).resolve()
    return dict(path=str(path), bytes=path.stat().st_size, sha256=sha(path))


def golden_manifest():
    g = json.loads((GOLDEN/'manifest.json').read_text())
    assert g['pass']
    assert sha(GOLDEN/'input_banks.bin') == g['input_banks']['sha256']
    return g


def regions(indices, mode):
    """Independent expected geometry: (expanded input box, owned indices)."""
    if not indices:
        return []
    tiles = rectangles(indices, mode='tiles')
    if mode == 0:
        return [(Rect(0, 0, 360, 640), indices)]
    if mode == 1:
        box = Rect(min(r.y0 for r in tiles), min(r.x0 for r in tiles),
                   max(r.y1 for r in tiles), max(r.x1 for r in tiles))
        return [(box.expand(3, 360, 640), indices)]
    assert mode == 2
    return [(r.expand(3, 360, 640),
             [i for i in indices if r.y0 <= i//10*60 < r.y1 and r.x0 <= i%10*64 < r.x1])
            for r in rectangles(indices, mode='merged_rectangles')]


def schedule(kind, base=0, repeats=3):
    """Six cyclic rotations balance C07 order across ABBA's two legs."""
    arms = [(0, m) for m in range(3)] if kind == 0 else [(c, m) for c in (1, 2) for m in range(3)]
    for rep in range(repeats):
        for j, case in enumerate(CASE_IDS):
            for order in range(len(arms)):
                condition, mode = arms[(j+base+rep+order) % len(arms)]
                yield dict(case=case, mode=mode, repeat=base+rep, condition=condition)
