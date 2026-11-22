"""Preview a spec on the rendered PNG (no .aif encode): for textures apply_spec.py cannot encode yet (DXT1)."""
import json, os, sys
import numpy as np
from PIL import Image
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import apply_spec
spec_path, lang, png, out = sys.argv[1:5]
spec = json.load(open(spec_path, encoding='utf-8'))
img = np.array(Image.open(png).convert('RGBA'))
for lab in spec['labels']:
    apply_spec.clear_box(img, lab, lang)
for lab in spec['labels']:
    apply_spec.draw_label(img, lab, lang, print)
Image.fromarray(img, 'RGBA').save(out)
