"""thumb.html -> thumb.png (560 px, 256-colour palette so the lamp colours survive)."""
import os
import subprocess
import sys
import pathlib
from PIL import Image

HERE = pathlib.Path(__file__).parent
scratch = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp")
raw = scratch / "thumb_raw.png"
chrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
subprocess.run(["timeout", "40", chrome, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                f"--user-data-dir={scratch}/chrome", "--window-size=560,560", "--virtual-time-budget=8000",
                f"--screenshot={raw}", f"file://{HERE}/thumb.html"], capture_output=True)
subprocess.run(["pkill", "-f", f"{scratch}/chrome"])
im = Image.open(raw).convert("RGB").crop((0, 0, 560, 560))
im.quantize(colors=256, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.NONE).save(HERE / "thumb.png", optimize=True)
print(os.path.getsize(HERE / "thumb.png") // 1024, "KB")
