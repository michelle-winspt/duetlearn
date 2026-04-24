"""
Duetlearn — Generic Article Pipeline
Usage: python3 pipeline.py PMC_ID [topic_tag]
Fetches any PMC open-access paper and rewrites it for ESL HS/college students.
"""
import json, os, re, sys, time, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Load .env
for line in (ROOT / ".env").read_text().splitlines():
    if "=" in line and not line.startswith("#"):
        k, _, v = line.partition("=")
        os.environ[k.strip()] = v.strip()
API_KEY = os.environ["GEMINI_API_KEY"]

PMC_ID = sys.argv[1] if len(sys.argv) > 1 else sys.exit("Usage: pipeline.py PMC_ID")
PMC_NUM = PMC_ID.replace("PMC", "")
SOURCE_URL = f"https://pmc.ncbi.nlm.nih.gov/articles/{PMC_ID}/"

# Fetch citation metadata from PMC
print(f"📥 Fetching metadata for {PMC_ID}…")
meta_url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=pmc&id={PMC_NUM}&retmode=json"
with urllib.request.urlopen(urllib.request.Request(meta_url, headers={"User-Agent": "Duetlearn/0.1"}), timeout=30) as r:
    meta = json.load(r)["result"].get(PMC_NUM, {})
AUTHORS = meta.get("authors", [])
author_str = ", ".join(a.get("name", "") for a in AUTHORS[:3])
if len(AUTHORS) > 3:
    author_str += " et al."
CITATION = f'{author_str} ({meta.get("pubdate","")[:4]}). {meta.get("title","")}. {meta.get("source","")}.'
LICENSE = "CC-BY 4.0"
print(f"   Citation: {CITATION[:120]}")

# Fetch full text XML
print(f"📥 Fetching full text…")
fetch_url = (
    f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
    f"?db=pmc&id={PMC_NUM}&rettype=xml"
)
req = urllib.request.Request(fetch_url, headers={"User-Agent": "Duetlearn-pipeline/0.1"})
with urllib.request.urlopen(req, timeout=60) as r:
    xml_text = r.read().decode("utf-8", errors="ignore")

(ROOT / "papers" / f"{PMC_ID}.xml").write_text(xml_text, encoding="utf-8")
print(f"   saved papers/{PMC_ID}.xml ({len(xml_text):,} chars)")

# Extract plaintext + abstract separately
plain = re.sub(r"<[^>]+>", " ", xml_text)
plain = re.sub(r"\s+", " ", plain).strip()[:40000]

# Extract abstract for storage
m = re.search(r"<abstract[^>]*>(.*?)</abstract>", xml_text, re.DOTALL)
abstract_raw = ""
if m:
    abstract_raw = re.sub(r"<[^>]+>", " ", m.group(1))
    abstract_raw = re.sub(r"\s+", " ", abstract_raw).strip()

SYSTEM = """You are a science educator writing for ESL high-school and college students in Taiwan
(CEFR B1/B2, around age 17-22, native Traditional Chinese speakers).

Your job: turn a dense scientific paper into a friendly, accurate learning article
with bilingual support and a layered quiz.

ABSOLUTE RULES:
- English: average sentence ≤20 words. Active voice >80%.
- Define every term above CEFR B2 inline (in parentheses).
- 600–900 words total for the English article.
- Structure: Hook → Background → What they did → What they found → Why it matters → Open questions.
- DO NOT copy any sentence directly from the paper.
- The Chinese version must be natural Traditional Chinese (zh-TW), Taiwanese vocabulary.
- Output STRICT JSON matching the schema. No markdown fences. No comments.
"""

SCHEMA_HINT = """{
  "title_en": "compelling, ≤10 words",
  "title_zh": "吸睛中文標題",
  "tldr_en": "two-sentence TL;DR",
  "tldr_zh": "兩句話總結",
  "difficulty": "B1" | "B2",
  "estimated_minutes": integer,
  "tags": ["#tag1", "#tag2", ...],
  "article_en": "markdown, 600-900 words",
  "article_zh": "對應的中文版 markdown",
  "glossary": [
    {"term": "...", "ipa": "...", "definition_en": "...", "definition_zh": "..."}
  ],
  "quiz": {
    "recall": [
      {
        "question_en": "...", "question_zh": "...",
        "options_en": ["A...", "B...", "C...", "D..."],
        "answer": "B",
        "hint_en": "...", "hint_zh": "...",
        "explanation_en": "...", "explanation_zh": "..."
      }
    ],
    "transfer": [],
    "critical": []
  }
}"""

prompt = f"""{SYSTEM}

Output JSON exactly matching this schema:
{SCHEMA_HINT}

---
PAPER METADATA
Citation: {CITATION}
License: {LICENSE}
Source: {SOURCE_URL}

PAPER FULL TEXT (XML stripped, may contain noise):
\"\"\"
{plain}
\"\"\"
"""

MODEL = "gemini-2.5-pro"
api_url = (
    f"https://generativelanguage.googleapis.com/v1beta/models/"
    f"{MODEL}:generateContent?key={API_KEY}"
)
body = {
    "contents": [{"parts": [{"text": prompt}]}],
    "generationConfig": {
        "responseMimeType": "application/json",
        "temperature": 0.7,
        "maxOutputTokens": 16000,
    },
}

print(f"🤖 Calling {MODEL}… (30–120s)")
result = None
for attempt in range(1, 5):
    req = urllib.request.Request(
        api_url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            result = json.load(r)
        break
    except urllib.error.HTTPError as e:
        msg = e.read().decode("utf-8", errors="ignore")[:200]
        print(f"   attempt {attempt} → HTTP {e.code}: {msg}")
        if e.code in (429, 503) and attempt < 4:
            wait = 10 * attempt
            print(f"   waiting {wait}s…")
            time.sleep(wait)
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
    s = cleaned.find("{"); e = cleaned.rfind("}")
    if s >= 0 and e > s:
        cleaned = cleaned[s:e+1]

try:
    parsed = json.loads(cleaned)
except json.JSONDecodeError as je:
    raw_dump = ROOT / "output" / f"raw_{PMC_ID}.txt"
    raw_dump.write_text(generated, encoding="utf-8")
    print(f"⚠️  JSON parse failed ({je}). Raw saved to {raw_dump}")
    sys.exit(1)

# Add original abstract + citation metadata
parsed["original_abstract"] = abstract_raw
parsed["original_citation"] = CITATION
parsed["original_url"] = SOURCE_URL
parsed["original_license"] = LICENSE
parsed["pmc_id"] = PMC_ID

# Save to output/
out_path = ROOT / "output" / f"article_{PMC_ID}.json"
out_path.write_text(json.dumps(parsed, ensure_ascii=False, indent=2), encoding="utf-8")

# Also save to web/data/articles/
articles_dir = ROOT / "web" / "data" / "articles"
articles_dir.mkdir(exist_ok=True)
(articles_dir / f"{PMC_ID}.json").write_text(json.dumps(parsed, ensure_ascii=False, indent=2), encoding="utf-8")

print()
print("=" * 60)
print(f"✅ DONE  →  {PMC_ID}")
print("=" * 60)
print(f"Title : {parsed.get('title_en', '')}")
print(f"標題  : {parsed.get('title_zh', '')}")
print(f"難度  : {parsed.get('difficulty', '')}  ·  {parsed.get('estimated_minutes', '?')} min")
print(f"Tags  : {' '.join(parsed.get('tags', []))}")
