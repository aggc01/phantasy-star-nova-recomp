"""review_grow_boxes.py <spec> - for each text label and language whose text (fixed size) is taller than its box,
set box_<lang> = the box grown by the missing rows (half above, half below), keeping the text's centre (review)."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.dirname(HERE))
import apply_spec as A
sp = sys.argv[1]; s = json.load(open(sp, encoding='utf-8'))
for i, L in enumerate(s['labels']):
    for lang in ('en', 'ar'):
        t = A.opt(L, lang, lang, '')
        size = A.opt(L, 'size', lang, None)
        if not t or size is None: continue
        ol = A.opt(L, 'outline', lang, None)
        st = int(A.opt(L, 'outline_px', lang, 1)) if ol else 0
        w, h, _ = A._measure(A._lines(t, lang), A.font_for(lang, int(size)), st, int(A.opt(L, 'line_gap', lang, 0)))
        x0, y0, x1, y1 = A.opt(L, 'box', lang)
        need = h - (y1 - y0)
        if need > 0:
            L['box_' + lang] = [x0, y0 - need // 2, x1, y1 + (need - need // 2)]
            print(i, lang, t.replace('\n', ' / ')[:30], 'box ->', L['box_' + lang])
json.dump(s, open(sp, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
