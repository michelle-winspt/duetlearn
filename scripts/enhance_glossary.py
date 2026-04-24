"""
Enhance all article glossaries with `pos` (part of speech) + `translation` (direct Chinese word).
Pure local — no API.
"""
import json
from pathlib import Path

ARTICLES_DIR = Path('/Users/michelle/Desktop/duetlearn/web/data/articles')

# Manual mapping of term → (pos, translation)
ENHANCE = {
    # PMC13062002 - Keratoconus
    'Keratoconus':              ('n.',   '圓錐角膜'),
    'Mendelian Randomisation':  ('phr.', '孟德爾隨機化（統計方法）'),
    'Atopy':                    ('n.',   '異位性體質／過敏傾向'),
    'Inflammation':             ('n.',   '發炎'),
    'Odds Ratio (OR)':          ('phr.', '勝算比'),
    # PMC13085316 - Psychological safety
    'Psychological safety':     ('phr.', '心理安全感'),
    'Peer feedback':            ('phr.', '同儕回饋'),
    'Vulnerability':            ('n.',   '脆弱／易受傷'),
    'Anonymous':                ('adj.', '匿名的'),
    'Relational calculus':      ('phr.', '人際關係計算'),
    # PMC13095118 - Sleep
    'Successor representation': ('phr.', '後繼表徵（預測下一步的腦內模型）'),
    'Electroencephalography (EEG)': ('n.', '腦電圖／腦波'),
    'Consolidation':            ('n.',   '鞏固／整合'),
    'Deep Neural Network (DNN)':('phr.', '深度神經網路'),
    'Slow-wave sleep (SWS)':    ('phr.', '慢波睡眠'),
    'Coupling':                 ('n.',   '耦合／連結'),
    # PMC13096162 - Bilingualism
    'Functional Connectivity':  ('phr.', '功能性連結'),
    'Domain-General':           ('adj.', '跨領域的／通用的'),
    'Hierarchical Structure':   ('phr.', '階層結構'),
    'Anterior':                 ('adj.', '前方的'),
    'Posterior':                ('adj.', '後方的'),
    # PMC8473838 - Music duets
    'Interpersonal synchrony':  ('phr.', '人際同步'),
    'Oscillator':               ('n.',   '振盪器／節律系統'),
    'Asynchrony':               ('n.',   '不同步'),
    'Hyperscanning':            ('n.',   '超掃描（同時測多人腦波）'),
}

count = 0
for f in sorted(ARTICLES_DIR.glob('PMC*.json')):
    d = json.loads(f.read_text(encoding='utf-8'))
    glossary = d.get('glossary', [])
    for g in glossary:
        term = g['term']
        if term in ENHANCE:
            pos, trans = ENHANCE[term]
            g['pos'] = pos
            g['translation'] = trans
            count += 1
        else:
            print(f'  ⚠️  No mapping for: {term}')
    f.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'✓ {f.name} ({len(glossary)} terms)')

print(f'\nTotal enhanced: {count} terms across all articles')
