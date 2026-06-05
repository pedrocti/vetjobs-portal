import os, re, logging
from typing import Optional
logger = logging.getLogger(__name__)

STRUCTURE = {
    "has_contact_block": [r"\+?\d[\d\s\-]{8,}", r"@gmail|@yahoo|@hotmail|@outlook", r"abuja|lagos|port harcourt|kano|nigeria"],
    "has_summary": [r"professional summary", r"career summary", r"profile", r"objective"],
    "has_experience": [r"experience", r"employment", r"work history", r"career history"],
    "has_education": [r"education", r"academic", r"qualification"],
    "has_certifications": [r"certif", r"licensed", r"accredited"],
    "has_skills_section": [r"skills", r"competenc", r"expertise"],
}
STRONG_VERBS = ["achieved","delivered","reduced","increased","led","managed","supervised","trained","implemented","developed","coordinated","established","improved","negotiated","resolved","streamlined","launched","built","designed","saved","cut","grew","drove","executed","spearheaded","oversaw","directed","secured"]
WEAK_PHRASES = [r"responsible for", r"duties include", r"tasked with", r"helped with", r"assisted in", r"worked on", r"involved in", r"participated in", r"carried out", r"was part of"]
PERSONAL_PRONOUNS = [r"\bI \b", r"\bmy \b", r"\bwe \b", r"\bour \b"]
FILLER_PHRASES = [r"references (available|furnished) (on|upon) request", r"references available", r"date of birth", r"sex\s*:", r"gender\s*:", r"marital status", r"religion\s*:", r"state of origin"]
WEAPONS_FLAGS = [r"weapon", r"firearm", r"armed combat", r"ammunition", r"ballistic"]
DATE_PATTERN = re.compile(r"(19|20)\d{2}\s*[–\-—]\s*((19|20)\d{2}|present|current|date|till date)", re.IGNORECASE)
YEAR_ONLY = re.compile(r"\b(19|20)\d{2}\b")
ROLE_MAP = {
    "security": "Security Manager / Close Protection Officer",
    "hse": "HSE Officer / Safety Compliance Manager",
    "logistics": "Logistics Coordinator / Supply Chain Officer",
    "operations": "Operations Manager / Facility Manager",
    "maritime": "Maritime Security Officer / Port Operations Manager",
    "engineering": "Maintenance Engineer / Technical Officer",
    "admin": "Administrative Officer / Executive Assistant",
    "training": "Training Coordinator / L&D Officer",
    "intelligence": "Intelligence Analyst / Risk & Compliance Officer",
    "driver": "Fleet Supervisor / Transport Coordinator",
}

def _infer_roles(text):
    return [v for k,v in ROLE_MAP.items() if k in text][:3] or ["Operations Officer","Security Consultant"]

def _check_structure(text, tl):
    present = [s for s,pats in STRUCTURE.items() if any(re.search(p,tl) for p in pats)]
    missing = [s for s in STRUCTURE if s not in present]
    return present, missing

def _check_writing(text, tl):
    issues, adj = [], 0
    verb_hits = [v for v in STRONG_VERBS if v in tl]
    if len(verb_hits) >= 3: adj += 8
    elif len(verb_hits) >= 1: adj += 3
    else:
        issues.append({"point":"No strong action verbs in bullet points","detail":"Start each bullet with: Achieved, Led, Reduced, Managed, Delivered, Implemented"})
        adj -= 8
    weak = sum(1 for p in WEAK_PHRASES if re.search(p,tl))
    if weak >= 3:
        issues.append({"point":"Heavy use of duty-based language","detail":"Replace responsible for/duties include with what you actually achieved and the result"})
        adj -= 10
    elif weak >= 1:
        issues.append({"point":"Some duty-based language detected","detail":"Rewrite task-focused bullets to show results and impact instead"})
        adj -= 5
    if re.search(r"\d+\s*%|\d+ (people|staff|personnel|teams?|years?)| reduced by| increased by| saved", tl):
        adj += 10
    else:
        issues.append({"point":"No quantified achievements","detail":"Add numbers wherever possible: team size, % improvement, years of experience, cost saved"})
        adj -= 8
    if sum(1 for p in PERSONAL_PRONOUNS if re.search(p,text)) >= 3:
        issues.append({"point":"Personal pronouns used (I, my, we)","detail":"CVs should be impersonal — remove all I/my/we references throughout"})
        adj -= 5
    if sum(1 for p in WEAPONS_FLAGS if re.search(p,tl)) >= 1:
        issues.append({"point":"Weapons-related language detected","detail":"Remove or reframe firearms/weapons references — they raise red flags with civilian HR"})
        adj -= 8
    if sum(1 for p in FILLER_PHRASES if re.search(p,tl)) >= 2:
        issues.append({"point":"CV contains outdated personal details","detail":"Remove: date of birth, gender, marital status, religion, references available on request"})
        adj -= 5
    return issues, adj

def _check_dates(text):
    years = YEAR_ONLY.findall(text)
    if len(years) < 2:
        return [{"point":"Missing dates in education or experience","detail":"Every job and qualification needs start and end dates — recruiters check for employment gaps"}], -8
    return [], 0

def _check_linkedin(tl):
    if re.search(r"linkedin\.com", tl): return [], 5
    return [{"point":"No LinkedIn profile URL","detail":"Add your LinkedIn URL — it is now standard on all civilian CVs and increases recruiter response rates"}], 0

def _check_summary(tl):
    if not any(re.search(p,tl) for p in STRUCTURE["has_summary"]):
        return [{"point":"No professional summary section","detail":"Add a 3-5 line targeted summary at the top stating your civilian role target and key value"}], -5
    if any(re.search(p,tl) for p in [r"seeking.*opportunity", r"to work in.*reputable", r"to contribute.*skills"]):
        return [{"point":"Professional summary is too generic","detail":"Rewrite it targeting a specific role: HSE Officer, Security Manager, Operations Coordinator"}], -5
    return [], 5

def _build_strength(tl, present):
    pts = []
    if any(re.search(p,tl) for p in [r"hse", r"nebosh", r"iosh"]): pts.append("HSE qualifications highly valued in civilian roles")
    if "has_certifications" in present: pts.append("relevant professional certifications")
    if re.search(r"leadership|supervised|managed|led", tl): pts.append("demonstrated leadership and supervisory experience")
    if re.search(r"\b1[5-9]\b|\b2\d\b years", tl): pts.append("extensive years of military service")
    base = "Your military background brings discipline, structured thinking, and operational experience that civilian employers genuinely value."
    if pts: base += " Your CV shows: " + ", ".join(pts[:3]) + "."
    return base

def _enhanced_keyword_analysis(cv_text):
    tl = cv_text.lower()
    score = 50
    issues = []
    present, missing = _check_structure(cv_text, tl)
    score += (len(present)/len(STRUCTURE)) * 20
    if "has_contact_block" not in present: issues.append({"point":"Contact information incomplete","detail":"Phone, email and location must be clearly visible at the very top"})
    if "has_experience" not in present: issues.append({"point":"Work experience section not clearly labelled","detail":"Use heading: Professional Experience or Work History"})
    if "has_education" not in present: issues.append({"point":"Education section missing or unclear","detail":"List qualifications with institution, dates and certificate earned"})
    wi, wa = _check_writing(cv_text, tl)
    score += wa; issues.extend(wi)
    di, da = _check_dates(cv_text)
    score += da; issues.extend(di)
    li, la = _check_linkedin(tl)
    score += la; issues.extend(li)
    si, sa = _check_summary(tl)
    score += sa; issues.extend(si)
    if cv_text.count("|") > 5:
        issues.append({"point":"Possible table/column layout detected","detail":"ATS systems cannot read tables — use single column plain text format"})
        score -= 8
    return {"score":max(20,min(95,int(score))),"strength_summary":_build_strength(tl,present),"issues":issues[:6],"target_roles":_infer_roles(tl),"method":"enhanced_keyword"}

def _claude_analysis(cv_text):
    import anthropic, json
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    prompt = ("You are a senior Nigerian HR consultant specialising in military-to-civilian career transitions.\n"
        "Analyse this CV for civilian workforce readiness.\nCheck: structure, writing quality (action verbs, quantified results), "
        "ATS compatibility, civilian positioning, completeness.\n\nCV:\n" + cv_text[:3500] +
        '\n\nRespond ONLY with valid JSON:\n{"score":<0-100>,"strength_summary":"<2 sentences>",'
        '"issues":[{"point":"<title>","detail":"<why it matters>"}],"target_roles":["<r1>","<r2>","<r3>"],"method":"claude"}\n2-6 issues, encouraging tone.')
    msg = client.messages.create(model="claude-sonnet-4-20250514",max_tokens=900,messages=[{"role":"user","content":prompt}])
    r = json.loads(msg.content[0].text.strip()); r["method"]="claude"; return r

def analyse_veteran_cv(veteran_profile):
    from services.cv_scanner import extract_cv_text
    path = getattr(veteran_profile,"resume_file",None)
    if not path: return None
    base = "/var/www/vetjobportal/static/uploads/resumes"
    full = path if os.path.isabs(path) else os.path.join(base, path.lstrip("/"))
    text = extract_cv_text(full)
    if not text or len(text.strip()) < 100: return None
    if os.environ.get("ANTHROPIC_API_KEY"):
        try: return _claude_analysis(text)
        except Exception as e: logger.warning(f"[cv_analysis] Claude failed ({e}), using keyword fallback")
    return _enhanced_keyword_analysis(text)