"""
services/ai_filter.py
----------------------
Scores scraped jobs for veteran relevance.

RIGHT NOW  → fast keyword-based scorer (no API key needed, works immediately)
LATER      → swap to Claude API by setting ANTHROPIC_API_KEY in your Replit secrets.
             Change USE_CLAUDE_API = True below. Nothing else changes.
"""

import os
import re
import logging

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# TOGGLE: set to True once you have ANTHROPIC_API_KEY set
# ─────────────────────────────────────────────────────────────
USE_CLAUDE_API = False  # Disabled: no API credits


# ─────────────────────────────────────────────────────────────
# Veteran-relevant keyword taxonomy
# ─────────────────────────────────────────────────────────────

CATEGORY_KEYWORDS = {
    'Security': [
        'security', 'guard', 'surveillance', 'patrol', 'armed', 'unarmed',
        'protection', 'close protection', 'bodyguard', 'access control',
        'gateman', 'watchman', 'intelligence', 'loss prevention',
    ],
    'Driver': [
        'driver', 'chauffeur', 'dispatch rider', 'vehicle operator',
        'fleet driver', 'truck driver', 'bus driver', 'courier',
        'logistics driver', 'defensive driving',
    ],
    'Logistics': [
        'logistics', 'supply chain', 'warehouse', 'inventory', 'store keeper',
        'storekeeper', 'procurement', 'fleet', 'dispatch', 'distribution',
        'freight', 'cargo', 'shipping', 'supply officer',
    ],
    'Operations': [
        'operations', 'operations officer', 'operations manager', 'field officer',
        'site supervisor', 'plant operator', 'production', 'facilities',
        'maintenance supervisor', 'site manager',
    ],
    'Admin': [
        'administrator', 'administrative', 'office manager', 'executive assistant',
        'personal assistant', 'clerical', 'records officer', 'document control',
        'admin officer', 'admin support',
    ],
    'Health': [
        'health', 'nurse', 'paramedic', 'first aid', 'medical officer',
        'community health', 'health safety', 'hse', 'occupational health',
        'clinic', 'pharmacy', 'laboratory',
    ],
    'Health & Safety': [
        'hse', 'health safety environment', 'safety officer', 'safety manager',
        'ehsq', 'fire safety', 'emergency response', 'risk assessment',
    ],
    'Engineering': [
        'engineer', 'technician', 'electrical', 'mechanical', 'civil',
        'instrumentation', 'maintenance engineer', 'field engineer',
        'plant engineer',
    ],
    'IT': [
        'it officer', 'network', 'systems administrator', 'helpdesk',
        'technical support', 'cybersecurity', 'communications officer',
        'radio operator', 'signal',
    ],
    'Remote': [
        'remote', 'work from home', 'wfh', 'hybrid', 'fully remote',
        'virtual', 'telecommute',
    ],
}

# Keywords that strongly suggest a veteran-friendly role
VETERAN_SIGNALS = [
    'veteran', 'ex-military', 'ex military', 'former military', 'retired military',
    'ex-serviceman', 'ex serviceman', 'military background', 'military experience',
    'discipline', 'leadership', 'team player', 'integrity', 'paramilitary',
    'naf', 'nigerian army', 'nigerian navy', 'nigerian air force', 'dss',
    'nscdc', 'nigeria police', 'ndc', 'afcon',
]

# Keywords that make a job relevant even without explicit veteran mention
GENERAL_VETERAN_FRIENDLY = [
    'supervisor', 'team lead', 'coordinator', 'officer', 'manager',
    'inspector', 'compliance', 'protocol', 'structured', 'routine',
]


def score_job(title: str, description: str = '', requirements: str = '') -> dict:
    """
    Score a job for veteran relevance.

    Returns a dict:
        score       int  0–100
        category    str  e.g. 'Security'
        reasoning   str  human-readable explanation
        is_remote   bool
        is_veteran_relevant  bool
    """
    if USE_CLAUDE_API:
        return _score_with_claude(title, description, requirements)
    return _score_with_keywords(title, description, requirements)


# ─────────────────────────────────────────────────────────────
# KEYWORD SCORER (works right now, no API key)
# ─────────────────────────────────────────────────────────────

def _score_with_keywords(title: str, description: str, requirements: str) -> dict:
    text = f"{title} {description} {requirements}".lower()

    score = 0
    matched_category = None
    matched_keywords = []
    reasons = []

    # 1. Category matching (up to 60 points)
    best_cat_score = 0
    for category, keywords in CATEGORY_KEYWORDS.items():
        if category == 'Remote':
            continue
        hits = [kw for kw in keywords if kw in text]
        cat_score = min(len(hits) * 20 + 10, 60) if hits else 0
        if cat_score > best_cat_score:
            best_cat_score = cat_score
            matched_category = category
            matched_keywords = hits

    score += best_cat_score
    if matched_keywords:
        reasons.append(f"Matches {matched_category} category (keywords: {', '.join(matched_keywords[:3])})")

    # 2. Veteran signal bonus (up to 25 points)
    vet_hits = [kw for kw in VETERAN_SIGNALS if kw in text]
    if vet_hits:
        score += min(len(vet_hits) * 10, 25)
        reasons.append(f"Veteran-friendly signals detected: {', '.join(vet_hits[:2])}")

    # 3. General suitability (up to 15 points)
    gen_hits = [kw for kw in GENERAL_VETERAN_FRIENDLY if kw in text]
    if gen_hits:
        score += min(len(gen_hits) * 5, 15)
        reasons.append(f"Role requires structured leadership skills")

    # 4. Remote flag
    is_remote = any(kw in text for kw in CATEGORY_KEYWORDS['Remote'])
    if is_remote and not matched_category:
        matched_category = 'Remote'
        reasons.append("Remote/hybrid role — accessible to veterans anywhere")

    score = min(score, 100)
    is_relevant = score >= 50

    reasoning = '. '.join(reasons) if reasons else 'No strong veteran-relevant signals found.'

    return {
        'score': score,
        'category': matched_category or 'General',
        'reasoning': reasoning,
        'is_remote': is_remote,
        'is_veteran_relevant': is_relevant,
    }


# ─────────────────────────────────────────────────────────────
# CLAUDE API SCORER (activated when ANTHROPIC_API_KEY is set)
# ─────────────────────────────────────────────────────────────

def _score_with_claude(title: str, description: str, requirements: str) -> dict:
    """Uses Claude claude-sonnet-4-20250514 to score the job. Falls back to keywords on error."""
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=os.environ['ANTHROPIC_API_KEY'])

        prompt = f"""You are an expert at identifying job opportunities suitable for Nigerian military veterans and military spouses.

Analyse this job posting and respond ONLY with a JSON object (no markdown, no extra text):

Job Title: {title}
Description: {description[:800]}
Requirements: {requirements[:400]}

Respond with exactly this JSON structure:
{{
  "score": <integer 0-100, how relevant for veterans>,
  "category": "<one of: Security, Driver, Logistics, Operations, Admin, Health, Health & Safety, Engineering, IT, Remote, General>",
  "reasoning": "<one sentence explaining the score>",
  "is_remote": <true or false>,
  "is_veteran_relevant": <true if score >= 50>
}}"""

        message = client.messages.create(
            model='claude-sonnet-4-20250514',
            max_tokens=300,
            messages=[{'role': 'user', 'content': prompt}]
        )

        import json
        raw = message.content[0].text.strip()
        result = json.loads(raw)
        return result

    except Exception as e:
        logger.warning(f"Claude API scoring failed ({e}), falling back to keywords")
        return _score_with_keywords(title, description, requirements)