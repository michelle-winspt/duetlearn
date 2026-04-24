"""
Duetlearn — Multi-Level Pipeline
Generates 4 CEFR-level versions (B1, B2, C1, C2) of an article in ONE Gemini call.
Glossary and quiz stay at B2 (shared across levels).

Usage: python3 pipeline_multilevel.py PMC_ID
"""
import json, os, re, sys, time, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for line in (ROOT / ".env").read_text().splitlines():
    if "=" in line and not line.startswith("#"):
        k, _, v = line.partition("=")
        os.environ[k.strip()] = v.strip()
API_KEY = os.environ["GEMINI_API_KEY"]

PMC_ID = sys.argv[1] if len(sys.argv) > 1 else sys.exit("Usage: pipeline_multilevel.py PMC_ID")
PMC_NUM = PMC_ID.replace("PMC", "")
SOURCE_URL = f"https://pmc.ncbi.nlm.nih.gov/articles/{PMC_ID}/"

# Try to use existing XML if available
xml_path = ROOT / "papers" / f"{PMC_ID}.xml"
if xml_path.exists():
    print(f"📂 Reusing cached {PMC_ID}.xml")
    xml_text = xml_path.read_text(encoding="utf-8")
else:
    print(f"📥 Fetching full text…")
    fetch_url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pmc&id={PMC_NUM}&rettype=xml"
    req = urllib.request.Request(fetch_url, headers={"User-Agent": "Duetlearn/0.1"})
    with urllib.request.urlopen(req, timeout=60) as r:
        xml_text = r.read().decode("utf-8", errors="ignore")
    xml_path.write_text(xml_text, encoding="utf-8")

# Try to reuse existing article JSON for citation/abstract
existing_path = ROOT / "web" / "data" / "articles" / f"{PMC_ID}.json"
existing = json.loads(existing_path.read_text(encoding="utf-8")) if existing_path.exists() else {}
CITATION = existing.get("original_citation", "")
abstract_raw = existing.get("original_abstract", "")

if not CITATION:
    meta_url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=pmc&id={PMC_NUM}&retmode=json"
    with urllib.request.urlopen(urllib.request.Request(meta_url, headers={"User-Agent":"Duetlearn/0.1"}), timeout=30) as r:
        meta = json.load(r)["result"].get(PMC_NUM, {})
    AUTHORS = meta.get("authors", [])
    author_str = ", ".join(a.get("name","") for a in AUTHORS[:3]) + (" et al." if len(AUTHORS) > 3 else "")
    CITATION = f'{author_str} ({meta.get("pubdate","")[:4]}). {meta.get("title","")}. {meta.get("source","")}.'

if not abstract_raw:
    m = re.search(r"<abstract[^>]*>(.*?)</abstract>", xml_text, re.DOTALL)
    if m:
        abstract_raw = re.sub(r"<[^>]+>", " ", m.group(1))
        abstract_raw = re.sub(r"\s+", " ", abstract_raw).strip()

plain = re.sub(r"<[^>]+>", " ", xml_text)
plain = re.sub(r"\s+", " ", plain).strip()[:40000]

SYSTEM = """You are a science educator producing FOUR CEFR-level versions of one article for ESL Taiwanese students (zh-TW).

LEVEL DEFINITIONS:
- B1 (basic): 300-450 words EN. Sentences ≤15 words. Only common vocabulary. Define every term beyond A2 inline.
- B2 (intermediate): 600-900 words EN. Sentences ≤20 words avg. Define terms beyond B2 inline.
- C1 (advanced): 800-1100 words EN. Complex sentences allowed. Use field-specific vocabulary naturally; brief inline gloss only when ambiguous. Include 1-2 methodology details.
- C2 (proficient): 1000-1400 words EN. Full academic register. Use original technical terms (no inline definitions). Include statistical results, methodological nuance, and limitations discussion.

ALL LEVELS:
- Active voice >70%
- Same overall narrative arc: Hook → Background → Method → Findings → Significance → Open questions
- DO NOT copy any sentence directly from the source paper.
- Each Chinese version is a NATURAL Traditional Chinese rewrite (zh-TW), not literal translation.
- Each level's content should be MEANINGFULLY different in vocabulary density and depth, NOT just longer.

Output STRICT JSON. No markdown fences. No comments.
"""

SCHEMA = """{
  "title_en": "compelling shared title, ≤10 words",
  "title_zh": "共用中文標題",
  "difficulty": "multi",
  "estimated_minutes": 7,
  "tags": ["#tag1", "#tag2", ...],
  "levels": {
    "B1": {
      "tldr_en": "...", "tldr_zh": "...",
      "article_en": "markdown 300-450 words",
      "article_zh": "對應中文版"
    },
    "B2": {
      "tldr_en": "...", "tldr_zh": "...",
      "article_en": "markdown 600-900 words",
      "article_zh": "..."
    },
    "C1": {
      "tldr_en": "...", "tldr_zh": "...",
      "article_en": "markdown 800-1100 words",
      "article_zh": "..."
    },
    "C2": {
      "tldr_en": "...", "tldr_zh": "...",
      "article_en": "markdown 1000-1400 words",
      "article_zh": "..."
    }
  },
  "glossary": [
    {"term":"...", "ipa":"...", "definition_en":"B2-level definition", "definition_zh":"..."}
  ],
  "quiz": {
    "recall": [
      {"question_en":"...", "question_zh":"...",
       "options_en":["A...","B...","C...","D..."],
       "answer":"B",
       "hint_en":"...", "hint_zh":"...",
       "explanation_en":"...", "explanation_zh":"..."}
    ],
    "transfer": [],
    "critical": []
  }
}"""

prompt = f"""{SYSTEM}

Output JSON exactly matching this schema:
{SCHEMA}

---
PAPER METADATA
Citation: {CITATION}
Source: {SOURCE_URL}

PAPER FULL TEXT (XML stripped):
\"\"\"
{plain}
\"\"\"
"""

MODEL = "gemini-2.5-pro"
api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={API_KEY}"
body = {
    "contents": [{"parts": [{"text": prompt}]}],
    "generationConfig": {
        "responseMimeType": "application/json",
        "temperature": 0.6,
        "maxOutputTokens": 32000,
    },
}

print(f"🤖 Calling {MODEL} (multi-level)... 60-180s")
result = None
for attempt in range(1, 4):
    req = urllib.request.Request(api_url, data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=240) as r:
            result = json.load(r)
        break
    except urllib.error.HTTPError as e:
        msg = e.read().decode("utf-8", errors="ignore")[:200]
        print(f"   attempt {attempt} → HTTP {e.code}: {msg}")
        if e.code in (429, 503) and attempt < 3:
            time.sleep(15 * attempt)
        else:
            sys.exit(1)

if result is None:
    sys.exit(1)

generated = result["candidates"][0]["content"]["parts"][0]["text"]
cleaned = generated.strip()
if cleaned.startswith("```"):
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```\s*$", "", cleaned)
if not cleaned.startswith("{"):
    s, e = cleaned.find("{"), cleaned.rfind("}")
    if s >= 0 and e > s:
        cleaned = cleaned[s:e+1]

try:
    parsed = json.loads(cleaned)
except json.JSONDecodeError as je:
    raw = ROOT / "output" / f"raw_multi_{PMC_ID}.txt"
    raw.write_text(generated, encoding="utf-8")
    print(f"⚠️  JSON parse failed: {je}. Raw → {raw}")
    sys.exit(1)

# Add metadata
parsed["original_abstract"] = abstract_raw
parsed["original_citation"] = CITATION
parsed["original_url"] = SOURCE_URL
parsed["original_license"] = "CC-BY 4.0"
parsed["pmc_id"] = PMC_ID
parsed["multilevel"] = True

out_path = ROOT / "output" / f"article_{PMC_ID}_multi.json"
out_path.write_text(json.dumps(parsed, ensure_ascii=False, indent=2), encoding="utf-8")
(ROOT / "web" / "data" / "articles" / f"{PMC_ID}.json").write_text(
    json.dumps(parsed, ensure_ascii=False, indent=2), encoding="utf-8")

print()
print("=" * 60)
print(f"✅ MULTI-LEVEL DONE → {PMC_ID}")
print("=" * 60)
print(f"Title : {parsed.get('title_en','')}")
print(f"標題  : {parsed.get('title_zh','')}")
print(f"Tags  : {' '.join(parsed.get('tags', []))}")
levels = parsed.get('levels', {})
for lvl in ['B1','B2','C1','C2']:
    if lvl in levels:
        wc = len(levels[lvl].get('article_en','').split())
        print(f"  {lvl}: {wc} EN words")
