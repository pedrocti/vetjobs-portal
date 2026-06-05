"""
services/cv_scanner.py
-----------------------
Scans a veteran's uploaded CV against a job's requirements
and returns a match score + reasoning.

Uses keyword/skill matching as primary method.
If ANTHROPIC_API_KEY is set and has credits, uses Claude for deeper analysis.
"""

import os
import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Skills and keywords grouped by category
SKILL_GROUPS = {
    'security': [
        'security', 'guard', 'surveillance', 'patrol', 'armed', 'unarmed',
        'access control', 'cctv', 'gateman', 'watchman', 'close protection',
        'bodyguard', 'loss prevention', 'intelligence', 'investigation',
    ],
    'driving': [
        'driver', 'driving', 'logistics driver', 'truck', 'bus driver',
        'dispatch rider', 'fleet', 'vehicle operation', 'defensive driving',
        'chauffeur', 'courier',
    ],
    'logistics': [
        'logistics', 'supply chain', 'warehouse', 'inventory', 'procurement',
        'store keeper', 'storekeeper', 'distribution', 'freight', 'cargo',
        'shipping', 'dispatch',
    ],
    'hse': [
        'hse', 'health safety', 'safety officer', 'fire safety', 'nebosh',
        'iosh', 'ispon', 'risk assessment', 'emergency response', 'ehsq',
        'occupational health', 'safety environment',
    ],
    'operations': [
        'operations', 'operations officer', 'supervisor', 'site manager',
        'facility management', 'plant operator', 'maintenance', 'coordinator',
    ],
    'admin': [
        'administrative', 'administration', 'office management', 'records',
        'document control', 'executive assistant', 'personal assistant',
        'clerical', 'admin officer',
    ],
    'military': [
        'military', 'army', 'navy', 'air force', 'naf', 'soldier',
        'officer', 'sergeant', 'lieutenant', 'captain', 'corporal',
        'service', 'veteran', 'ex-military', 'ex military', 'retired',
        'paramilitary', 'nscdc', 'police', 'dss',
    ],
    'soft_skills': [
        'leadership', 'team lead', 'discipline', 'integrity', 'communication',
        'teamwork', 'problem solving', 'decision making', 'management',
    ],
}


def extract_cv_text(resume_file_path: str) -> Optional[str]:
    """
    Extract plain text from a CV file.
    Supports PDF and Word documents.
    """
    if not resume_file_path:
        return None

    import os
    full_path = resume_file_path
    if not os.path.isabs(full_path):
        # Try multiple possible upload locations
        candidates = [
            os.path.join('/var/www/vetjobportal/static/uploads/resumes', resume_file_path.lstrip('/')),
            os.path.join('/var/www/vetjobportal/static/uploads/resumes', resume_file_path.lstrip('/')),
            os.path.join('/var/www/vetjobportal/static/uploads/resumes', resume_file_path.lstrip('/')),
        ]
        for candidate in candidates:
            if os.path.exists(candidate):
                full_path = candidate
                break
        else:
            full_path = candidates[0]  # default for error message

    if not os.path.exists(full_path):
        logger.warning(f"[cv_scanner] CV file not found: {full_path}")
        return None

    ext = os.path.splitext(full_path)[1].lower()

    try:
        if ext == '.pdf':
            try:
                import pdfplumber
                with pdfplumber.open(full_path) as pdf:
                    return '\n'.join(
                        page.extract_text() or '' for page in pdf.pages
                    )
            except ImportError:
                try:
                    import PyPDF2
                    with open(full_path, 'rb') as f:
                        reader = PyPDF2.PdfReader(f)
                        return '\n'.join(
                            page.extract_text() or '' for page in reader.pages
                        )
                except ImportError:
                    logger.warning("[cv_scanner] No PDF library available (pdfplumber/PyPDF2)")
                    return None

        elif ext in ('.docx', '.doc'):
            try:
                import docx
                doc = docx.Document(full_path)
                return '\n'.join(p.text for p in doc.paragraphs)
            except ImportError:
                logger.warning("[cv_scanner] python-docx not available")
                return None

        elif ext == '.txt':
            with open(full_path, 'r', errors='ignore') as f:
                return f.read()

        else:
            logger.warning(f"[cv_scanner] Unsupported CV format: {ext}")
            return None

    except Exception as e:
        logger.error(f"[cv_scanner] Error extracting CV text: {e}")
        return None


def _keyword_match(cv_text: str, job_title: str, job_requirements: str, job_description: str) -> dict:
    """
    Strict keyword-based CV match scoring.

    Scoring rules:
    - Base score: percentage of REQUIRED skill groups found in the CV (max 80)
    - Title match bonus: +10 if core job title words appear in CV
    - Military bonus: +5 only if military group is ALSO a job requirement
      (prevents inflating score for unrelated roles just because candidate is a veteran)
    - Threshold: 65 (raised from 50 to reduce false positives)
    - If the job has health/medical/nursing keywords and the CV has none: hard fail
    """
    cv_lower = cv_text.lower()
    job_text = f"{job_title} {job_requirements} {job_description}".lower()

    # ── Identify what skill groups the JOB requires ──────────
    job_needs = {}
    for group, keywords in SKILL_GROUPS.items():
        job_hits = [kw for kw in keywords if kw in job_text]
        if job_hits:
            job_needs[group] = job_hits

    # If no specific groups detected, use soft skills only (not military bonus)
    if not job_needs:
        job_needs = {'soft_skills': SKILL_GROUPS['soft_skills']}

    # ── Hard-fail: detect medical/health roles and check CV ──
    HEALTH_SIGNALS = [
        'nurs', 'doctor', 'physician', 'pharmacist', 'medical officer',
        'clinical', 'midwife', 'radiographer', 'physiotherapist',
        'laboratory', 'health worker', 'community health',
    ]
    job_is_health = any(sig in job_text for sig in HEALTH_SIGNALS)
    cv_has_health = any(sig in cv_lower for sig in HEALTH_SIGNALS)

    if job_is_health and not cv_has_health:
        return {
            'score': 15,
            'is_match': False,
            'reasoning': (
                'This role requires healthcare or medical qualifications. '
                'Your CV does not show relevant medical or clinical experience. '
                'Please only apply if you have the required healthcare background.'
            ),
            'matched_skills': [],
            'missing_skills': ['nursing/medical qualification', 'clinical experience', 'healthcare background'],
        }

    # ── Check which required groups appear in the CV ─────────
    matched_groups = {}
    missing_groups = {}
    for group, needed_kws in job_needs.items():
        cv_hits = [kw for kw in needed_kws if kw in cv_lower]
        if cv_hits:
            matched_groups[group] = cv_hits
        else:
            missing_groups[group] = needed_kws[:3]

    # ── Score calculation ─────────────────────────────────────
    total_needed = len(job_needs)
    total_matched = len(matched_groups)

    if total_needed == 0:
        score = 40
    else:
        # Base: proportion of required groups found in CV
        base_score = int((total_matched / total_needed) * 80)

        # Title match bonus: core job title words in CV
        title_words = [w for w in job_title.lower().split() if len(w) > 3]
        title_hits = [w for w in title_words if w in cv_lower]
        if title_hits:
            base_score = min(base_score + 10, 100)

        # Military bonus ONLY when the job itself requires military/security skills
        # (prevents admin/nursing CVs getting boosted just for being veterans)
        if 'military' in matched_groups and 'military' in job_needs:
            base_score = min(base_score + 5, 100)

        score = base_score

    # ── Build honest reasoning ────────────────────────────────
    reasons = []
    if matched_groups:
        matched_labels = [g for g in matched_groups if g != 'military'][:3]
        if matched_labels:
            reasons.append(f"Your CV shows relevant experience in: {', '.join(matched_labels)}")
        elif 'military' in matched_groups:
            reasons.append("Your military background is noted, but this role needs specific civilian skills")
    if missing_groups:
        missing_labels = list(missing_groups.keys())[:2]
        reasons.append(
            f"The role specifically requires {', '.join(missing_labels)} experience "
            f"which is not clearly shown in your CV"
        )

    # Threshold raised to 65 for stricter matching
    is_match = score >= 65
    reasoning = '. '.join(reasons) if reasons else (
        "Your CV shows a strong fit for this role." if is_match
        else "Your CV does not clearly match the specific requirements of this role."
    )

    return {
        'score': score,
        'is_match': is_match,
        'reasoning': reasoning,
        'matched_skills': [kw for hits in matched_groups.values() for kw in hits[:2]],
        'missing_skills': [kw for hits in missing_groups.values() for kw in hits[:2]],
    }


def _claude_match(cv_text: str, job_title: str, job_requirements: str, job_description: str) -> dict:
    """Deep CV match using Claude API."""
    try:
        import anthropic
        import json

        client = anthropic.Anthropic(api_key=os.environ['ANTHROPIC_API_KEY'])

        prompt = f"""You are a strict Nigerian HR consultant reviewing a veteran's CV for a civilian job application.

Your job is to give an HONEST and ACCURATE assessment. Do NOT be generous.
A veteran applying for a nursing, medical, legal, or engineering role with an unrelated CV should score very low.
Military background alone is NOT sufficient for specialist roles.

JOB TITLE: {job_title}

JOB REQUIREMENTS:
{job_requirements[:800]}

JOB DESCRIPTION:
{job_description[:600]}

CANDIDATE'S CV:
{cv_text[:2000]}

Carefully assess:
1. Does the CV show direct experience or qualifications for THIS specific role?
2. Are the key required skills actually present in the CV?
3. Military background is a plus ONLY if the role requires security, leadership, logistics, or operations.
4. For healthcare, legal, engineering, or technical roles: the candidate MUST show relevant qualifications.

Respond ONLY with JSON (no markdown, no extra text):
{{
  "score": <integer 0-100, be strict and accurate>,
  "is_match": <true ONLY if score >= 65>,
  "reasoning": "<2 honest sentences. If it's a mismatch, clearly state what specific qualifications or experience are missing>",
  "matched_skills": ["only skills genuinely present in CV that match the role"],
  "missing_skills": ["critical skills the role needs that are absent from the CV"]
}}"""

        msg = client.messages.create(
            model='claude-sonnet-4-20250514',
            max_tokens=400,
            messages=[{'role': 'user', 'content': prompt}]
        )
        return json.loads(msg.content[0].text.strip())

    except Exception as e:
        logger.warning(f"[cv_scanner] Claude match failed ({e}), falling back to keywords")
        return _keyword_match(cv_text, job_title, job_requirements, job_description)


def scan_cv_against_job(
    resume_file_path: str,
    job_title: str,
    job_requirements: str,
    job_description: str = '',
) -> dict:
    """
    Main entry point. Returns:
        score         int 0-100
        is_match      bool
        reasoning     str
        matched_skills list
        missing_skills list
        error         str or None
    """
    cv_text = extract_cv_text(resume_file_path)

    if not cv_text or len(cv_text.strip()) < 50:
        return {
            'score': 0,
            'is_match': False,
            'reasoning': 'We could not read your CV file. Please ensure it is a valid PDF or Word document.',
            'matched_skills': [],
            'missing_skills': [],
            'error': 'cv_unreadable',
        }

    use_claude = bool(os.environ.get('ANTHROPIC_API_KEY'))

    if use_claude:
        result = _claude_match(cv_text, job_title, job_requirements, job_description)
    else:
        result = _keyword_match(cv_text, job_title, job_requirements, job_description)

    result['error'] = None
    return result