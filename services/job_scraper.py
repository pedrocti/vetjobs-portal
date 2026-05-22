"""
services/job_scraper.py
------------------------
Scrapes Nigerian job boards for veteran-relevant roles.
Saves complete job details to the scraped_jobs staging table.

Sources (10 boards):
  1. HotNigerianJobs  — category pages + full detail fetch
  2. JobsInNigeria.careers — RSS feed + full detail fetch
  3. MyJobMag          — category pages + full detail fetch
  4. NaijaHotJobs      — RSS feed
  5. MySalaryScale     — category pages
  6. JobGurus Nigeria  — search pages
  7. Jobzilla Nigeria  — category pages
  8. NigeriaJob.com    — listing pages
  9. DelonJobs         — search pages
 10. WhatJobsNG        — listing pages

Architecture:
  Phase 1 — Collect listing URLs from each source
  Phase 2 — For each URL, fetch the full detail page and extract:
             title, company, location, salary, description,
             requirements, application email/link, deadline
  Phase 3 — Veteran keyword pre-filter → AI score → save to DB
"""

import logging
import hashlib
import time
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Optional

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/120.0.0.0 Safari/537.36'
    ),
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
}

REQUEST_TIMEOUT = 15
POLITE_DELAY    = 1.5   # seconds between requests to same host
DETAIL_DELAY    = 1.0   # seconds between detail page fetches
MAX_PER_SOURCE  = 20    # max listings to fetch details for, per source

VETERAN_KEYWORDS = [
    'security', 'driver', 'logistics', 'operations', 'administrative',
    'hse', 'health safety', 'fleet', 'warehouse', 'supply chain',
    'facility', 'close protection', 'supervisor', 'military',
    'navy', 'army', 'officer', 'guard', 'maritime', 'procurement',
    'transport', 'dispatch', 'enforcement', 'intelligence', 'surveillance',
    'patrol', 'protection', 'safety', 'stevedore', 'marine',
]

def is_veteran_relevant(title: str) -> bool:
    t = title.lower()
    return any(kw in t for kw in VETERAN_KEYWORDS)

def make_external_id(site: str, url: str, title: str = '') -> str:
    raw = f"{site}|{url or title}"
    return hashlib.md5(raw.encode()).hexdigest()

def safe_get(url: str, session: requests.Session) -> Optional[BeautifulSoup]:
    try:
        resp = session.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, 'html.parser')
    except Exception as e:
        logger.warning(f"[scraper] Failed to fetch {url}: {e}")
        return None

def extract_email(text: str) -> Optional[str]:
    """Extract first email address found in text."""
    match = re.search(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}', text)
    return match.group(0) if match else None

def extract_application_info(soup: BeautifulSoup, page_text: str) -> dict:
    """
    Extract application method from a job detail page.
    Returns dict with 'apply_email', 'apply_link', 'apply_text'.
    """
    info = {'apply_email': None, 'apply_link': None, 'apply_text': None}

    # Look for email in full page text
    email = extract_email(page_text)
    if email:
        info['apply_email'] = email

    # Look for apply buttons/links
    apply_patterns = ['apply now', 'apply here', 'click to apply', 'send cv', 'submit application']
    for a in soup.select('a[href]'):
        link_text = a.get_text(strip=True).lower()
        href = a.get('href', '')
        if any(p in link_text for p in apply_patterns):
            if href.startswith('mailto:'):
                info['apply_email'] = href.replace('mailto:', '').split('?')[0]
            elif href.startswith('http'):
                info['apply_link'] = href
            break

    # Build human-readable apply text
    parts = []
    if info['apply_email']:
        parts.append(f"Email: {info['apply_email']}")
    if info['apply_link']:
        parts.append(f"Apply online: {info['apply_link']}")
    if parts:
        info['apply_text'] = ' | '.join(parts)

    return info


# ─────────────────────────────────────────────────────────────
# DETAIL PAGE FETCHER
# Fetches the full job page and extracts complete information.
# Each site has its own extractor because layouts differ.
# ─────────────────────────────────────────────────────────────

def fetch_hnj_detail(url: str, session: requests.Session) -> dict:
    """Fetch full job details from a HotNigerianJobs job page."""
    result = {}
    soup = safe_get(url, session)
    if not soup:
        return result

    page_text = soup.get_text(separator=' ', strip=True)

    # Title
    title_el = soup.select_one('h1, h2.job-title, .entry-title')
    if title_el:
        result['title'] = title_el.get_text(strip=True)

    # Company — usually in the first paragraph or a span
    company_el = soup.select_one('.company-name, [class*="company"]')
    if not company_el:
        # HNJ embeds company name in the post body — try to extract from first lines
        body = soup.select_one('.entry-content, .post-content, article')
        if body:
            lines = body.get_text(separator='\n', strip=True).split('\n')
            for line in lines[:5]:
                if 'recruiting' in line.lower() or 'limited' in line.lower() or 'plc' in line.lower():
                    result['company_name'] = line[:150]
                    break
    else:
        result['company_name'] = company_el.get_text(strip=True)

    # Location
    loc_el = soup.select_one('[class*="location"], [class*="Location"]')
    if loc_el:
        result['location'] = loc_el.get_text(strip=True)
    else:
        # Try to find "located in X" pattern
        loc_match = re.search(r'located in ([^.]+)', page_text, re.IGNORECASE)
        if loc_match:
            result['location'] = loc_match.group(1).strip()[:100]

    # Salary
    salary_match = re.search(
        r'(salary|remuneration|pay)[:\s]*([\u20a6N][\d,]+|[\d,]+\s*(?:per|monthly|annually))',
        page_text, re.IGNORECASE
    )
    if salary_match:
        result['salary_info'] = salary_match.group(0)[:100]

    # Full description — the main body
    body_el = soup.select_one('.entry-content, .post-content, .job-description, article')
    if body_el:
        result['description'] = body_el.get_text(separator='\n', strip=True)[:3000]

    # Requirements — look for requirements/qualifications section
    req_match = re.search(
        r'(requirements?|qualifications?|criteria)[:\s\n]+(.*?)(?=\n\n|\Z)',
        page_text, re.IGNORECASE | re.DOTALL
    )
    if req_match:
        result['requirements'] = req_match.group(0)[:1500]

    # Deadline
    deadline_match = re.search(
        r'(deadline|closing date|apply before|applications? close)[:\s]*([^\n.]{5,50})',
        page_text, re.IGNORECASE
    )
    if deadline_match:
        result['deadline'] = deadline_match.group(2).strip()

    # Application info
    apply_info = extract_application_info(soup, page_text)
    result.update(apply_info)

    return result


def fetch_generic_detail(url: str, session: requests.Session, source_site: str) -> dict:
    """
    Generic detail page fetcher for sites without custom extractors.
    Extracts as much as possible using common patterns.
    """
    result = {}
    soup = safe_get(url, session)
    if not soup:
        return result

    page_text = soup.get_text(separator=' ', strip=True)

    # Title
    for sel in ['h1', 'h1.job-title', '.job-title h1', 'h2.entry-title']:
        el = soup.select_one(sel)
        if el:
            result['title'] = el.get_text(strip=True)
            break

    # Company
    for sel in ['.company-name', '[class*="company"]', '[itemprop="hiringOrganization"]']:
        el = soup.select_one(sel)
        if el:
            result['company_name'] = el.get_text(strip=True)[:200]
            break

    # Location
    for sel in ['.job-location', '[class*="location"]', '[itemprop="jobLocation"]']:
        el = soup.select_one(sel)
        if el:
            result['location'] = el.get_text(strip=True)[:200]
            break

    # Salary
    salary_match = re.search(
        r'(salary|remuneration|pay)[:\s]*([\u20a6N][\d,]+[\w\s]*|[\d,]+\s*(?:per|monthly|annually)[\w\s]*)',
        page_text, re.IGNORECASE
    )
    if salary_match:
        result['salary_info'] = salary_match.group(0)[:150]

    # Main content
    for sel in ['.job-description', '.entry-content', '.post-content', 'article', 'main', '.content']:
        el = soup.select_one(sel)
        if el and len(el.get_text(strip=True)) > 100:
            result['description'] = el.get_text(separator='\n', strip=True)[:3000]
            break

    # Requirements section
    req_match = re.search(
        r'(requirements?|qualifications?|what we need|criteria)[:\s\n]+(.*?)(?=\n\s*\n|\Z)',
        page_text, re.IGNORECASE | re.DOTALL
    )
    if req_match:
        result['requirements'] = req_match.group(0)[:1500]

    # Deadline
    deadline_match = re.search(
        r'(deadline|closing date|apply before|applications? close)[:\s]*([^\n.]{5,60})',
        page_text, re.IGNORECASE
    )
    if deadline_match:
        result['deadline'] = deadline_match.group(2).strip()

    # Application info
    apply_info = extract_application_info(soup, page_text)
    result.update(apply_info)

    return result


# ─────────────────────────────────────────────────────────────
# SOURCE 1: HOT NIGERIAN JOBS
# Category pages + full detail fetch per job
# ─────────────────────────────────────────────────────────────

HNJ_CATEGORIES = [
    ('Security Services',   'https://www.hotnigerianjobs.com/field/253/'),
    ('Driving Services',    'https://www.hotnigerianjobs.com/field/218/'),
    ('HSE / Safety',        'https://www.hotnigerianjobs.com/field/232/'),
    ('Logistics & Supply',  'https://www.hotnigerianjobs.com/field/242/'),
    ('Facility Management', 'https://www.hotnigerianjobs.com/field/227/'),
    ('Administration',      'https://www.hotnigerianjobs.com/field/201/'),
    ('Logistics Transport', 'https://www.hotnigerianjobs.com/industry/123/'),
    ('Maritime Services',   'https://www.hotnigerianjobs.com/field/244/'),
    ('Security Industry',   'https://www.hotnigerianjobs.com/industry/132/'),
    ('Law Enforcement',     'https://www.hotnigerianjobs.com/field/253/'),
]

def scrape_hotnigerianjobs(session: requests.Session) -> list[dict]:
    listings = []
    seen_urls = set()

    for category_name, cat_url in HNJ_CATEGORIES:
        soup = safe_get(cat_url, session)
        if not soup:
            time.sleep(POLITE_DELAY)
            continue

        job_links = soup.select('a[href*="/hotjobs/"]')
        count = 0
        for link in job_links:
            href  = link.get('href', '')
            title = link.get_text(strip=True)
            if not href or not title or href in seen_urls or len(title) < 5:
                continue
            if not href.startswith('http'):
                href = f"https://www.hotnigerianjobs.com{href}"
            seen_urls.add(href)
            listings.append({
                'url': href, 'title': title,
                'category': category_name,
                'source_site': 'HotNigerianJobs',
            })
            count += 1
            if count >= MAX_PER_SOURCE:
                break

        logger.info(f"[hotnigerianjobs] {category_name} → {count} listings found")
        time.sleep(POLITE_DELAY)

    # Fetch details for veteran-relevant listings
    results = []
    for listing in listings:
        if not is_veteran_relevant(listing['title']):
            continue
        time.sleep(DETAIL_DELAY)
        detail = fetch_hnj_detail(listing['url'], session)
        title = detail.get('title') or listing['title']
        results.append({
            'source_site':  'HotNigerianJobs',
            'source_url':   listing['url'],
            'external_id':  make_external_id('hotnigerianjobs', listing['url']),
            'title':        title,
            'company_name': detail.get('company_name'),
            'location':     detail.get('location', 'Nigeria'),
            'job_type':     'full-time',
            'salary_info':  detail.get('salary_info'),
            'description':  detail.get('description', f"Category: {listing['category']}"),
            'requirements': detail.get('requirements', ''),
            'apply_email':  detail.get('apply_email'),
            'apply_link':   detail.get('apply_link'),
            'apply_text':   detail.get('apply_text'),
            'deadline':     detail.get('deadline'),
        })

    logger.info(f"[hotnigerianjobs] Total with full details: {len(results)}")
    return results


# ─────────────────────────────────────────────────────────────
# SOURCE 2: JOBSINNIGERIA.CAREERS — RSS + detail fetch
# ─────────────────────────────────────────────────────────────

def scrape_jobsinnigeria(session: requests.Session) -> list[dict]:
    results = []
    url = 'https://jobsinnigeria.careers/feed/?post_type=job_listing'

    try:
        resp = session.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
        channel = root.find('channel')
        if not channel:
            return results

        items = channel.findall('item')
        for item in items[:30]:
            title = (item.findtext('title') or '').strip()
            link  = (item.findtext('link')  or '').strip()
            if not title or not link or not is_veteran_relevant(title):
                continue

            time.sleep(DETAIL_DELAY)
            detail = fetch_generic_detail(link, session, 'JobsInNigeria')

            results.append({
                'source_site':  'JobsInNigeria',
                'source_url':   link,
                'external_id':  make_external_id('jobsinnigeria', link),
                'title':        detail.get('title') or title,
                'company_name': detail.get('company_name'),
                'location':     detail.get('location', 'Nigeria'),
                'job_type':     'full-time',
                'salary_info':  detail.get('salary_info'),
                'description':  detail.get('description', ''),
                'requirements': detail.get('requirements', ''),
                'apply_email':  detail.get('apply_email'),
                'apply_link':   detail.get('apply_link'),
                'apply_text':   detail.get('apply_text'),
                'deadline':     detail.get('deadline'),
            })

    except Exception as e:
        logger.warning(f"[jobsinnigeria] RSS fetch failed: {e}")

    logger.info(f"[jobsinnigeria] → {len(results)} results with full details")
    return results


# ─────────────────────────────────────────────────────────────
# SOURCE 3: MYJOBMAG — category pages + detail fetch
# ─────────────────────────────────────────────────────────────

MYJOBMAG_CATEGORIES = [
    ('Security',        'https://www.myjobmag.com/jobs-by-field/security'),
    ('Driving',         'https://www.myjobmag.com/jobs-by-field/transportation-driving'),
    ('Logistics',       'https://www.myjobmag.com/jobs-by-field/logistics-supply-chain'),
    ('HSE',             'https://www.myjobmag.com/jobs-by-field/safety-and-environment-hse'),
    ('Operations',      'https://www.myjobmag.com/jobs-by-field/management'),
    ('Admin',           'https://www.myjobmag.com/jobs-by-field/administration-office-management'),
    ('Engineering',     'https://www.myjobmag.com/jobs-by-field/engineering-technical'),
]

def scrape_myjobmag(session: requests.Session) -> list[dict]:
    results = []
    seen_urls = set()

    for category_name, cat_url in MYJOBMAG_CATEGORIES:
        soup = safe_get(cat_url, session)
        if not soup:
            time.sleep(POLITE_DELAY)
            continue

        # MyJobMag uses /job/NNNNN/ style links
        job_links = soup.select('a[href*="/job/"]')
        if not job_links:
            # fallback: any link with job-like path
            job_links = soup.select('h2 a, h3 a, .job-title a')

        count = 0
        for link in job_links[:MAX_PER_SOURCE]:
            href  = link.get('href', '')
            title = link.get_text(strip=True)
            if not href or not title or href in seen_urls or len(title) < 5:
                continue
            if not href.startswith('http'):
                href = f"https://www.myjobmag.com{href}"
            if not is_veteran_relevant(title):
                continue
            seen_urls.add(href)

            time.sleep(DETAIL_DELAY)
            detail = fetch_generic_detail(href, session, 'MyJobMag')

            results.append({
                'source_site':  'MyJobMag',
                'source_url':   href,
                'external_id':  make_external_id('myjobmag', href),
                'title':        detail.get('title') or title,
                'company_name': detail.get('company_name'),
                'location':     detail.get('location', 'Nigeria'),
                'job_type':     'full-time',
                'salary_info':  detail.get('salary_info'),
                'description':  detail.get('description', f"Category: {category_name}"),
                'requirements': detail.get('requirements', ''),
                'apply_email':  detail.get('apply_email'),
                'apply_link':   detail.get('apply_link'),
                'apply_text':   detail.get('apply_text'),
                'deadline':     detail.get('deadline'),
            })
            count += 1

        logger.info(f"[myjobmag] {category_name} → {count} results with details")
        time.sleep(POLITE_DELAY)

    return results


# ─────────────────────────────────────────────────────────────
# SOURCE 4: NAIJAHOTJOBS — RSS feed + detail fetch
# ─────────────────────────────────────────────────────────────

def scrape_naijahotjobs(session: requests.Session) -> list[dict]:
    results = []
    rss_url = 'https://www.naijahotjobs.com/feed/'

    try:
        resp = session.get(rss_url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
        channel = root.find('channel')
        if not channel:
            return results

        for item in channel.findall('item')[:30]:
            title = (item.findtext('title') or '').strip()
            link  = (item.findtext('link')  or '').strip()
            if not title or not link or not is_veteran_relevant(title):
                continue

            time.sleep(DETAIL_DELAY)
            detail = fetch_generic_detail(link, session, 'NaijaHotJobs')

            results.append({
                'source_site':  'NaijaHotJobs',
                'source_url':   link,
                'external_id':  make_external_id('naijahotjobs', link),
                'title':        detail.get('title') or title,
                'company_name': detail.get('company_name'),
                'location':     detail.get('location', 'Nigeria'),
                'job_type':     'full-time',
                'salary_info':  detail.get('salary_info'),
                'description':  detail.get('description', ''),
                'requirements': detail.get('requirements', ''),
                'apply_email':  detail.get('apply_email'),
                'apply_link':   detail.get('apply_link'),
                'apply_text':   detail.get('apply_text'),
                'deadline':     detail.get('deadline'),
            })

    except Exception as e:
        logger.warning(f"[naijahotjobs] RSS failed: {e}")

    logger.info(f"[naijahotjobs] → {len(results)} results")
    return results


# ─────────────────────────────────────────────────────────────
# SOURCE 5: MYSALARYSCALE — search pages
# ─────────────────────────────────────────────────────────────

MYSALARYSCALE_URLS = [
    'https://mysalaryscale.com/jobs/?s=security+officer',
    'https://mysalaryscale.com/jobs/?s=logistics+officer',
    'https://mysalaryscale.com/jobs/?s=hse+officer',
    'https://mysalaryscale.com/jobs/?s=driver',
    'https://mysalaryscale.com/jobs/?s=operations+officer',
]

def scrape_mysalaryscale(session: requests.Session) -> list[dict]:
    results = []
    seen_urls = set()

    for search_url in MYSALARYSCALE_URLS:
        soup = safe_get(search_url, session)
        if not soup:
            time.sleep(POLITE_DELAY)
            continue

        for link in soup.select('h2 a, h3 a, article a, .job-title a')[:10]:
            href  = link.get('href', '')
            title = link.get_text(strip=True)
            if not href or not title or href in seen_urls or len(title) < 5:
                continue
            if not is_veteran_relevant(title):
                continue
            seen_urls.add(href)

            time.sleep(DETAIL_DELAY)
            detail = fetch_generic_detail(href, session, 'MySalaryScale')

            results.append({
                'source_site':  'MySalaryScale',
                'source_url':   href,
                'external_id':  make_external_id('mysalaryscale', href),
                'title':        detail.get('title') or title,
                'company_name': detail.get('company_name'),
                'location':     detail.get('location', 'Nigeria'),
                'job_type':     'full-time',
                'salary_info':  detail.get('salary_info'),
                'description':  detail.get('description', ''),
                'requirements': detail.get('requirements', ''),
                'apply_email':  detail.get('apply_email'),
                'apply_link':   detail.get('apply_link'),
                'apply_text':   detail.get('apply_text'),
                'deadline':     detail.get('deadline'),
            })

        time.sleep(POLITE_DELAY)

    logger.info(f"[mysalaryscale] → {len(results)} results")
    return results


# ─────────────────────────────────────────────────────────────
# SOURCE 6: JOBGURUS NIGERIA
# ─────────────────────────────────────────────────────────────

JOBGURUS_URLS = [
    'https://www.jobgurus.com.ng/search?q=security+officer&l=Nigeria',
    'https://www.jobgurus.com.ng/search?q=driver&l=Nigeria',
    'https://www.jobgurus.com.ng/search?q=logistics+officer&l=Nigeria',
    'https://www.jobgurus.com.ng/search?q=hse+officer&l=Nigeria',
]

def scrape_jobgurus(session: requests.Session) -> list[dict]:
    results = []
    seen_urls = set()

    for search_url in JOBGURUS_URLS:
        soup = safe_get(search_url, session)
        if not soup:
            time.sleep(POLITE_DELAY)
            continue

        for link in soup.select('h2 a, h3 a, .job-title a, a[href*="/job/"]')[:10]:
            href  = link.get('href', '')
            title = link.get_text(strip=True)
            if not href or not title or href in seen_urls or len(title) < 5:
                continue
            if not href.startswith('http'):
                href = f"https://www.jobgurus.com.ng{href}"
            seen_urls.add(href)

            time.sleep(DETAIL_DELAY)
            detail = fetch_generic_detail(href, session, 'JobGurus')

            results.append({
                'source_site':  'JobGurus',
                'source_url':   href,
                'external_id':  make_external_id('jobgurus', href),
                'title':        detail.get('title') or title,
                'company_name': detail.get('company_name'),
                'location':     detail.get('location', 'Nigeria'),
                'job_type':     'full-time',
                'salary_info':  detail.get('salary_info'),
                'description':  detail.get('description', ''),
                'requirements': detail.get('requirements', ''),
                'apply_email':  detail.get('apply_email'),
                'apply_link':   detail.get('apply_link'),
                'apply_text':   detail.get('apply_text'),
                'deadline':     detail.get('deadline'),
            })

        time.sleep(POLITE_DELAY)

    logger.info(f"[jobgurus] → {len(results)} results")
    return results


# ─────────────────────────────────────────────────────────────
# SOURCE 7: NIGERIAJOB.COM
# ─────────────────────────────────────────────────────────────

def scrape_nigeriajob(session: requests.Session) -> list[dict]:
    results = []
    soup = safe_get('https://www.nigeriajob.com/', session)
    if not soup:
        return results

    seen_urls = set()
    for link in soup.select('a[href*="nigeriajob.com"]')[:30]:
        title = link.get_text(strip=True)
        href  = link.get('href', '')
        if not title or len(title) < 15 or href in seen_urls:
            continue
        if not is_veteran_relevant(title):
            continue
        seen_urls.add(href)

        time.sleep(DETAIL_DELAY)
        detail = fetch_generic_detail(href, session, 'NigeriaJob')

        results.append({
            'source_site':  'NigeriaJob',
            'source_url':   href,
            'external_id':  make_external_id('nigeriajob', href),
            'title':        detail.get('title') or title,
            'company_name': detail.get('company_name'),
            'location':     detail.get('location', 'Nigeria'),
            'job_type':     'full-time',
            'salary_info':  detail.get('salary_info'),
            'description':  detail.get('description', ''),
            'requirements': detail.get('requirements', ''),
            'apply_email':  detail.get('apply_email'),
            'apply_link':   detail.get('apply_link'),
            'apply_text':   detail.get('apply_text'),
            'deadline':     detail.get('deadline'),
        })

    logger.info(f"[nigeriajob] → {len(results)} results")
    return results


# ─────────────────────────────────────────────────────────────
# SOURCE 8: DELONJOBS
# ─────────────────────────────────────────────────────────────

DELONJOBS_URLS = [
    'https://jobs.delon.ng/?s=security',
    'https://jobs.delon.ng/?s=logistics',
    'https://jobs.delon.ng/?s=driver',
    'https://jobs.delon.ng/?s=operations',
]

def scrape_delonjobs(session: requests.Session) -> list[dict]:
    results = []
    seen_urls = set()

    for search_url in DELONJOBS_URLS:
        soup = safe_get(search_url, session)
        if not soup:
            time.sleep(POLITE_DELAY)
            continue

        for link in soup.select('h2 a, h3 a, .job_listing-clickbox, a[href*="jobs.delon.ng/"]')[:10]:
            href  = link.get('href', '')
            title = link.get_text(strip=True)
            if not href or not title or href in seen_urls or len(title) < 5:
                continue
            if not is_veteran_relevant(title):
                continue
            seen_urls.add(href)

            time.sleep(DETAIL_DELAY)
            detail = fetch_generic_detail(href, session, 'DelonJobs')

            results.append({
                'source_site':  'DelonJobs',
                'source_url':   href,
                'external_id':  make_external_id('delonjobs', href),
                'title':        detail.get('title') or title,
                'company_name': detail.get('company_name'),
                'location':     detail.get('location', 'Nigeria'),
                'job_type':     'full-time',
                'salary_info':  detail.get('salary_info'),
                'description':  detail.get('description', ''),
                'requirements': detail.get('requirements', ''),
                'apply_email':  detail.get('apply_email'),
                'apply_link':   detail.get('apply_link'),
                'apply_text':   detail.get('apply_text'),
                'deadline':     detail.get('deadline'),
            })

        time.sleep(POLITE_DELAY)

    logger.info(f"[delonjobs] → {len(results)} results")
    return results


# ─────────────────────────────────────────────────────────────
# SOURCE 9: NAIJAJOBPORTAL.COM.NG
# ─────────────────────────────────────────────────────────────

def scrape_naijajobportal(session: requests.Session) -> list[dict]:
    results = []
    seen_urls = set()

    search_urls = [
        'https://www.naijajobportal.com.ng/?s=security',
        'https://www.naijajobportal.com.ng/?s=logistics',
        'https://www.naijajobportal.com.ng/?s=driver',
        'https://www.naijajobportal.com.ng/?s=hse',
    ]

    for search_url in search_urls:
        soup = safe_get(search_url, session)
        if not soup:
            time.sleep(POLITE_DELAY)
            continue

        for link in soup.select('h2 a, h3 a, article a, a[href*="naijajobportal"]')[:10]:
            href  = link.get('href', '')
            title = link.get_text(strip=True)
            if not href or not title or href in seen_urls or len(title) < 5:
                continue
            if not is_veteran_relevant(title):
                continue
            seen_urls.add(href)

            time.sleep(DETAIL_DELAY)
            detail = fetch_generic_detail(href, session, 'NaijaJobPortal')

            results.append({
                'source_site':  'NaijaJobPortal',
                'source_url':   href,
                'external_id':  make_external_id('naijajobportal', href),
                'title':        detail.get('title') or title,
                'company_name': detail.get('company_name'),
                'location':     detail.get('location', 'Nigeria'),
                'job_type':     'full-time',
                'salary_info':  detail.get('salary_info'),
                'description':  detail.get('description', ''),
                'requirements': detail.get('requirements', ''),
                'apply_email':  detail.get('apply_email'),
                'apply_link':   detail.get('apply_link'),
                'apply_text':   detail.get('apply_text'),
                'deadline':     detail.get('deadline'),
            })

        time.sleep(POLITE_DELAY)

    logger.info(f"[naijajobportal] → {len(results)} results")
    return results


# ─────────────────────────────────────────────────────────────
# MAIN SCRAPE RUNNER
# ─────────────────────────────────────────────────────────────

ALL_SCRAPERS = [
    ('HotNigerianJobs',  scrape_hotnigerianjobs),
    ('JobsInNigeria',    scrape_jobsinnigeria),
    ('MyJobMag',         scrape_myjobmag),
    ('NaijaHotJobs',     scrape_naijahotjobs),
    ('MySalaryScale',    scrape_mysalaryscale),
    ('JobGurus',         scrape_jobgurus),
    ('NigeriaJob',       scrape_nigeriajob),
    ('DelonJobs',        scrape_delonjobs),
    ('NaijaJobPortal',   scrape_naijajobportal),
]


def run_full_scrape(flask_app=None) -> dict:
    """
    Run all scrapers. Each returns jobs with full details already fetched.
    AI-score survivors. Save to scraped_jobs staging table.
    """
    from services.ai_filter import score_job

    ctx = None
    if flask_app:
        ctx = flask_app.app_context()
        ctx.push()

    try:
        from extensions import db
        from models.scraped_job import ScrapedJob

        session = requests.Session()
        session.headers.update(HEADERS)

        total_found   = 0
        total_saved   = 0
        total_skipped = 0
        errors        = []
        all_raw       = []

        for scraper_name, scraper_fn in ALL_SCRAPERS:
            try:
                raw = scraper_fn(session)
                all_raw.extend(raw)
                logger.info(f"[scraper] {scraper_name} contributed {len(raw)} jobs")
            except Exception as e:
                msg = f"[{scraper_name}] scraper error: {e}"
                logger.error(msg)
                errors.append(msg)

        logger.info(f"[scraper] Total collected across all sources: {len(all_raw)}")

        for raw in all_raw:
            total_found += 1

            # Already veteran-filtered at collection time, but double-check
            if not is_veteran_relevant(raw.get('title', '')):
                total_skipped += 1
                continue

            # Deduplication
            existing = ScrapedJob.query.filter_by(
                source_site=raw['source_site'],
                external_id=raw['external_id']
            ).first()
            if existing:
                total_skipped += 1
                continue

            # AI scoring
            try:
                score_result = score_job(
                    title=raw.get('title', ''),
                    description=raw.get('description', ''),
                    requirements=raw.get('requirements', ''),
                )
            except Exception as e:
                logger.warning(f"[scraper] AI score failed for '{raw.get('title')}': {e}")
                score_result = {
                    'score': 50, 'category': 'General',
                    'reasoning': 'AI scoring unavailable',
                    'is_remote': False, 'is_veteran_relevant': True,
                }

            if score_result['score'] < 15:
                total_skipped += 1
                continue

            # Build description with application info appended
            description = raw.get('description', '')
            if raw.get('apply_text'):
                description += f"\n\n--- HOW TO APPLY ---\n{raw['apply_text']}"
            if raw.get('deadline'):
                description += f"\n\nApplication Deadline: {raw['deadline']}"

            job = ScrapedJob(
                source_site         = raw['source_site'],
                source_url          = raw.get('source_url'),
                external_id         = raw['external_id'],
                title               = raw.get('title', 'Untitled'),
                company_name        = raw.get('company_name'),
                location            = raw.get('location', 'Nigeria'),
                job_type            = raw.get('job_type', 'full-time'),
                description         = description[:5000],
                requirements        = raw.get('requirements', '')[:2000],
                salary_info         = raw.get('salary_info'),
                ai_score            = score_result['score'],
                ai_category         = score_result['category'],
                ai_reasoning        = score_result['reasoning'],
                is_remote           = score_result['is_remote'],
                is_veteran_relevant = score_result['is_veteran_relevant'],
                status              = 'pending',
                scraped_at          = datetime.utcnow(),
            )
            db.session.add(job)
            total_saved += 1

        db.session.commit()

        summary = {
            'found':   total_found,
            'saved':   total_saved,
            'skipped': total_skipped,
            'errors':  errors,
            'ran_at':  datetime.utcnow().isoformat(),
        }
        logger.info(f"[scraper] Run complete: {summary}")
        return summary

    except Exception as e:
        logger.error(f"[scraper] Fatal error: {e}")
        try:
            from extensions import db
            db.session.rollback()
        except Exception:
            pass
        return {'error': str(e)}

    finally:
        if ctx:
            ctx.pop()
