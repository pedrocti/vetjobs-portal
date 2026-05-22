"""
services/job_formatter.py
--------------------------
Parses raw scraped job text into clean structured sections
before a ScrapedJob is approved and posted as a real JobPosting.
"""

import re
from datetime import datetime
from typing import Optional

DESCRIPTION_HEADERS = [
    r'job\s*summary', r'role\s*overview', r'about\s*the\s*role',
    r'position\s*summary', r'overview', r'about\s*the\s*job',
    r'responsibilities', r'key\s*responsibilities', r'duties',
    r'what\s*you\s*will\s*do', r'your\s*role', r'job\s*description',
    r'the\s*role', r'scope\s*of\s*work', r'job\s*functions?',
]

REQUIREMENTS_HEADERS = [
    r'requirements?', r'qualifications?', r'what\s*we\s*need',
    r'who\s*we\s*are\s*looking\s*for', r'ideal\s*candidate',
    r'skills?\s*(?:and\s*)?(?:experience)?', r'criteria',
    r'experience\s*required', r'minimum\s*qualifications?',
    r'candidate\s*profile', r'person\s*specification',
]

BENEFITS_HEADERS = [
    r'what\s*we\s*offer', r'benefits?', r'perks?', r'compensation',
    r'why\s*join\s*us', r'we\s*offer', r'remuneration',
    r'salary\s*and\s*benefits', r'package',
]

APPLY_HEADERS = [
    r'how\s*to\s*apply', r'application\s*(?:method|process|procedure)',
    r'to\s*apply', r'interested\s*candidates?\s*should',
    r'send\s*(?:your\s*)?(?:cv|resume)', r'apply\s*(?:now|here|via)',
    r'method\s*of\s*application', r'application\s*instruction',
]

CATEGORY_TO_INDUSTRY = {
    'Security':       'Security Services',
    'Driver':         'Logistics & Transportation',
    'Logistics':      'Logistics & Transportation',
    'Operations':     'Operations & Management',
    'Admin':          'Administration',
    'Health':         'Healthcare',
    'Health & Safety': 'HSE / Health & Safety',
    'Engineering':    'Engineering & Technical',
    'IT':             'Information Technology',
    'Remote':         'General',
    'General':        'General',
}


def _clean_text(text: str) -> str:
    noise = [
        r'The post .+? appeared first on .+?\.', r'Copyright © \d{4}\.?',
        r'Subscribe to Job Alert[^\n]*', r'HNJ EXCLUSIVE[^\n]*',
        r'\[…\]', r'Category:\s*\w+[\w\s]*',
        r'Click here to apply[^\n]*', r'Jobs in Nigeria[^\n]*',
    ]
    for pat in noise:
        text = re.sub(pat, '', text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def _make_pattern(headers):
    joined = '|'.join(headers)
    return re.compile(
        rf'(?:^|\n)\s*(?:{joined})\s*[:\-–]?\s*\n',
        re.IGNORECASE | re.MULTILINE
    )


def _split_sections(text: str) -> dict:
    patterns = {
        'description': _make_pattern(DESCRIPTION_HEADERS),
        'requirements': _make_pattern(REQUIREMENTS_HEADERS),
        'benefits': _make_pattern(BENEFITS_HEADERS),
        'apply': _make_pattern(APPLY_HEADERS),
    }
    found = []
    for name, pat in patterns.items():
        for m in pat.finditer(text):
            found.append((m.start(), m.end(), name))
    found.sort(key=lambda x: x[0])

    if not found:
        return {'body': text}

    sections = {}
    for i, (start, end, name) in enumerate(found):
        next_start = found[i + 1][0] if i + 1 < len(found) else len(text)
        content = text[end:next_start].strip()
        sections[name] = sections.get(name, '') + ('\n' + content if name in sections else content)

    if found[0][0] > 50:
        sections['body'] = text[:found[0][0]].strip()

    return sections


def _extract_salary(text: str):
    t = text.replace(',', '').replace('₦', 'N').replace('NGN', 'N')
    range_m = re.search(r'N?\s*(\d{4,8})\s*(?:[-–]|to)\s*N?\s*(\d{4,8})', t, re.IGNORECASE)
    if range_m:
        lo, hi = int(range_m.group(1)), int(range_m.group(2))
        return min(lo, hi), max(lo, hi)
    single_m = re.search(r'N?\s*(\d{4,8})', t, re.IGNORECASE)
    if single_m:
        v = int(single_m.group(1))
        return v, v
    return None, None


def _extract_experience(text: str) -> Optional[str]:
    t = text.lower()
    if any(k in t for k in ['entry level', 'no experience', '0 year', 'nysc', 'fresh graduate']):
        return 'Entry Level'
    if any(k in t for k in ['1 year', '2 year', '1-2', '2-3', 'junior']):
        return 'Junior'
    if any(k in t for k in ['3 year', '4 year', '5 year', '3-5', '3 - 5', 'mid level', 'mid-level']):
        return 'Mid Level'
    if any(k in t for k in ['senior', '5+', '7 year', '10 year', '6 year', 'managerial']):
        return 'Senior'
    return None


def _extract_deadline(text: str) -> Optional[datetime]:
    patterns = [
        r'deadline[:\s]+([^\n]{5,60})',
        r'closing\s*date[:\s]+([^\n]{5,60})',
        r'apply\s*(?:on\s*or\s*)?before[:\s]+([^\n]{5,60})',
        r'application(?:s)?\s*close[:\s]+([^\n]{5,60})',
    ]
    date_formats = [
        '%d %B %Y', '%d %b %Y', '%B %d, %Y', '%b %d, %Y',
        '%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y',
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            raw = m.group(1).strip()[:60]
            # Clean common trailing noise
            raw = re.sub(r'[\.\,].*$', '', raw).strip()
            for fmt in date_formats:
                try:
                    return datetime.strptime(raw, fmt)
                except ValueError:
                    continue
    return None


def _extract_email(text: str) -> Optional[str]:
    m = re.search(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}', text)
    return m.group(0) if m else None


def _extract_apply_url(text: str) -> Optional[str]:
    # Look for apply links — prefer links with apply/career/job in URL
    matches = re.findall(r'https?://[^\s<>"\']{10,}', text)
    for url in matches:
        url = url.rstrip('.,)')
        if any(k in url.lower() for k in ['apply', 'career', 'job', 'recruit', 'vacancy']):
            return url
    return matches[0].rstrip('.,)') if matches else None


def format_scraped_job(scraped) -> dict:
    """
    Takes a ScrapedJob ORM object.
    Returns structured dict ready for JobPosting creation.
    """
    raw_desc = _clean_text(scraped.description or '')
    raw_req  = _clean_text(scraped.requirements or '')
    salary_raw = scraped.salary_info or ''
    ai_category = scraped.ai_category or 'General'

    full_text = raw_desc + '\n' + raw_req
    sections = _split_sections(raw_desc)

    # ── DESCRIPTION ──────────────────────────────────────────
    parts = []

    body = sections.get('body', '').strip()
    if body and len(body) > 30:
        parts.append(body)

    resp = sections.get('description', '').strip()
    if resp and len(resp) > 20:
        parts.append('<strong>Key Responsibilities</strong>\n' + resp)

    benefits = sections.get('benefits', '').strip()
    if benefits and len(benefits) > 10:
        parts.append('<strong>What We Offer</strong>\n' + benefits)

    # Apply info in description
    apply_section = sections.get('apply', '').strip()
    if apply_section and len(apply_section) > 10:
        parts.append('<strong>How to Apply</strong>\n' + apply_section)

    if scraped.source_url:
        parts.append(
            f'<em>Originally posted on {scraped.source_site}. '
            f'<a href="{scraped.source_url}" target="_blank" rel="noopener">View original posting</a></em>'
        )

    clean_description = '\n\n'.join(parts).strip()

    if not clean_description or len(clean_description) < 60:
        company = scraped.company_name or 'a Nigerian employer'
        location = scraped.location or 'Nigeria'
        clean_description = (
            f"<strong>{scraped.title}</strong>\n\n"
            f"{company} is recruiting for this role in {location}.\n\n"
            f"This is a veteran-friendly position suitable for ex-military personnel "
            f"with relevant background and experience.\n\n"
            f'<em><a href="{scraped.source_url or "#"}" target="_blank" rel="noopener">'
            f'View full details on {scraped.source_site}</a></em>'
        )

    # ── REQUIREMENTS ─────────────────────────────────────────
    req_parts = []

    parsed_reqs = sections.get('requirements', '').strip()
    if parsed_reqs and len(parsed_reqs) > 20:
        req_parts.append(parsed_reqs)

    if raw_req and len(raw_req) > 20:
        cleaned = re.sub(r'^requirements?\s*[:\-–]\s*', '', raw_req, flags=re.IGNORECASE).strip()
        if cleaned and cleaned not in (parsed_reqs or ''):
            req_parts.append(cleaned)

    clean_requirements = '\n\n'.join(req_parts).strip()

    if not clean_requirements or len(clean_requirements) < 20:
        clean_requirements = (
            "• Candidates with military or paramilitary background are strongly encouraged to apply.\n"
            "• Relevant experience in a similar role required.\n"
            "• OND / HND / B.Sc in a relevant discipline (or equivalent military training).\n"
            "• Good communication, leadership, and teamwork skills."
        )

    # ── HOW TO APPLY ─────────────────────────────────────────
    # Extract apply email
    apply_email = None
    apply_url = None

    # Check apply section first
    if apply_section:
        apply_email = _extract_email(apply_section)
        if not apply_email:
            apply_url = _extract_apply_url(apply_section)

    # Fall back to full text scan
    if not apply_email and not apply_url:
        apply_email = _extract_email(full_text)
    if not apply_url and not apply_email:
        apply_url = _extract_apply_url(full_text)

    # Build how_to_apply text
    how_to_apply_parts = []
    if apply_section:
        how_to_apply_parts.append(apply_section)
    if apply_email and apply_email not in (apply_section or ''):
        how_to_apply_parts.append(f"Send your CV to: {apply_email}")
    if apply_url and apply_url not in (apply_section or ''):
        how_to_apply_parts.append(f"Apply online: {apply_url}")

    how_to_apply = '\n'.join(how_to_apply_parts).strip() or None

    # ── SALARY ───────────────────────────────────────────────
    salary_min, salary_max = _extract_salary(salary_raw + ' ' + full_text)

    # ── OTHER FIELDS ─────────────────────────────────────────
    industry        = CATEGORY_TO_INDUSTRY.get(ai_category, 'General')
    experience_level = _extract_experience(full_text)
    deadline        = _extract_deadline(full_text)

    return {
        'description':      clean_description,
        'requirements':     clean_requirements,
        'how_to_apply':     how_to_apply,
        'apply_email':      apply_email,
        'external_apply_url': apply_url,
        'salary_min':       salary_min,
        'salary_max':       salary_max,
        'industry':         industry,
        'experience_level': experience_level,
        'deadline':         deadline,
    }