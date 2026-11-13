"""One-off: turn the variable Google Fonts into small static subsets (base64 WOFF2/WOFF)
that render_cards.py embeds. Run locally after changing fonts; output is committed."""
import base64, json, pathlib, subprocess, sys
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

ROOT = pathlib.Path(__file__).resolve().parent.parent / "fonts"
TEXT = "".join(chr(c) for c in range(32, 127)) + "·→↗★•—–…▍"
JOBS = [  # (source, weight, out name)
    ("SpaceGrotesk%5Bwght%5D.ttf", 700, "grotesk-700"),
    ("SpaceGrotesk%5Bwght%5D.ttf", 500, "grotesk-500"),
    ("JetBrainsMono%5Bwght%5D.ttf", 400, "mono-400"),
    ("JetBrainsMono%5Bwght%5D.ttf", 600, "mono-600"),
]
try:
    import brotli  # noqa: F401
    FLAVOR, EXT = "woff2", "woff2"
except ImportError:
    FLAVOR, EXT = "woff", "woff"

metrics = {}
for src, wght, name in JOBS:
    font = instancer.instantiateVariableFont(TTFont(ROOT / src), {"wght": wght})
    cmap, hmtx = font.getBestCmap(), font["hmtx"]
    metrics[name] = {"upm": font["head"].unitsPerEm,
                     "adv": {ch: hmtx[cmap[ord(ch)]][0] for ch in TEXT if ord(ch) in cmap}}
    tmp = ROOT / f"{name}.ttf"
    font.save(tmp)
    out = ROOT / f"{name}.{EXT}"
    subprocess.run([sys.executable, "-m", "fontTools.subset", str(tmp), f"--text={TEXT}",
                    f"--flavor={FLAVOR}", "--layout-features=kern,liga", "--no-hinting",
                    "--desubroutinize", f"--output-file={out}"], check=True)
    tmp.unlink()
    (ROOT / f"{name}.b64").write_text(f"{EXT}:" + base64.b64encode(out.read_bytes()).decode())
    print(name, out.stat().st_size, "bytes")

(ROOT / "metrics.json").write_text(json.dumps(metrics))
