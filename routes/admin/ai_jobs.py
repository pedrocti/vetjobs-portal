import logging
from datetime import datetime

from flask import (
    Blueprint, render_template, request, redirect,
    url_for, flash, jsonify, current_app
)
from flask_login import login_required, current_user

from extensions import db
from models.scraped_job import ScrapedJob
from models.profile_veteran import VeteranProfile
from models.jobpost import JobPosting

logger = logging.getLogger(__name__)

ai_jobs_bp = Blueprint('ai_jobs', __name__, url_prefix='/admin/ai-jobs')

ADMIN_POSTED_BY = 4


def _require_admin():
    if not current_user.is_admin():
        flash('Access denied.', 'error')
        return redirect(url_for('main.index'))
    return None


@ai_jobs_bp.route('/')
@login_required
def dashboard():
    gate = _require_admin()
    if gate:
        return gate

    tab    = request.args.get('tab', 'pending')
    page   = request.args.get('page', 1, type=int)
    source = request.args.get('source', '')
    cat    = request.args.get('category', '')

    query = ScrapedJob.query

    if tab in ('pending', 'approved', 'rejected'):
        query = query.filter_by(status=tab)
    if source:
        query = query.filter_by(source_site=source)
    if cat:
        query = query.filter_by(ai_category=cat)

    jobs = query.order_by(
        ScrapedJob.ai_score.desc(),
        ScrapedJob.scraped_at.desc()
    ).paginate(page=page, per_page=20, error_out=False)

    stats = {
        'pending':  ScrapedJob.query.filter_by(status='pending').count(),
        'approved': ScrapedJob.query.filter_by(status='approved').count(),
        'rejected': ScrapedJob.query.filter_by(status='rejected').count(),
        'total':    ScrapedJob.query.count(),
        'pending_verifications': VeteranProfile.query.filter_by(verification_status='pending').count(),
        'pending_job_approvals': JobPosting.query.filter_by(status='pending').count(),
        'pending_app_reviews': 0,
        'open_requests': 0,
    }

    sources = [r[0] for r in db.session.query(ScrapedJob.source_site).distinct().all()]
    categories = [
        r[0] for r in
        db.session.query(ScrapedJob.ai_category)
        .filter(ScrapedJob.ai_category.isnot(None))
        .distinct().all()
    ]

    return render_template(
        'admin/ai_jobs/dashboard.html',
        jobs=jobs,
        stats=stats,
        tab=tab,
        sources=sources,
        categories=categories,
        current_source=source,
        current_category=cat,
    )


# ─────────────────────────────────────────────────────────────
# approve route
# ─────────────────────────────────────────────────────────────

@ai_jobs_bp.route('/approve/<int:job_id>', methods=['POST'])
@login_required
def approve(job_id):
    gate = _require_admin()
    if gate:
        return gate

    scraped = ScrapedJob.query.get_or_404(job_id)

    if scraped.status == 'approved':
        flash('Already approved.', 'info')
        return redirect(url_for('ai_jobs.dashboard', tab='approved'))

    try:
        # ── Step 1: Fetch full detail from source if we only have thin data ──
        raw_desc = scraped.description or ''
        needs_detail_fetch = len(raw_desc.strip()) < 200 or raw_desc.strip().startswith('Category:')

        if needs_detail_fetch and scraped.source_url:
            logger.info(f"[approve] Fetching full detail from {scraped.source_url}")
            try:
                import requests as req_lib
                from bs4 import BeautifulSoup

                HEADERS = {
                    'User-Agent': (
                        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                        'AppleWebKit/537.36 (KHTML, like Gecko) '
                        'Chrome/120.0.0.0 Safari/537.36'
                    )
                }
                resp = req_lib.get(scraped.source_url, headers=HEADERS, timeout=15)
                resp.raise_for_status()
                soup = BeautifulSoup(resp.text, 'html.parser')
                page_text = soup.get_text(separator='\n', strip=True)

                # Extract body content
                body_el = soup.select_one(
                    '.job-description, .entry-content, .post-content, '
                    'article, main .content, #content, .job-details'
                )
                if body_el:
                    scraped.description = body_el.get_text(separator='\n', strip=True)[:5000]
                elif len(page_text) > 300:
                    # Use full page text, skip nav/footer noise
                    lines = [l.strip() for l in page_text.split('\n') if len(l.strip()) > 20]
                    scraped.description = '\n'.join(lines[:150])

                # Extract company name if missing
                if not scraped.company_name:
                    for sel in ['.company-name', '[class*="company"]', '[itemprop="hiringOrganization"]']:
                        el = soup.select_one(sel)
                        if el:
                            scraped.company_name = el.get_text(strip=True)[:200]
                            break

                # Extract location if still Nigeria
                if scraped.location in (None, 'Nigeria'):
                    for sel in ['.job-location', '[class*="location"]', '[itemprop="jobLocation"]']:
                        el = soup.select_one(sel)
                        if el:
                            scraped.location = el.get_text(strip=True)[:200]
                            break

                logger.info(f"[approve] Detail fetch successful — {len(scraped.description or '')} chars")
            except Exception as e:
                logger.warning(f"[approve] Detail fetch failed: {e} — proceeding with scraped data")

        # ── Step 2: Format the scraped data into clean structured fields ──
        from services.job_formatter import format_scraped_job
        structured = format_scraped_job(scraped)

        # ── Step 3: Create the real JobPosting ──
        real_job = JobPosting(
            posted_by           = ADMIN_POSTED_BY,
            title               = scraped.title,
            company_name        = scraped.company_name or 'Employer (via VetJobPortal)',
            location            = scraped.location or 'Nigeria',
            job_type            = scraped.job_type or 'full-time',
            description         = structured['description'],
            requirements        = structured['requirements'],
            how_to_apply        = structured['how_to_apply'],
            apply_email         = structured['apply_email'],
            external_apply_url  = structured['external_apply_url'],
            salary_min          = structured['salary_min'],
            salary_max          = structured['salary_max'],
            industry            = structured['industry'],
            experience_level    = structured['experience_level'],
            deadline            = structured['deadline'],
            is_veteran_friendly = True,
            is_admin_posted     = True,
            status              = 'approved',
            is_active           = True,
            is_featured         = False,
            company_logo        = 'images/vetjoblogo1.png',
        )

        db.session.add(real_job)
        db.session.flush()

        scraped.status           = 'approved'
        scraped.reviewed_by      = current_user.id
        scraped.reviewed_at      = datetime.utcnow()
        scraped.published_job_id = real_job.id

        db.session.commit()

        apply_info = []
        if structured['apply_email']:
            apply_info.append(f"email → {structured['apply_email']}")
        if structured['external_apply_url']:
            apply_info.append(f"link → {structured['external_apply_url']}")

        flash(
            f'✅ "{scraped.title}" approved and posted live!'
            + (f' [{", ".join(apply_info)}]' if apply_info else ''),
            'success'
        )
        logger.info(
            f"[ai_jobs] Admin {current_user.id} approved scraped job {job_id} "
            f"→ JobPosting {real_job.id} | desc={len(structured['description'])} chars"
        )

    except Exception as e:
        db.session.rollback()
        logger.error(f"[ai_jobs] Approve error: {e}", exc_info=True)
        flash('Error approving job. Please try again.', 'error')

    return redirect(url_for('ai_jobs.dashboard', tab='pending'))


@ai_jobs_bp.route('/reject/<int:job_id>', methods=['POST'])
@login_required
def reject(job_id):
    gate = _require_admin()
    if gate:
        return gate

    scraped = ScrapedJob.query.get_or_404(job_id)

    try:
        scraped.status      = 'rejected'
        scraped.reviewed_by = current_user.id
        scraped.reviewed_at = datetime.utcnow()
        db.session.commit()
        flash(f'❌ "{scraped.title}" rejected.', 'info')
    except Exception as e:
        db.session.rollback()
        flash('Error rejecting job.', 'error')

    return redirect(url_for('ai_jobs.dashboard', tab='pending'))


@ai_jobs_bp.route('/run-scrape', methods=['POST'])
@login_required
def run_scrape():
    gate = _require_admin()
    if gate:
        return gate

    import threading
    from services.job_scraper import run_full_scrape

    app = current_app._get_current_object()

    def scrape_in_background():
        with app.app_context():
            run_full_scrape(flask_app=None)

    thread = threading.Thread(target=scrape_in_background, daemon=True)
    thread.start()

    flash("Scraper started in the background — check back in a few minutes for new jobs.", 'info')
    return redirect(url_for('ai_jobs.dashboard'))


@ai_jobs_bp.route('/stats')
@login_required
def stats():
    gate = _require_admin()
    if gate:
        return jsonify({'error': 'Forbidden'}), 403

    return jsonify({
        'pending':  ScrapedJob.query.filter_by(status='pending').count(),
        'approved': ScrapedJob.query.filter_by(status='approved').count(),
        'rejected': ScrapedJob.query.filter_by(status='rejected').count(),
        'total':    ScrapedJob.query.count(),
        'pending_verifications': VeteranProfile.query.filter_by(verification_status='pending').count(),
        'pending_job_approvals': JobPosting.query.filter_by(status='pending').count(),
        'pending_app_reviews': 0,
        'open_requests': 0,
    })
