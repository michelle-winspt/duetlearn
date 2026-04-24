"""
EduPaper / Duetlearn — Pilot 001
Fetches an open-access paper from PubMed Central, then asks Gemini
to rewrite it for ESL HS students with bilingual + 3-tier quiz.

Zero external dependencies (uses only Python stdlib).
"""
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

# ---- 1. Load API key from .env ----
ROOT = Path(__file__).resolve().parent.parent
env_path = ROOT / ".env"
for line in env_path.read_text().splitlines():
    if "=" in line and not line.startswith("#"):
        k, _, v = line.partition("=")
        os.environ[k.strip()] = v.strip()
API_KEY = os.environ["GEMINI_API_KEY"]

# ---- 2. Paper config ----
PMC_ID = "PMC8473838"  # Behavioral and Neural Dynamics of Interpersonal Synchrony (piano duet hyperscanning)
SOURCE_URL = f"https://pmc.ncbi.nlm.nih.gov/articles/{PMC_ID}/"
CITATION = "Müller V, Sänger J, Lindenberger U (2021). Behavioral and Neural Dynamics of Interpersonal Synchrony Between Performing Musicians: A Wireless EEG Hyperscanning Study. Frontiers in Human Neuroscience, 15:717810."
LICENSE = "CC-BY 4.0"

# ---- 3. Fetch the full text via PMC E-utilities ----
print(f"📥 Fetching {PMC_ID} from PubMed Central…")
pmc_numeric = PMC_ID.replace("PMC", "")
fetch_url = (
    f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
    f"?db=pmc&id={pmc_numeric}&rettype=xml"
)
req = urllib.request.Request(
    fetch_url,
    headers={"User-Agent": "Duetlearn-pilot/0.1 (educational research)"},
)
with urllib.request.urlopen(req, timeout=60) as resp:
    xml_text = resp.read().decode("utf-8", errors="ignore")

(ROOT / "papers" / f"{PMC_ID}.xml").write_text(xml_text, encoding="utf-8")
print(f"   saved papers/{PMC_ID}.xml ({len(xml_text):,} chars)")

# ---- 4. Strip XML tags into rough plaintext ----
plain = re.sub(r"<[^>]+>", " ", xml_text)
plain = re.sub(r"\s+", " ", plain).strip()
# Cap at ~40k chars to stay well within Gemini's context budget
plain = plain[:40000]
print(f"   plaintext extracted ({len(plain):,} chars after trim)")

# ---- 5. Build the rewriter prompt ----
SYSTEM = """You are a science educator writing for ESL high-school students in Taiwan
(CEFR B1/B2, around age 17, native Traditional Chinese speakers).

Your job: turn a dense scientific paper into a friendly, accurate learning article
with bilingual support and a layered quiz.

ABSOLUTE RULES:
- English: average sentence ≤20 words. Active voice >80%.
- Define every term above CEFR B2 inline (in parentheses).
- 600–900 words total for the English article.
- Structure: Hook → Background → What they did → What they found → Why it matters → Open questions.
- DO NOT copy any sentence directly from the paper (avoid even on CC-BY material).
- The Chinese version must be a natural Traditional Chinese (zh-TW) translation,
  NOT a literal word-for-word render. Use Taiwanese vocabulary.
- Output STRICT JSON matching the schema. No markdown fences. No comments.
"""

SCHEMA_HINT = """{
  "title_en": "compelling, ≤10 words",
  "title_zh": "吸睛中文標題",
  "tldr_en": "two-sentence TL;DR",
  "tldr_zh": "兩句話總結",
  "difficulty": "B1" | "B2",
  "estimated_minutes": integer,
  "tags": ["#音樂腦科學", "#鋼琴合作", ...],
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
        "hint_en": "where to look in the article",
        "hint_zh": "...",
        "explanation_en": "why this is the right answer",
        "explanation_zh": "..."
      }
      // 3 questions total
    ],
    "transfer": [ /* 2 questions: apply concept to new scenario */ ],
    "critical": [ /* 1 question: limitation / what's missing? */ ]
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

PAPER FULL TEXT (XML stripped, may contain noise — ignore reference lists / figure captions if unclear):
\"\"\"
{plain}
\"\"\"
"""

# ---- 6. Call Gemini 2.5 Pro ----
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
import time
print(f"🤖 Calling {MODEL}… (this may take 30–90 seconds)")
result = None
for attempt in range(1, 5):
    req = urllib.request.Request(
        api_url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            result = json.loads(resp.read())
        break
    except urllib.error.HTTPError as e:
        msg = e.read().decode("utf-8", errors="ignore")[:300]
        print(f"   attempt {attempt} → HTTP {e.code}: {msg[:120]}")
        if e.code in (429, 503) and attempt < 4:
            wait = 5 * attempt
            print(f"   waiting {wait}s before retry…")
            time.sleep(wait)
            continue
        sys.exit(1)
if result is None:
    sys.exit(1)

generated = result["candidates"][0]["content"]["parts"][0]["text"]
# Strip ```json ... ``` fences if model added them
cleaned = generated.strip()
if cleaned.startswith("```"):
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```\s*$", "", cleaned)
# Find first { and last } as a final safety net
if not cleaned.startswith("{"):
    s = cleaned.find("{"); e = cleaned.rfind("}")
    if s >= 0 and e > s:
        cleaned = cleaned[s : e + 1]
try:
    parsed = json.loads(cleaned)
except json.JSONDecodeError as je:
    raw_dump = ROOT / "output" / f"raw_{PMC_ID}.txt"
    raw_dump.write_text(generated, encoding="utf-8")
    print(f"⚠️  JSON parse failed ({je}). Raw output saved to {raw_dump}")
    sys.exit(1)

# ---- 7. Save ----
out_path = ROOT / "output" / f"article_{PMC_ID}.json"
out_path.write_text(json.dumps(parsed, ensure_ascii=False, indent=2), encoding="utf-8")

# ---- 8. Pretty preview ----
print()
print("=" * 60)
print(f"✅ DONE  →  output/article_{PMC_ID}.json")
print("=" * 60)
print(f"標題  : {parsed.get('title_zh', '')}")
print(f"Title : {parsed.get('title_en', '')}")
print(f"難度  : {parsed.get('difficulty', '')}  ·  {parsed.get('estimated_minutes', '?')} min")
print(f"Tags  : {' '.join(parsed.get('tags', []))}")
print()
print("📝 TL;DR (EN):", parsed.get("tldr_en", ""))
print("📝 TL;DR (中):", parsed.get("tldr_zh", ""))
print()
print("📚 Glossary terms:", len(parsed.get("glossary", [])))
quiz = parsed.get("quiz", {})
print(f"📊 Quiz: {len(quiz.get('recall', []))} recall + "
      f"{len(quiz.get('transfer', []))} transfer + "
      f"{len(quiz.get('critical', []))} critical")
