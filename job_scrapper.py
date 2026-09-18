import undetected_chromedriver as uc
from bs4 import BeautifulSoup
import csv
import time
import random
import urllib.parse
import re
import os
import json
import argparse
import threading
import requests
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode, urljoin, parse_qs
from datetime import datetime, timedelta
import pytz
from concurrent.futures import ThreadPoolExecutor, as_completed
import html as html_lib

# -------------------------------
# Configuration
# -------------------------------
DEFAULT_MAX_PAGES_PER_QUERY = 8

ATS_MAX_PAGES = {
    "greenhouse": 20,
    "ashby": 20,
    "lever": 20,
    "workday": 20,
    "rest": 10,
    "ziprecruiter": 10,
}

GOOGLE_SEARCH_BASE = "https://www.google.com/search?q="
CHROME_VERSION_MAIN = 152
CHROME_CREATE_LOCK = threading.Lock()

PARALLEL_JD_WORKERS = 4
STRICT_DAYS_LIMIT = 6

HEADLESS_JD_EXTRACTION = False

CSV_DIR = "CSV"
LINK_HISTORY_DIR = os.path.join(CSV_DIR, "link_history")
CONTROL_DIR = os.path.join(CSV_DIR, "control")
CHECKPOINT_DIR = os.path.join(CSV_DIR, "checkpoints")
ENABLE_RESUME_FROM_CHECKPOINT = True

SKIP_CURRENT_QUERY_FLAG_FILE = os.path.join(CONTROL_DIR, "skip_current_query.flag")
STOP_FULL_RUN_FLAG_FILE = os.path.join(CONTROL_DIR, "stop_full_run.flag")

# Debugger flags. Set either to True while debugging.
SKIP_CURRENT_QUERY_DEBUG_FLAG = False
STOP_FULL_RUN_DEBUG_FLAG = False

SKIP_LINKS_SEEN_YESTERDAY = True
SKIP_KNOWN_NO_SPONSOR_COMPANIES = True

STOP_GOOGLE_SEARCH_ON_BROWSER_ERROR = True
MAX_GOOGLE_PAGE_ERRORS_BEFORE_STOP = 3

WAIT_BETWEEN_GOOGLE_PAGES = (58, 75)
WAIT_BETWEEN_GOOGLE_SEARCHES = (70, 88)
WAIT_AFTER_GOOGLE_BLOCK = (200, 300)

REQUEST_TIMEOUT_SECONDS = 18
MIN_HTML_LENGTH_FOR_REQUESTS = 1000
MIN_JD_LENGTH = 500
RETRY_MIN_JD_LENGTH = 500
ENABLE_TITLE_FILTERING = False
COMPANY_SPONSORSHIP_MEMORY_FILE = os.path.join(CSV_DIR, "company_sponsorship_memory.csv")

ALLOWED_EXACT_DOMAINS = {
    "boards.greenhouse.io",
    "job-boards.greenhouse.io",
    "jobs.lever.co",
    "jobs.ashbyhq.com",
    "apply.workable.com",
    "jobs.smartrecruiters.com",
    "careers.smartrecruiters.com",
    "jobs.icims.com",
    "jobs.jobvite.com",
    "jobs.recruitee.com",
    "breezy.hr",
    "recruiting.paylocity.com",
    "careers.jazz.co",
    "applytojob.com",
    "teamtailor.com",
    "rippling-ats.com",
    "linkedin.com",
    "jobs.apple.com",
    # "remoterocketship.com",
    "ziprecruiter.com",
    "ycombinator.com",
    "levels.fyi",
}

ALLOWED_SUFFIX_DOMAINS = (
    ".myworkdayjobs.com",
)

SENIORITY_BLOCKLIST = {
    "lead",
    "staff",
    "principal",
    "manager",
    "director",
    "architect",
    "head",
    "vp",
    "vice president",
    "chief",
}

# ATS_SEARCH_GROUPS = [
#     {
#         "ats_group": "greenhouse",
#         "site_query": "(site:boards.greenhouse.io OR site:job-boards.greenhouse.io)",
#     },
#     {
#         "ats_group": "ashby",
#         "site_query": "site:jobs.ashbyhq.com",
#     },
#     {
#         "ats_group": "lever",
#         "site_query": "site:jobs.lever.co",
#     },
#     {
#         "ats_group": "workday",
#         "site_query": "site:myworkdayjobs.com",
#     },
#     {
#         "ats_group": "rest",
#         "site_query": """(
#             site:apply.workable.com
#             OR site:jobs.smartrecruiters.com
#             OR site:careers.smartrecruiters.com
#             OR site:jobs.icims.com
#             OR site:jobs.jobvite.com
#             OR site:jobs.recruitee.com
#             OR site:breezy.hr
#             OR site:recruiting.paylocity.com
#             OR site:careers.jazz.co
#             OR site:rippling-ats.com
#             OR site:levels.fyi
#         )""",
#     },
# ]
# #             OR site:remoterocketship.com

ATS_SEARCH_GROUPS = [
    {
        "ats_group": "greenhouse",
        "site_query": "(site:boards.greenhouse.io OR site:job-boards.greenhouse.io)",
    },
    {
        "ats_group": "ashby",
        "site_query": "site:jobs.ashbyhq.com",
    },
    {
        "ats_group": "lever",
        "site_query": "site:jobs.lever.co",
    },
    # {
    #     "ats_group": "workday",
    #     "site_query": "site:myworkdayjobs.com",
    # },
    {
        "ats_group": "adp",
        "site_query": "site:workforcenow.adp.com",
    },
    {
        "ats_group": "icims",
        "site_query": "site:icims.com",
    },
    {
        "ats_group": "workable",
        "site_query": "site:apply.workable.com",
    },
    {
        "ats_group": "rest",
        "site_query": """(
            site:jobs.smartrecruiters.com
            OR site:careers.smartrecruiters.com
            OR site:jobs.jobvite.com
            OR site:jobs.recruitee.com
            OR site:breezy.hr
            OR site:recruiting.paylocity.com
            OR site:careers.jazz.co
            OR site:rippling-ats.com
            OR site:levels.fyi
        )""",
    },
]

LOCATION_SEARCHES = [
    {
        "location_group": "remote",
        "query": """
            ("US Remote" OR "Remote - US" OR "Remote within the United States" OR "United States")
            -Europe -India -Canada -UK -"United Kingdom" -Germany -Poland -Portugal -Netherlands -Australia -Singapore
        """,
    },
    {
        "location_group": "hybrid",
        "query": """
            (hybrid OR "hybrid schedule" OR "hybrid role" OR "3 days onsite" OR "2 days onsite" OR "in office")
            ("United States" OR "USA" OR "Los Angeles" OR "San Francisco" OR "Austin" OR "Seattle" OR "New York" OR "Chicago")
            -remote -"work from anywhere"
            -Europe -India -Canada -UK -"United Kingdom" -Germany -Poland -Portugal -Netherlands -Australia -Singapore
        """,
    },
    {
        "location_group": "onsite",
        "query": """
            (onsite OR "on site" OR "in office" OR "5 days onsite" OR "office based")
            ("United States" OR "USA" OR "Los Angeles" OR "San Francisco" OR "Austin" OR "Seattle" OR "New York" OR "Chicago")
            -remote -hybrid -"work from anywhere"
            -Europe -India -Canada -UK -"United Kingdom" -Germany -Poland -Portugal -Netherlands -Australia -Singapore
        """,
    },
]

COMMON_NEGATIVE_TITLE_QUERY = """
    -intitle:Staff
    -intitle:Principal
    -intitle:Lead
    -intitle:Manager
    -intitle:Director
    -intitle:Architect
"""

JOB_SEARCHES = [
    ("Software Engineer", ["software engineer"]),
    ("Product Engineer", ["Product Engineer"]),
    ("Support Engineer", [ "Support Engineer"]),
    ("Full Stack Developer", [
        "full stack software engineer",
        "full-stack software engineer",
        "full stack developer",
        "full-stack developer",
        "fullstack engineer",
        "full-stack engineer",
        "full stack engineer",
    ]),
    ("AI Engineer", [
        "ai engineer",
        "artificial intelligence engineer",
        "applied ai engineer",
    ]),
    ("Data Engineer", [
        "data engineer",
        "data software engineer",
    ]),
    ("Backend Engineer", [
        "backend engineer",
        "back end engineer",
        "backend software engineer",
        "back end software engineer",
        "software engineer backend",
    ]),
    ("Software Developer", ["software developer"]),
    ("Platform Engineer", [
        "platform engineer",
        "platform software engineer",
    ]),
    ("Python Developer", [
        "python developer",
        "python software engineer",
        "python engineer",
    ]),
    ("Java Developer", [
        "java developer",
        "java software engineer",
        "java engineer",
    ]),
]

SPONSORSHIP_REJECT_PATTERNS = [
    r"\bwill not sponsor\b",
    r"\bdoes not sponsor\b",
    r"\bdo not sponsor\b",
    r"\bno sponsorship\b",
    r"\bno visa sponsorship\b",
    r"\bvisa sponsorship is not available\b",
    r"\bsponsorship is not available\b",
    r"\bunable to sponsor\b",
    r"\bwe are unable to sponsor\b",
    r"\bwe do not offer sponsorship\b",
    r"\bwe cannot sponsor\b",
    r"\bmust be authorized to work in the united states without sponsorship\b",
    r"\bmust be legally authorized to work.*without.*sponsorship\b",
    r"\bmust be authorized.*without.*sponsorship\b",
    r"\bmust not require sponsorship\b",
    r"\bdoes not provide.*visa sponsorship\b",
    r"\bdo not provide.*visa sponsorship\b",
    r"\bwill not provide.*visa sponsorship\b",
    r"\bno.*visa sponsorship.*provided\b",
    r"\bneed immigration support\b",
    r"\bwill need immigration support\b",
    r"\brequire immigration support\b",
    r"\bwill require immigration support\b",
    r"\bneed.*h-?1b\b",
    r"\bneed.*stem opt\b",
    r"\bneed.*tn\b",
    r"\bstem opt training plans\b",
    r"\bnot open for work sponsorship\b",
    r"\bnot open for .* sponsorship\b",
    r"\bnot available for work sponsorship\b",
    r"\bwork sponsorship is not available\b",
    r"\bemployment sponsorship is not available\b",
    r"\bnot able to provide work sponsorship\b",
    r"\bunable to provide work sponsorship\b",
    r"\bwill not provide work sponsorship\b",
    r"\bdoes not provide work sponsorship\b",
    r"\bno work sponsorship\b",
    r"\bno employment sponsorship\b",
]

SPONSORSHIP_POSITIVE_PATTERNS = [
    r"\bvisa sponsorship available\b",
    r"\bsponsorship available\b",
    r"\bwill sponsor\b",
    r"\bwe sponsor\b",
    r"\bh-?1b sponsorship\b",
    r"\bh-?1b transfer\b",
    r"\bopen to sponsorship\b",
]

CLEARANCE_REJECT_PATTERNS = [
    r"\bus citizen\b",
    r"\bu\.s\. citizen\b",
    r"\bu\.s\. citizenship\b",
    r"\bmust be a citizen\b",
    r"\bsecurity clearance\b",
    r"\bsecret clearance\b",
    r"\btop secret\b",
    r"\bts/sci\b",
    r"\bsci clearance\b",
    r"\bdod clearance\b",
    r"\bpublic trust\b",
    r"\bitar\b",
    r"\bexport control\b",
    r"\bfederal contractor\b",
    r"\bgovernment clearance\b",
]

US_LOCATION_HINTS = [
    "united states",
    "usa",
    "u.s.",
    "us remote",
    "remote - us",
    "remote within the united states",
    "new york",
    "san francisco",
    "los angeles",
    "chicago",
    "austin",
    "seattle",
    "boston",
    "denver",
    "dallas",
    "atlanta",
    "miami",
    "washington",
    "california",
    "texas",
    "illinois",
]

NON_US_LOCATION_HINTS = [
    "india",
    "bengaluru",
    "bangalore",
    "karnataka",
    "hyderabad",
    "pune",
    "mumbai",
    "chennai",
    "delhi",
    "noida",
    "gurugram",
    "gurgaon",
    "canada",
    "united kingdom",
    "uk",
    "europe",
    "germany",
    "poland",
    "portugal",
    "netherlands",
    "australia",
    "singapore",
    "south africa",
    "taiwan",
    "bulgaria",
    "bosnia",
    "sarajevo",
]

BAD_JD_MARKERS = [
    "you need to enable javascript to run this app",
    "autofill application",
    "autofill from resume",
    "autofill with resume",
    "upload your resume",
    "drop your resume here",
    "create a job alert",
    "create alert",
    "this job posting has expired",
    "this job is no longer accepting applications",
    "the page you are looking for doesn't exist",
    "the page you are looking for does not exist",
    "salary calculator",
    "salary jobs",
    "table view",
    "post a job affiliates search remote jobs",
    "please enable javascript in your browser",
    "sign in to apply",
    "login to apply",
    "apply with linkedin",
    "application for",
]

GOOD_JD_MARKERS = [
    "responsibilities",
    "requirements",
    "qualifications",
    "what you'll do",
    "what you will do",
    "about the role",
    "about you",
    "job description",
    "required experience",
    "minimum qualifications",
    "preferred qualifications",
    "you will",
    "we are looking for",
    "who you are",
    "skills",
    "experience with",
    "nice to have",
    "benefits",
]

LINK_FIELDNAMES = [
    "ats_group",
    "location_group",
    "search_bucket",
    "title",
    "title_match_status",
    "title_reject_reason",
    "url",
    "display_domain",
    "company_guess",
    "job_id_guess",
    "canonical_company_job_key",
    "page_number",
]

ENRICHED_FIELDNAMES = [
    "ats_group",
    "location_group",
    "search_bucket",
    "title",
    "title_match_status",
    "title_reject_reason",
    "url",
    "display_domain",
    "company_guess",
    "job_id_guess",
    "canonical_company_job_key",
    "application_url",
    "application_dedupe_key",
    "page_number",
    "decision",
    "rejection_reasons",
    "posted_status",
    "posted_value",
    "posted_source",
    "posted_age_days",
    "location_status",
    "location_evidence",
    "sponsorship_status",
    "positive_sponsorship_matches",
    "negative_sponsorship_matches",
    "sponsorship_evidence_snippet",
    "positive_sponsorship_evidence_snippet",
    "clearance_matches",
    "clearance_evidence_snippet",
    "jd_quality_status",
    "jd_quality_reasons",
    "jd_text_length",
    "JD_Text",
    "extraction_method",
    "retry_attempted",
    "error",
]

COMPANY_MEMORY_FIELDNAMES = [
    "company_key",
    "company_guess",
    "display_domain",
    "sponsorship_status",
    "last_seen_date",
    "evidence_url",
    "evidence_snippet",
    "notes",
]


class GoogleSearchStoppedError(Exception):
    pass


class RunSummary:
    def __init__(self):
        self.data = {
            "started_at": datetime.now().isoformat(),
            "finished_at": "",
            "mode": "",
            "accepted_links_added": 0,
            "rejected_title_links_added": 0,
            "yesterday_duplicate_links_added": 0,
            "links_found_today": 0,
            "jd_total_input_rows": 0,
            "jd_accepted": 0,
            "jd_rejected": 0,
            "jd_needs_review": 0,
            "jd_errors": 0,
            "jd_retries_attempted": 0,
            "jd_retries_successful": 0,
            "known_no_sponsor_skipped": 0,
            "company_memory_updates": 0,
            "google_blocks_detected": 0,
            "google_page_errors": 0,
            "google_search_stopped_due_to_error": False,
            "google_error_message": "",
            "request_extractions": 0,
            "selenium_fallback_extractions": 0,
            "manual_skip_query_requests": 0,
            "manual_stop_run_requests": 0,
            "total_google_queries_planned": 0,
            "last_google_query_number": 0,
            "last_google_query_label": "",
            "application_duplicates_skipped": 0,
            "total_seconds": 0,
        }
        self.lock = threading.Lock()

    def increment(self, key: str, amount: int = 1):
        with self.lock:
            self.data[key] = self.data.get(key, 0) + amount

    def set_value(self, key: str, value):
        with self.lock:
            self.data[key] = value

    def get_value(self, key: str, default=None):
        with self.lock:
            return self.data.get(key, default)

    def save(self, date_suffix: str):
        self.data["finished_at"] = datetime.now().isoformat()
        path = os.path.join(CSV_DIR, f"run_summary_{date_suffix}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2)
        print(f"\nRun summary saved to: {path}")


RUN_SUMMARY = RunSummary()


def ensure_output_dirs():
    os.makedirs(CSV_DIR, exist_ok=True)
    os.makedirs(LINK_HISTORY_DIR, exist_ok=True)
    os.makedirs(CONTROL_DIR, exist_ok=True)
    os.makedirs(CHECKPOINT_DIR, exist_ok=True)

def now_chicago_suffix() -> str:
    return datetime.now(tz=pytz.timezone("America/Chicago")).strftime("%d%m%Y")


def today_chicago_iso() -> str:
    return datetime.now(tz=pytz.timezone("America/Chicago")).date().isoformat()


def get_date_suffix_for_days_ago(days_ago: int) -> str:
    chicago_tz = pytz.timezone("America/Chicago")
    target_date = datetime.now(tz=chicago_tz).date() - timedelta(days=days_ago)
    return target_date.strftime("%d%m%Y")


def get_link_history_file(date_suffix: str) -> str:
    return os.path.join(LINK_HISTORY_DIR, f"links_seen_{date_suffix}.txt")


def load_links_from_file(filepath: str) -> set[str]:
    if not os.path.exists(filepath):
        return set()

    with open(filepath, "r", encoding="utf-8") as f:
        return {line.strip() for line in f if line.strip()}


def save_links_to_file(links: set[str], filepath: str):
    existing_links = load_links_from_file(filepath)
    merged_links = existing_links | links

    with open(filepath, "w", encoding="utf-8") as f:
        for link in sorted(merged_links):
            f.write(link + "\n")


def get_checkpoint_file(date_suffix: str) -> str:
    return os.path.join(CHECKPOINT_DIR, f"checkpoint_{date_suffix}.json")


def load_checkpoint(date_suffix: str) -> dict:
    if not ENABLE_RESUME_FROM_CHECKPOINT:
        return {}

    checkpoint_file = get_checkpoint_file(date_suffix)

    if not os.path.exists(checkpoint_file):
        return {}

    try:
        with open(checkpoint_file, "r", encoding="utf-8") as f:
            checkpoint = json.load(f)

        print(f"\nLoaded checkpoint: {checkpoint_file}")
        print(json.dumps(checkpoint, indent=2))
        return checkpoint

    except Exception as e:
        print(f"\nCould not load checkpoint: {e}")
        return {}


def save_checkpoint(date_suffix: str, checkpoint: dict):
    checkpoint_file = get_checkpoint_file(date_suffix)
    temp_file = checkpoint_file + ".tmp"

    checkpoint["updated_at"] = datetime.now().isoformat()

    try:
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(checkpoint, f, indent=2)

        os.replace(temp_file, checkpoint_file)

    except Exception as e:
        print(f"\nCould not save checkpoint: {e}")

# Clear Checkpoint File
def clear_checkpoint(date_suffix: str):
    checkpoint_file = get_checkpoint_file(date_suffix)

    if os.path.exists(checkpoint_file):
        try:
            os.remove(checkpoint_file)
            print(f"\nCleared checkpoint: {checkpoint_file}")
        except Exception as e:
            print(f"\nCould not clear checkpoint: {e}")


def get_last_completed_query_index(checkpoint: dict) -> int:
    google_state = checkpoint.get("google", {})
    return int(google_state.get("last_completed_query_index", -1))


def should_skip_completed_query(current_query_index: int, last_completed_query_index: int) -> bool:
    return current_query_index <= last_completed_query_index

def load_yesterday_links() -> set[str]:
    yesterday_suffix = get_date_suffix_for_days_ago(1)
    yesterday_file = get_link_history_file(yesterday_suffix)

    yesterday_links = load_links_from_file(yesterday_file)

    print(f"\nYesterday link file checked: {yesterday_file}")
    print(f"Links found from yesterday: {len(yesterday_links)}")

    return yesterday_links


def consume_flag_file(filepath: str) -> bool:
    if not os.path.exists(filepath):
        return False

    try:
        os.remove(filepath)
    except Exception:
        pass

    return True


def should_skip_current_query() -> bool:
    global SKIP_CURRENT_QUERY_DEBUG_FLAG

    if SKIP_CURRENT_QUERY_DEBUG_FLAG:
        SKIP_CURRENT_QUERY_DEBUG_FLAG = False
        return True

    return consume_flag_file(SKIP_CURRENT_QUERY_FLAG_FILE)


def should_stop_full_run() -> bool:
    global STOP_FULL_RUN_DEBUG_FLAG

    if STOP_FULL_RUN_DEBUG_FLAG:
        STOP_FULL_RUN_DEBUG_FLAG = False
        return True

    return consume_flag_file(STOP_FULL_RUN_FLAG_FILE)


def sleep_random(wait_range: tuple[int, int], reason: str):
    wait_time = random.uniform(wait_range[0], wait_range[1])
    print(f" -> Sleeping {round(wait_time, 1)} seconds: {reason}")
    time.sleep(wait_time)


def safe_quit_driver(driver):
    try:
        if driver:
            driver.quit()
    except Exception:
        pass


def normalize_domain(url_or_domain: str) -> str:
    raw = (url_or_domain or "").strip().lower()

    if not raw:
        return ""

    parsed = urlparse(raw)

    if parsed.netloc:
        host = parsed.netloc
    else:
        parsed = urlparse("//" + raw)
        host = parsed.netloc or parsed.path

    host = host.lower().strip()

    if host.startswith("www."):
        host = host[4:]

    return host


def canonicalize_url(url: str) -> str:
    parsed = urlparse((url or "").strip())

    scheme = parsed.scheme.lower() or "https"
    netloc = parsed.netloc.lower()

    if netloc.startswith("www."):
        netloc = netloc[4:]

    path = parsed.path.rstrip("/")
    if not path:
        path = "/"

    drop_params = {
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "utm_term",
        "utm_content",
        "gclid",
        "gbraid",
        "wbraid",
        "fbclid",
        "gh_jid",
        "gh_src",
    }

    filtered_query = [
        (k, v)
        for k, v in parse_qsl(parsed.query, keep_blank_values=True)
        if k.lower() not in drop_params
    ]

    filtered_query.sort()
    query = urlencode(filtered_query, doseq=True)

    return urlunparse((scheme, netloc, path, "", query, ""))


def canonicalize_ats_job_url(url: str) -> str:
    """
    Converts ATS application URLs into job-posting URLs before extraction.
    This prevents scraping application forms instead of job descriptions.
    """
    url = canonicalize_url(url)
    parsed = urlparse(url)
    host = normalize_domain(url)
    path = parsed.path

    if host.endswith(".myworkdayjobs.com"):
        path = re.sub(r"/apply(?:/.*)?$", "", path, flags=re.IGNORECASE)

    if host == "apply.workable.com":
        path = re.sub(r"/apply/?$", "", path, flags=re.IGNORECASE)

    if host == "jobs.ashbyhq.com":
        path = re.sub(r"/application/?$", "", path, flags=re.IGNORECASE)

    if "greenhouse.io" in host:
        path = re.sub(r"/application/?$", "", path, flags=re.IGNORECASE)

    cleaned = urlunparse((
        parsed.scheme,
        parsed.netloc,
        path.rstrip("/") or "/",
        "",
        "",
        "",
    ))

    return cleaned


def normalize_text(text: str) -> str:
    text = (text or "").lower().strip()
    text = re.sub(r"[^a-z0-9\s\-/&,()]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def normalize_lower(text: str) -> str:
    return normalize_space(text).lower()


def contains_phrase_as_words(text: str, phrase: str) -> bool:
    normalized_text = normalize_text(text)
    normalized_phrase = normalize_text(phrase)
    pattern = r"\b" + re.escape(normalized_phrase) + r"\b"
    return re.search(pattern, normalized_text) is not None


def has_blocked_seniority(title: str) -> bool:
    title_norm = normalize_text(title)

    for blocked in SENIORITY_BLOCKLIST:
        if contains_phrase_as_words(title_norm, blocked):
            return True

    return False


def get_title_match_status(title: str, allowed_phrases: list[str]) -> tuple[str, str]:
    # if has_blocked_seniority(title):
    #     return "rejected", "blocked_seniority"

    # title_norm = normalize_text(title)
    # if any(contains_phrase_as_words(title_norm, phrase) for phrase in allowed_phrases):
    return "accepted", ""

    # return "accepted", "phrase_mismatch"


def is_allowed_ats_url(url: str) -> bool:
    host = normalize_domain(url)

    if host in ALLOWED_EXACT_DOMAINS:
        return True

    return any(host.endswith(suffix) for suffix in ALLOWED_SUFFIX_DOMAINS)


def create_driver(headless: bool = False):
    with CHROME_CREATE_LOCK:
        options = uc.ChromeOptions()
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")

        if headless:
            options.add_argument("--headless=new")

        return uc.Chrome(options=options, version_main=CHROME_VERSION_MAIN)


def get_url_from_row(row: dict) -> str:
    for key in ["url", "URL", "link", "Link", "job_url", "Job URL", "application_url"]:
        value = row.get(key)
        if value and str(value).strip().startswith("http"):
            return str(value).strip()
    return ""


def row_key_url(row: dict) -> str:
    url = get_url_from_row(row) or row.get("url", "")
    if not url:
        return ""
    return canonicalize_ats_job_url(url)


def extract_company_job_key(url: str) -> tuple[str, str, str]:
    parsed = urlparse(url)
    host = normalize_domain(url)
    path_parts = [p for p in parsed.path.split("/") if p]

    company = ""
    job_id = ""

    if "greenhouse.io" in host:
        if len(path_parts) >= 2:
            company = path_parts[0]
            job_id = path_parts[-1]

    elif host == "jobs.lever.co":
        if len(path_parts) >= 2:
            company = path_parts[0]
            job_id = path_parts[1]

    elif host == "jobs.ashbyhq.com":
        if len(path_parts) >= 2:
            company = path_parts[0]
            job_id = path_parts[-1]

    elif host.endswith(".myworkdayjobs.com"):
        company = host.split(".")[0]
        job_id = path_parts[-1] if path_parts else ""

    elif host == "remoterocketship.com":
        company = "remoterocketship"
        job_id = path_parts[-1] if path_parts else ""

    elif host == "levels.fyi":
        company = "levels"
        job_id = path_parts[-1] if path_parts else ""

    else:
        company = host.split(".")[0]
        job_id = path_parts[-1] if path_parts else ""

    key = f"{host}|{company}|{job_id}".lower()
    return company, job_id, key


def get_company_key(company_guess: str, display_domain: str) -> str:
    company = normalize_text(company_guess).replace(" ", "_")
    domain = normalize_domain(display_domain)
    return f"{domain}|{company}".strip("|").lower()


def read_existing_csv_rows(filepath: str) -> list[dict]:
    if not os.path.exists(filepath):
        return []

    with open(filepath, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def get_existing_urls_from_csv(filepath: str) -> set[str]:
    urls = set()

    for row in read_existing_csv_rows(filepath):
        url = row_key_url(row)
        if url:
            urls.add(url)

    return urls


def get_existing_application_keys_from_csv(filepath: str) -> set[str]:
    keys = set()

    for row in read_existing_csv_rows(filepath):
        key = row.get("application_dedupe_key", "").strip()
        if key:
            keys.add(key)

    return keys


def append_unique_rows_to_csv(filepath: str, rows: list[dict], fieldnames: list[str], unique_key: str = "url") -> int:
    os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)

    if not os.path.exists(filepath):
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()

    if not rows:
        return 0

    existing_urls = get_existing_urls_from_csv(filepath)
    rows_to_write = []
    seen_in_batch = set()

    for row in rows:
        row = {key: row.get(key, "") for key in fieldnames}

        url = row.get(unique_key, "").strip()
        if not url:
            continue

        normalized_url = canonicalize_ats_job_url(url)
        row[unique_key] = normalized_url

        if normalized_url in existing_urls:
            continue

        if normalized_url in seen_in_batch:
            continue

        seen_in_batch.add(normalized_url)
        rows_to_write.append(row)

    if not rows_to_write:
        return 0

    with open(filepath, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writerows(rows_to_write)

    return len(rows_to_write)


def flush_location_rows(
    accepted_csv: str,
    rejected_title_csv: str,
    yesterday_csv: str,
    location_accepted_rows: list[dict],
    location_rejected_title_rows: list[dict],
    location_yesterday_duplicate_rows: list[dict],
) -> tuple[int, int, int]:
    accepted_added = append_unique_rows_to_csv(
        accepted_csv,
        location_accepted_rows,
        LINK_FIELDNAMES,
    )
    rejected_added = append_unique_rows_to_csv(
        rejected_title_csv,
        location_rejected_title_rows,
        LINK_FIELDNAMES,
    )
    yesterday_added = append_unique_rows_to_csv(
        yesterday_csv,
        location_yesterday_duplicate_rows,
        LINK_FIELDNAMES,
    )

    location_accepted_rows.clear()
    location_rejected_title_rows.clear()
    location_yesterday_duplicate_rows.clear()

    return accepted_added, rejected_added, yesterday_added


class CompanySponsorshipMemory:
    def __init__(self, filepath: str):
        self.filepath = filepath
        self.lock = threading.Lock()
        self.memory = {}
        self.ensure_file()
        self.load()

    def ensure_file(self):
        os.makedirs(os.path.dirname(self.filepath) or ".", exist_ok=True)

        if not os.path.exists(self.filepath) or os.path.getsize(self.filepath) == 0:
            with open(self.filepath, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=COMPANY_MEMORY_FIELDNAMES)
                writer.writeheader()

    def load(self):
        self.memory = {}

        with open(self.filepath, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)

            for row in reader:
                key = row.get("company_key", "").strip().lower()
                if key:
                    self.memory[key] = row

    def is_known_no_sponsor(self, company_key: str) -> bool:
        if not company_key:
            return False

        row = self.memory.get(company_key.lower())
        if not row:
            return False

        return row.get("sponsorship_status") == "red_blocker_found"

    def get_memory_row(self, company_key: str) -> dict:
        return self.memory.get(company_key.lower(), {})

    def update_from_enriched_row(self, row: dict):
        sponsorship_status = row.get("sponsorship_status", "")
        if sponsorship_status not in {"red_blocker_found", "green_positive_signal"}:
            return

        company_guess = row.get("company_guess", "")
        display_domain = row.get("display_domain", "")
        company_key = get_company_key(company_guess, display_domain)

        if not company_key:
            return

        memory_row = {
            "company_key": company_key,
            "company_guess": company_guess,
            "display_domain": display_domain,
            "sponsorship_status": sponsorship_status,
            "last_seen_date": today_chicago_iso(),
            "evidence_url": row.get("url", ""),
            "evidence_snippet": (
                row.get("sponsorship_evidence_snippet", "")
                or row.get("positive_sponsorship_evidence_snippet", "")
            ),
            "notes": "",
        }

        with self.lock:
            self.memory[company_key] = memory_row
            self.rewrite_file_locked()
            RUN_SUMMARY.increment("company_memory_updates")

    def rewrite_file_locked(self):
        with open(self.filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=COMPANY_MEMORY_FIELDNAMES)
            writer.writeheader()
            writer.writerows(self.memory.values())


COMPANY_MEMORY = None


def clean_google_href(href: str) -> str:
    if not href:
        return ""

    href = href.strip()

    if href.startswith("/url?q="):
        parsed = urllib.parse.urlparse(href)
        query_params = urllib.parse.parse_qs(parsed.query)
        return query_params.get("q", [""])[0].strip()

    return href


def extract_result_link(result) -> tuple[str, str]:
    title_tag = result.select_one("h3")
    if not title_tag:
        return "", ""

    anchor = title_tag.find_parent("a", href=True)
    if not anchor:
        anchor = result.select_one("a[href]")

    if not anchor:
        return "", ""

    href = clean_google_href(anchor.get("href", ""))
    title = title_tag.get_text(" ", strip=True)

    return title, href


def build_google_title_query(allowed_phrases: list[str]) -> str:
    if len(allowed_phrases) == 1:
        return f'"{allowed_phrases[0]}"'

    return "(" + " OR ".join(f'"{phrase}"' for phrase in allowed_phrases) + ")"


def build_search_url(
    allowed_phrases: list[str],
    location_query: str,
    site_query: str,
    page_num: int,
) -> str:
    job_title_query = build_google_title_query(allowed_phrases)

    full_query = f"""
        {job_title_query}
        {site_query}
        {location_query}
        {COMMON_NEGATIVE_TITLE_QUERY}
    """

    cleaned_query = " ".join(full_query.split())
    encoded_query = urllib.parse.quote_plus(cleaned_query)
    start_param = page_num * 10

    print("\nGoogle query:")
    print(cleaned_query)


    ## time frame todo
    return (
        f"{GOOGLE_SEARCH_BASE}{encoded_query}"
        f"&tbs=qdr:h80"
        f"&filter=0"
        f"&num=10"
        f"&start={start_param}"
    )


def is_google_blocked(driver, soup: BeautifulSoup) -> bool:
    page_text = soup.get_text(" ", strip=True).lower()
    title = (driver.title or "").lower()

    return (
        "our systems have detected unusual traffic" in page_text
        or "to continue, please type the characters" in page_text
        or "unusual traffic" in page_text
        or "sorry" in title
    )


def build_link_row(
    ats_group: str,
    location_group: str,
    job_title_label: str,
    title: str,
    normalized_url: str,
    host: str,
    page_num: int,
    allowed_phrases: list[str],
) -> dict:
    title_status, title_reason = get_title_match_status(title, allowed_phrases)
    company, job_id, company_job_key = extract_company_job_key(normalized_url)

    return {
        "ats_group": ats_group,
        "location_group": location_group,
        "search_bucket": job_title_label,
        "title": title,
        "title_match_status": title_status,
        "title_reject_reason": title_reason,
        "url": normalized_url,
        "display_domain": host,
        "company_guess": company,
        "job_id_guess": job_id,
        "canonical_company_job_key": company_job_key,
        "page_number": page_num + 1,
    }


def handle_runtime_control_flags(
    accepted_csv: str,
    rejected_title_csv: str,
    yesterday_csv: str,
    location_accepted_rows: list[dict],
    location_rejected_title_rows: list[dict],
    location_yesterday_duplicate_rows: list[dict],
) -> tuple[str, int, int, int]:
    if should_stop_full_run():
        RUN_SUMMARY.increment("manual_stop_run_requests")
        print(" -> Stop-full-run flag detected. Saving current rows before exit.")

        accepted_added, rejected_added, yesterday_added = flush_location_rows(
            accepted_csv=accepted_csv,
            rejected_title_csv=rejected_title_csv,
            yesterday_csv=yesterday_csv,
            location_accepted_rows=location_accepted_rows,
            location_rejected_title_rows=location_rejected_title_rows,
            location_yesterday_duplicate_rows=location_yesterday_duplicate_rows,
        )

        return "stop", accepted_added, rejected_added, yesterday_added

    if should_skip_current_query():
        RUN_SUMMARY.increment("manual_skip_query_requests")
        print(" -> Skip-current-query flag detected. Saving current rows and moving to next query.")

        accepted_added, rejected_added, yesterday_added = flush_location_rows(
            accepted_csv=accepted_csv,
            rejected_title_csv=rejected_title_csv,
            yesterday_csv=yesterday_csv,
            location_accepted_rows=location_accepted_rows,
            location_rejected_title_rows=location_rejected_title_rows,
            location_yesterday_duplicate_rows=location_yesterday_duplicate_rows,
        )

        return "skip_query", accepted_added, rejected_added, yesterday_added

    return "continue", 0, 0, 0


def handle_google_page_error(
    error: Exception,
    accepted_csv: str,
    rejected_title_csv: str,
    yesterday_csv: str,
    location_accepted_rows: list[dict],
    location_rejected_title_rows: list[dict],
    location_yesterday_duplicate_rows: list[dict],
) -> tuple[int, int, int]:
    RUN_SUMMARY.increment("google_page_errors")
    RUN_SUMMARY.set_value("google_error_message", str(error))

    print(f"\nGoogle page/browser error: {error}")

    accepted_added, rejected_added, yesterday_added = flush_location_rows(
        accepted_csv=accepted_csv,
        rejected_title_csv=rejected_title_csv,
        yesterday_csv=yesterday_csv,
        location_accepted_rows=location_accepted_rows,
        location_rejected_title_rows=location_rejected_title_rows,
        location_yesterday_duplicate_rows=location_yesterday_duplicate_rows,
    )

    print("Saved current collected rows before moving forward.")

    return accepted_added, rejected_added, yesterday_added


def collect_google_links(start_time, yesterday_links: set[str], date_suffix: str):
    accepted_csv = os.path.join(CSV_DIR, f"google_jobs_paginated_new_{date_suffix}.csv")
    rejected_title_csv = os.path.join(CSV_DIR, f"google_jobs_rejected_titles_{date_suffix}.csv")
    yesterday_csv = os.path.join(CSV_DIR, f"google_jobs_seen_yesterday_{date_suffix}.csv")

    seen_all_urls = set()
    seen_all_urls.update(get_existing_urls_from_csv(accepted_csv))
    seen_all_urls.update(get_existing_urls_from_csv(rejected_title_csv))
    seen_all_urls.update(get_existing_urls_from_csv(yesterday_csv))

    all_found_today_links = set()
    rejected_domains = {}

    total_accepted = 0
    total_rejected_title = 0
    total_yesterday_duplicates = 0

    total_queries = len(ATS_SEARCH_GROUPS) * len(LOCATION_SEARCHES) * len(JOB_SEARCHES)
    current_query_number = 0

    checkpoint = load_checkpoint(date_suffix)
    last_completed_query_index = get_last_completed_query_index(checkpoint)

    if last_completed_query_index >= 0:
        print(f"\nResume enabled. Last completed Google query index: {last_completed_query_index}")
        print("Completed queries will be skipped. Current unfinished query will restart from page 1.")

    RUN_SUMMARY.set_value("total_google_queries_planned", total_queries)

    print(f"\nTotal Google search queries planned: {total_queries}")
    print("Launching browser for Google search...")

    driver = None

    try:
        driver = create_driver(headless=False)

    except Exception as e:
        RUN_SUMMARY.increment("google_page_errors")
        RUN_SUMMARY.set_value("google_error_message", str(e))
        RUN_SUMMARY.set_value("google_search_stopped_due_to_error", True)

        print(f"\nCould not launch Google search browser: {e}")
        print("Skipping Google search and moving to JD extraction using existing accepted CSV.")
        return set()

    try:
        for ats_group_data in ATS_SEARCH_GROUPS:
            ats_group = ats_group_data["ats_group"]
            site_query = ats_group_data["site_query"]

            for location_data in LOCATION_SEARCHES:
                location_group = location_data["location_group"]
                location_query = location_data["query"]

                location_accepted_rows = []
                location_rejected_title_rows = []
                location_yesterday_duplicate_rows = []

                print("\n==============================")
                print(f"Starting location query: {location_group}")
                print(f"ATS group: {ats_group}")
                print("==============================")

                for job_title_label, allowed_phrases in JOB_SEARCHES:
                    current_query_number += 1
                    current_query_index = current_query_number - 1

                    query_label = (
                        f"ATS={ats_group} | "
                        f"Location={location_group} | "
                        f"Bucket={job_title_label}"
                    )

                    if should_skip_completed_query(current_query_index, last_completed_query_index):
                        print(
                            f" -> Skipping completed query "
                            f"{current_query_number}/{total_queries}: {query_label}"
                        )
                        continue

                    RUN_SUMMARY.set_value("last_google_query_number", current_query_number)
                    RUN_SUMMARY.set_value("last_google_query_label", query_label)

                    print("\n##################################################")
                    print(f"Running query {current_query_number}/{total_queries}: {query_label}")
                    print("##################################################")

                    max_pages_for_ats = ATS_MAX_PAGES.get(
                        ats_group,
                        DEFAULT_MAX_PAGES_PER_QUERY,
                    )

                    print(f"Max Google pages for ATS group '{ats_group}': {max_pages_for_ats}")

                    query_completed_normally = False

                    # Smart exhaustion detection:
                    # Keep requesting explicit start=0,10,20,... offsets, but stop once
                    # Google itself appears to have run out of distinct result pages.
                    #
                    # IMPORTANT: this is intentionally independent of seen_all_urls and
                    # yesterday_links. A Google page may contain only jobs we've already
                    # seen and still be a real page with later pages available.
                    previous_google_page_urls = None
                    consecutive_empty_google_pages = 0
                    MAX_CONSECUTIVE_EMPTY_GOOGLE_PAGES = 2

                    for page_num in range(max_pages_for_ats):
                        search_url = build_search_url(
                            allowed_phrases=allowed_phrases,
                            location_query=location_query,
                            site_query=site_query,
                            page_num=page_num,
                        )

                        print(
                            f"\nSearching: query {current_query_number}/{total_queries} | "
                            f"{ats_group} | {location_group} | {job_title_label} | "
                            f"Page {page_num + 1}/{max_pages_for_ats}"
                        )

                        try:
                            print("\n==============================================")
                            print(f"REQUESTING GOOGLE PAGE: {page_num + 1}")
                            print(f"EXPECTED START PARAM: {page_num * 10}")
                            print(f"REQUESTED URL: {search_url}")
                            print("==============================================")

                            driver.get(search_url)
                            time.sleep(random.uniform(6, 12))

                            print("\n==============================================")
                            print(f"ACTUAL GOOGLE URL: {driver.current_url}")
                            print(f"BROWSER TITLE: {driver.title}")
                            print("==============================================")

                            soup = BeautifulSoup(driver.page_source, "html.parser")

                        except Exception as e:
                            accepted_added, rejected_added, yesterday_added = handle_google_page_error(
                                error=e,
                                accepted_csv=accepted_csv,
                                rejected_title_csv=rejected_title_csv,
                                yesterday_csv=yesterday_csv,
                                location_accepted_rows=location_accepted_rows,
                                location_rejected_title_rows=location_rejected_title_rows,
                                location_yesterday_duplicate_rows=location_yesterday_duplicate_rows,
                            )

                            total_accepted += accepted_added
                            total_rejected_title += rejected_added
                            total_yesterday_duplicates += yesterday_added

                            should_stop = STOP_GOOGLE_SEARCH_ON_BROWSER_ERROR
                            error_count = RUN_SUMMARY.get_value("google_page_errors", 0)

                            if should_stop or error_count >= MAX_GOOGLE_PAGE_ERRORS_BEFORE_STOP:
                                RUN_SUMMARY.set_value(
                                    "google_search_stopped_due_to_error",
                                    True,
                                )

                                print(
                                    "Stopping Google search safely and "
                                    "moving to JD extraction."
                                )

                                raise GoogleSearchStoppedError(str(e))

                            sleep_random(
                                WAIT_BETWEEN_GOOGLE_SEARCHES,
                                "after Google page error",
                            )

                            continue

                        # ---------------------------------------------------
                        # Google blocking / CAPTCHA detection
                        # ---------------------------------------------------
                        if is_google_blocked(driver, soup):
                            RUN_SUMMARY.increment("google_blocks_detected")

                            print(
                                f" -> Google block detected on page "
                                f"{page_num + 1}."
                            )

                            sleep_random(
                                WAIT_AFTER_GOOGLE_BLOCK,
                                "Google block detected",
                            )

                            # Do NOT treat a blocked page as an empty-results page.
                            # Move forward without increasing no-new-page counter.
                            continue

                        # ---------------------------------------------------
                        # Find Google result containers
                        # ---------------------------------------------------
                        search_results = soup.select(
                            "div.g, div.MjjYud, div.yuRUbf"
                        )

                        parsed_links = 0
                        ats_links = 0
                        accepted_links = 0
                        rejected_title_links = 0
                        duplicate_links = 0
                        yesterday_duplicate_links = 0

                        # Every external result URL Google showed on THIS page.
                        # Track this before ATS filtering and our own deduplication.
                        google_page_urls = set()

                        # ---------------------------------------------------
                        # Parse results
                        # ---------------------------------------------------
                        for result in search_results:
                            title, final_url = extract_result_link(result)

                            if not title or not final_url:
                                continue

                            if not final_url.startswith("http"):
                                continue

                            normalized_url = canonicalize_ats_job_url(final_url)
                            host = normalize_domain(normalized_url)

                            if "google.com" in host:
                                continue

                            # Track Google's result page independently of our ATS/domain
                            # filters and independently of whether we've seen the job before.
                            google_page_urls.add(normalized_url)

                            parsed_links += 1

                            # Ignore domains outside our supported ATS list.
                            if not is_allowed_ats_url(normalized_url):
                                rejected_domains[host] = (
                                        rejected_domains.get(host, 0) + 1
                                )
                                continue

                            ats_links += 1

                            # Track every valid ATS URL found by Google today.
                            all_found_today_links.add(normalized_url)

                            row = build_link_row(
                                ats_group=ats_group,
                                location_group=location_group,
                                job_title_label=job_title_label,
                                title=title,
                                normalized_url=normalized_url,
                                host=host,
                                page_num=page_num,
                                allowed_phrases=allowed_phrases,
                            )

                            # ---------------------------------------------------
                            # Yesterday duplicate handling
                            # ---------------------------------------------------
                            if normalized_url in yesterday_links:
                                yesterday_duplicate_links += 1
                                location_yesterday_duplicate_rows.append(row)

                                if SKIP_LINKS_SEEN_YESTERDAY:
                                    continue

                            # ---------------------------------------------------
                            # Current-run / existing CSV duplicate handling
                            # ---------------------------------------------------
                            if normalized_url in seen_all_urls:
                                duplicate_links += 1
                                continue

                            seen_all_urls.add(normalized_url)

                            # ---------------------------------------------------
                            # Title filtering
                            # ---------------------------------------------------
                            if row["title_match_status"] != "accepted":
                                location_rejected_title_rows.append(row)
                                rejected_title_links += 1
                                continue

                            location_accepted_rows.append(row)
                            accepted_links += 1

                        # ---------------------------------------------------
                        # Page diagnostics
                        # ---------------------------------------------------
                        print(f" -> Google result containers: {len(search_results)}")
                        print(f" -> Parsed links on page: {parsed_links}")
                        print(f" -> ATS links found: {ats_links}")
                        print(f" -> Accepted links collected: {accepted_links}")
                        print(
                            f" -> Rejected-title links collected: "
                            f"{rejected_title_links}"
                        )
                        print(f" -> Duplicate links skipped: {duplicate_links}")
                        print(
                            f" -> Links seen yesterday: "
                            f"{yesterday_duplicate_links}"
                        )

                        # ---------------------------------------------------
                        # Runtime manual controls
                        # ---------------------------------------------------
                        (
                            control_action,
                            accepted_added,
                            rejected_added,
                            yesterday_added,
                        ) = handle_runtime_control_flags(
                            accepted_csv=accepted_csv,
                            rejected_title_csv=rejected_title_csv,
                            yesterday_csv=yesterday_csv,
                            location_accepted_rows=location_accepted_rows,
                            location_rejected_title_rows=location_rejected_title_rows,
                            location_yesterday_duplicate_rows=location_yesterday_duplicate_rows,
                        )

                        total_accepted += accepted_added
                        total_rejected_title += rejected_added
                        total_yesterday_duplicates += yesterday_added

                        if control_action == "stop":
                            raise SystemExit

                        if control_action == "skip_query":
                            query_completed_normally = True

                            sleep_random(
                                WAIT_BETWEEN_GOOGLE_SEARCHES,
                                "before next Google search",
                            )

                            break

                        # ---------------------------------------------------
                        # Smart Google pagination exhaustion detection
                        # ---------------------------------------------------
                        requested_start = page_num * 10

                        actual_start = None
                        try:
                            actual_query_params = parse_qs(
                                urlparse(driver.current_url).query
                            )
                            if "start" in actual_query_params:
                                actual_start = int(
                                    actual_query_params["start"][0] or 0
                                )
                        except Exception:
                            actual_start = None

                        print(
                            f" -> Requested Google start offset: {requested_start}"
                        )
                        print(
                            f" -> Actual Google start offset: "
                            f"{actual_start if actual_start is not None else 'not present'}"
                        )
                        print(
                            f" -> Google result URLs on this page: "
                            f"{len(google_page_urls)}"
                        )

                        # Signal 1: Google explicitly redirected us backward to an
                        # earlier start offset. Only use this signal when Google kept
                        # a start parameter in the final URL.
                        if (
                            page_num > 0
                            and actual_start is not None
                            and actual_start < requested_start
                        ):
                            print(
                                " -> Google redirected to an earlier results page."
                            )
                            print(
                                " -> No additional Google pages appear to exist."
                            )
                            query_completed_normally = True
                            break

                        # Signal 2: Google returned the exact same result URL set as
                        # the immediately previous page. This compares page-to-page,
                        # NOT against CSV/history dedupe state.
                        if (
                            previous_google_page_urls is not None
                            and google_page_urls
                            and google_page_urls == previous_google_page_urls
                        ):
                            print(
                                " -> Google repeated the exact previous result page."
                            )
                            print(
                                " -> Treating this as the end of available pages."
                            )
                            query_completed_normally = True
                            break

                        # Signal 3: no external Google result URLs were parsed.
                        # Require two consecutive empty pages to avoid stopping on a
                        # one-off Google markup/parser glitch.
                        if not google_page_urls:
                            consecutive_empty_google_pages += 1
                            print(
                                f" -> No Google result URLs detected. "
                                f"Empty-page count: "
                                f"{consecutive_empty_google_pages}/"
                                f"{MAX_CONSECUTIVE_EMPTY_GOOGLE_PAGES}"
                            )
                        else:
                            consecutive_empty_google_pages = 0

                        if (
                            consecutive_empty_google_pages
                            >= MAX_CONSECUTIVE_EMPTY_GOOGLE_PAGES
                        ):
                            print(
                                " -> Two consecutive Google pages contained "
                                "no result URLs."
                            )
                            print(" -> Ending this query.")
                            query_completed_normally = True
                            break

                        if google_page_urls:
                            previous_google_page_urls = set(google_page_urls)

                        # ---------------------------------------------------
                        # Timing / delay before next page
                        # ---------------------------------------------------
                        end_time = time.perf_counter()

                        print(
                            f" -> Total elapsed runtime: "
                            f"{end_time - start_time:.2f} seconds"
                        )

                        # Don't sleep after the final configured page.
                        if page_num < max_pages_for_ats - 1:
                            sleep_random(
                                WAIT_BETWEEN_GOOGLE_PAGES,
                                "before next Google results page",
                            )

                    else:
                        # Reached max_pages_for_ats without breaking.
                        query_completed_normally = True

                    if query_completed_normally:
                        accepted_added, rejected_added, yesterday_added = flush_location_rows(
                            accepted_csv=accepted_csv,
                            rejected_title_csv=rejected_title_csv,
                            yesterday_csv=yesterday_csv,
                            location_accepted_rows=location_accepted_rows,
                            location_rejected_title_rows=location_rejected_title_rows,
                            location_yesterday_duplicate_rows=location_yesterday_duplicate_rows,
                        )

                        total_accepted += accepted_added
                        total_rejected_title += rejected_added
                        total_yesterday_duplicates += yesterday_added

                        save_checkpoint(date_suffix, {
                            "phase": "google_search",
                            "google": {
                                "last_completed_query_index": current_query_index,
                                "last_completed_query_number": current_query_number,
                                "last_completed_query_label": query_label,
                                "resume_behavior": "restart_unfinished_query_from_page_1",
                            },
                        })

                        last_completed_query_index = current_query_index

                        print(
                            f" -> Checkpoint saved. Completed query "
                            f"{current_query_number}/{total_queries}: {query_label}"
                        )
                        print(f" -> Rows flushed after query completion.")
                        print(f"    Accepted rows added: {accepted_added}")
                        print(f"    Rejected-title rows added: {rejected_added}")
                        print(f"    Yesterday-duplicate rows added: {yesterday_added}")

                accepted_added, rejected_added, yesterday_added = flush_location_rows(
                    accepted_csv=accepted_csv,
                    rejected_title_csv=rejected_title_csv,
                    yesterday_csv=yesterday_csv,
                    location_accepted_rows=location_accepted_rows,
                    location_rejected_title_rows=location_rejected_title_rows,
                    location_yesterday_duplicate_rows=location_yesterday_duplicate_rows,
                )

                total_accepted += accepted_added
                total_rejected_title += rejected_added
                total_yesterday_duplicates += yesterday_added

                print(f"\nSaved after location query: {ats_group} | {location_group}")
                print(f"New accepted rows added: {accepted_added}")
                print(f"New rejected-title rows added: {rejected_added}")
                print(f"New yesterday-duplicate rows added: {yesterday_added}")

    finally:
        print("\nClosing Google search browser...")
        safe_quit_driver(driver)

    RUN_SUMMARY.increment("accepted_links_added", total_accepted)
    RUN_SUMMARY.increment("rejected_title_links_added", total_rejected_title)
    RUN_SUMMARY.increment("yesterday_duplicate_links_added", total_yesterday_duplicates)
    RUN_SUMMARY.increment("links_found_today", len(all_found_today_links))

    print("\nGoogle link collection finished.")
    print(f"New accepted links added this run: {total_accepted}")
    print(f"New rejected-title links added this run: {total_rejected_title}")
    print(f"New yesterday duplicate links added this run: {total_yesterday_duplicates}")
    print(f"Total links found today for history: {len(all_found_today_links)}")

    if rejected_domains:
        print("\nTop rejected non-allowed domains:")
        for domain, count in sorted(rejected_domains.items(), key=lambda x: x[1], reverse=True)[:20]:
            print(f"  {domain}: {count}")

    return all_found_today_links


def fetch_page_html_fast(url: str) -> str:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/148.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }

    try:
        response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS)
        if response.status_code == 200 and len(response.text) >= MIN_HTML_LENGTH_FOR_REQUESTS:
            return response.text
    except Exception:
        return ""

    return ""


def clean_html_to_text(html: str) -> str:
    soup = BeautifulSoup(html or "", "html.parser")
    return normalize_space(soup.get_text(" ", strip=True))


def fix_common_mojibake(text: str) -> str:
    """
    Some Workday meta descriptions show characters like â or â¯
    when decoded poorly. This fixes the common UTF-8-as-Latin-1 issue.
    """
    if not text:
        return ""

    try:
        fixed = text.encode("latin1").decode("utf-8")
        if "â" in text and "â" not in fixed:
            return fixed
    except Exception:
        pass

    return text


def clean_meta_content(text: str) -> str:
    text = html_lib.unescape(text or "")
    text = html_lib.unescape(text)
    text = fix_common_mojibake(text)
    return normalize_space(text)


def get_meta_content(soup: BeautifulSoup, selectors: list[str]) -> str:
    for selector in selectors:
        tag = soup.select_one(selector)
        if tag and tag.get("content"):
            return clean_meta_content(tag.get("content", ""))

    return ""


def extract_between_markers(text: str, start_marker: str, end_markers: list[str]) -> str:
    if not text:
        return ""

    lower_text = text.lower()
    start_index = lower_text.find(start_marker.lower())

    if start_index == -1:
        return ""

    start_index += len(start_marker)

    end_index = len(text)

    for marker in end_markers:
        marker_index = lower_text.find(marker.lower(), start_index)
        if marker_index != -1:
            end_index = min(end_index, marker_index)

    return normalize_space(text[start_index:end_index])


def extract_workday_meta_data(soup: BeautifulSoup) -> dict:
    """
    Workday static HTML often has an empty React root, while the useful
    JD is stored in og:description / meta description.
    """
    meta_description = get_meta_content(soup, [
        'meta[property="og:description"]',
        'meta[name="description"]',
    ])

    title = get_meta_content(soup, [
        'meta[property="og:title"]',
        'meta[name="title"]',
    ])

    canonical_tag = soup.select_one('link[rel="canonical"]')
    canonical_url = canonical_tag.get("href", "") if canonical_tag else ""

    location = extract_between_markers(
        meta_description,
        "All Job Posting Locations:",
        [
            "Job Description:",
            "Required Skills:",
            "Preferred Skills:",
            "The anticipated base pay range",
        ],
    )

    if not location:
        location = extract_between_markers(
            meta_description,
            "The position will be located in",
            [
                ".",
                "#",
                "Johnson & Johnson",
            ],
        )

    jd = extract_between_markers(
        meta_description,
        "Job Description:",
        [
            "Required Skills:",
            "Preferred Skills:",
            "The anticipated base pay range",
            "Additional Description for Pay Transparency:",
            "Johnson & Johnson is an Equal Opportunity Employer.",
            "Do Not Sell or Share My Personal Information",
        ],
    )

    if not jd:
        jd = meta_description

    jd_parts = [
        title,
        location,
        jd,
    ]

    return {
        "job_description": normalize_space(" ".join(part for part in jd_parts if part)),
        "location": normalize_space(location),
        "source": "workday_meta_description",
        "canonical_url": canonical_url,
    }


def extract_workday_location(soup: BeautifulSoup) -> str:
    data = extract_workday_meta_data(soup)
    return normalize_space(data.get("location", ""))


def extract_braced_json_after_marker(text: str, marker: str) -> str:
    if not text or marker not in text:
        return ""

    marker_index = text.find(marker)
    start = text.find("{", marker_index)

    if start == -1:
        return ""

    depth = 0
    in_string = False
    escape = False

    for index in range(start, len(text)):
        char = text[index]

        if escape:
            escape = False
            continue

        if char == "\\":
            escape = True
            continue

        if char == '"':
            in_string = not in_string
            continue

        if in_string:
            continue

        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1

            if depth == 0:
                return text[start:index + 1]

    return ""


def extract_window_app_data(soup: BeautifulSoup) -> dict:
    for script in soup.find_all("script"):
        script_text = script.string or script.get_text("", strip=False)

        if "window.__appData" not in script_text:
            continue

        raw_json = extract_braced_json_after_marker(script_text, "window.__appData")

        if not raw_json:
            continue

        try:
            return json.loads(raw_json)
        except json.JSONDecodeError:
            continue

    return {}


def extract_address_location(address: dict) -> str:
    if not isinstance(address, dict):
        return ""

    return normalize_space(", ".join(
        part for part in [
            address.get("addressLocality"),
            address.get("addressRegion"),
            address.get("addressCountry"),
        ]
        if part
    ))


def extract_ashby_posting_data(soup: BeautifulSoup) -> dict:
    app_data = extract_window_app_data(soup)
    posting = app_data.get("posting", {}) if app_data else {}

    if not posting:
        return {}

    description_parts = posting.get("descriptionParts") or {}
    description_body = description_parts.get("descriptionBody") or {}

    jd_text = (
        posting.get("descriptionPlainText")
        or posting.get("descriptionPlain")
        or description_body.get("plain")
        or clean_html_to_text(posting.get("descriptionHtml", ""))
        or clean_html_to_text(description_body.get("html", ""))
    )

    postal_address = (
        posting.get("address", {})
        .get("postalAddress", {})
    )

    location = (
        posting.get("locationName")
        or posting.get("locationExternalName")
        or extract_address_location(postal_address)
    )

    if not location and posting.get("isRemote") is True:
        location = "Remote"

    return {
        "job_description": normalize_space(jd_text),
        "location": normalize_space(location),
        "is_remote": posting.get("isRemote"),
        "workplace_type": posting.get("workplaceType"),
        "source": "ashby_window_app_data",
    }


def extract_ashby_location(soup: BeautifulSoup) -> str:
    data = extract_ashby_posting_data(soup)
    return normalize_space(data.get("location", ""))


def fetch_greenhouse_api_jd(url: str) -> tuple[str, str]:
    parsed = urlparse(url)
    host = normalize_domain(url)
    path_parts = [p for p in parsed.path.split("/") if p]

    if "greenhouse.io" not in host:
        return "", ""

    if len(path_parts) < 2:
        return "", ""

    board_token = path_parts[0]
    job_id = path_parts[-1]

    api_url = f"https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs/{job_id}"

    try:
        response = requests.get(api_url, timeout=REQUEST_TIMEOUT_SECONDS)
        if response.status_code != 200:
            return "", ""

        data = response.json()

        parts = [
            data.get("title", ""),
            data.get("location", {}).get("name", ""),
            clean_html_to_text(data.get("content", "")),
        ]

        jd_text = normalize_space(" ".join(parts)) + str(data.get("location", {}))

        if len(jd_text) >= MIN_JD_LENGTH:
            return jd_text, "greenhouse_api"

    except Exception:
        return "", ""

    return "", ""


def extract_visible_text(content):
    try:
        # Input is already plain text
        if isinstance(content, str):
            return normalize_space(content)

        # Input is a BeautifulSoup object
        for tag in content.find_all(["script", "style", "noscript"]):
            tag.decompose()

        return normalize_space(content.get_text(" ", strip=True))

    except Exception as e:
        print(f"Failed to extract visible text: {e}")
        return ""


def extract_jsonld_text(soup: BeautifulSoup) -> str:
    parts = []

    for script in soup.select('script[type="application/ld+json"]'):
        content = script.get_text(" ", strip=True)
        if content:
            parts.append(content)

    return normalize_space(" ".join(parts))


def extract_jd_text_by_domain(soup: BeautifulSoup, domain: str) -> str:
    if "greenhouse.io" in domain:
        selectors = ["#content", ".app_body", ".job__description", ".content", "main", "body"]
    elif domain == "jobs.lever.co":
        selectors = [".posting-page", ".section-wrapper", ".content", "main", "body"]
    elif domain == "jobs.ashbyhq.com":
        ashby_data = extract_ashby_posting_data(soup)
        ashby_jd = ashby_data.get("job_description", "")

        if len(ashby_jd) >= MIN_JD_LENGTH:
            return ashby_jd

        selectors = [
            "[data-testid='job-posting-description']",
        ]
    elif domain.endswith(".myworkdayjobs.com"):
        workday_data = extract_workday_meta_data(soup)
        workday_jd = workday_data.get("job_description", "")

        if len(workday_jd) >= MIN_JD_LENGTH:
            return workday_jd

        selectors = [
            "[data-automation-id='jobPostingDescription']",
            "[data-automation-id='jobPostingPage']",
            "main",
        ]
    elif domain == "remoterocketship.com":
        selectors = [
            "[data-testid='job-description']",
            ".job-description",
            ".jobDescription",
            ".description",
            "article",
            "main",
            "body",
        ]
    elif domain == "levels.fyi":
        selectors = [
            "[data-testid='job-description']",
            ".job-description",
            ".description",
            "article",
            "main",
            "body",
        ]
    else:
        selectors = [
            "[data-testid='job-description']",
            ".job-description",
            "#job-description",
            ".description",
            "#description",
            ".posting",
            ".posting-description",
            ".content",
            "main",
            "body",
        ]

    for selector in selectors:
        tag = soup.select_one(selector)
        if tag:
            text = normalize_space(tag.get_text(" ", strip=True))
            if len(text) >= MIN_JD_LENGTH:
                return text

    if domain == "jobs.ashbyhq.com":
        return ""

    if domain.endswith(".myworkdayjobs.com"):
        workday_data = extract_workday_meta_data(soup)
        return workday_data.get("job_description", "")

    return extract_visible_text(soup)


def evaluate_jd_quality(jd_text: str, title: str = "") -> tuple[str, list[str]]:
    reasons = []
    text = normalize_lower(jd_text)
    title_norm = normalize_lower(title)

    if not text:
        return "bad", ["empty_jd_text"]

    if len(text) < 300:
        reasons.append("very_short_jd_text")
    elif len(text) < MIN_JD_LENGTH:
        reasons.append("short_jd_text")

    bad_hits = [marker for marker in BAD_JD_MARKERS if marker in text]
    if bad_hits:
        reasons.append("bad_jd_marker:" + ",".join(bad_hits[:3]))

    good_hits = [marker for marker in GOOD_JD_MARKERS if marker in text]
    if not good_hits and len(text) < 2500:
        reasons.append("missing_good_jd_sections")

    title_words = [
        word for word in re.split(r"\W+", title_norm)
        if len(word) >= 4 and word not in {"jobs", "remote", "engineer", "developer", "software"}
    ]

    if title_words and len(text) > 300:
        matched_title_words = [word for word in title_words if word in text]
        if not matched_title_words:
            reasons.append("possible_title_jd_mismatch")

    if any(reason.startswith("bad_jd_marker") for reason in reasons):
        return "bad", reasons

    if "very_short_jd_text" in reasons:
        return "bad", reasons

    if reasons:
        return "weak", reasons

    return "good", []


def resolve_possible_redirect_href(href: str, base_url: str) -> str:
    if not href:
        return ""

    href = href.strip()

    if href.startswith("mailto:") or href.startswith("tel:") or href.startswith("#"):
        return ""

    full_url = urljoin(base_url, href)
    parsed = urlparse(full_url)

    query = parse_qs(parsed.query)

    for key in ["url", "u", "target", "redirect", "redirect_url", "to", "application_url"]:
        if key in query and query[key]:
            possible = query[key][0]
            if possible.startswith("http"):
                return canonicalize_ats_job_url(possible)

    return canonicalize_ats_job_url(full_url)


def extract_application_url_from_soup(soup: BeautifulSoup, page_url: str) -> str:
    page_host = normalize_domain(page_url)

    if page_host not in {"remoterocketship.com", "levels.fyi", "ziprecruiter.com"}:
        return ""

    skip_domains = {
        page_host,
        "facebook.com",
        "twitter.com",
        "x.com",
        "linkedin.com",
        "instagram.com",
        "youtube.com",
        "google.com",
    }

    candidates = []

    for anchor in soup.select("a[href]"):
        raw_href = anchor.get("href", "")
        text = normalize_lower(anchor.get_text(" ", strip=True))
        candidate_url = resolve_possible_redirect_href(raw_href, page_url)

        if not candidate_url or not candidate_url.startswith("http"):
            continue

        candidate_host = normalize_domain(candidate_url)

        if candidate_host in skip_domains:
            continue

        if candidate_url.lower().endswith((".png", ".jpg", ".jpeg", ".svg", ".webp", ".pdf")):
            continue

        score = 0

        if "apply" in text:
            score += 10
        if "apply now" in text:
            score += 15
        if "view job" in text or "view role" in text:
            score += 8
        if "company" in text or "career" in text:
            score += 5
        if is_allowed_ats_url(candidate_url):
            score += 20
        if "jobs" in urlparse(candidate_url).path.lower() or "careers" in urlparse(candidate_url).path.lower():
            score += 5

        if score > 0:
            candidates.append((score, candidate_url))

    if not candidates:
        return ""

    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]


def get_application_dedupe_key(application_url: str, fallback_url: str, company_job_key: str) -> str:
    if application_url:
        return canonicalize_ats_job_url(application_url)

    if company_job_key:
        return company_job_key

    return canonicalize_ats_job_url(fallback_url)


def wait_for_real_jd(driver, domain: str, title: str = "", timeout_seconds: int = 14) -> str:
    end_time = time.time() + timeout_seconds
    best_text = ""

    while time.time() < end_time:
        soup = BeautifulSoup(driver.page_source, "html.parser")
        jd_text = extract_jd_text_by_domain(soup, domain)

        if len(jd_text) > len(best_text):
            best_text = jd_text

        quality_status, _ = evaluate_jd_quality(jd_text=jd_text, title=title)

        if quality_status == "good":
            return jd_text

        time.sleep(1)

    return best_text


def extract_with_requests_or_selenium(driver, url: str, domain: str, title: str = "", force_selenium: bool = False):
    url = canonicalize_ats_job_url(url)
    if "apply".upper() in url[-8:].upper():
        url = url.replace("apply", "")

    if not force_selenium and "greenhouse.io" in domain:
        jd_text, method = fetch_greenhouse_api_jd(url)
        if jd_text:
            soup = BeautifulSoup(jd_text, "html.parser")
            RUN_SUMMARY.increment("request_extractions")
            return soup, jd_text, method

    extraction_method = "requests"

    if not force_selenium:
        html = fetch_page_html_fast(url)

        if html:
            soup = BeautifulSoup(html, "html.parser")
            jd_text = extract_jd_text_by_domain(soup, domain)

            quality_status, _ = evaluate_jd_quality(jd_text, title=title)

            if quality_status == "good":
                RUN_SUMMARY.increment("request_extractions")
                return soup, jd_text, extraction_method

    extraction_method = "selenium_fallback"
    RUN_SUMMARY.increment("selenium_fallback_extractions")

    driver.get(url)
    time.sleep(random.uniform(3, 5))

    try:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight * 0.35);")
        time.sleep(1)
    except Exception:
        pass

    jd_text = wait_for_real_jd(driver, domain, title=title, timeout_seconds=14)
    soup = BeautifulSoup(driver.page_source, "html.parser")

    return soup, jd_text, extraction_method


def parse_iso_datetime(value: str):
    try:
        value = value.strip()
        if value.endswith("Z"):
            value = value.replace("Z", "+00:00")
        return datetime.fromisoformat(value)
    except Exception:
        return None


def extract_date_from_text(text: str):
    if not text:
        return None, "", ""

    patterns = [
        r"\b(?:posted|date posted|published|listing date)\s*[:\-]?\s*([A-Za-z]{3,9}\s+\d{1,2},\s+\d{4})\b",
        r"\b(?:posted|date posted|published|listing date)\s*[:\-]?\s*(\d{1,2}/\d{1,2}/\d{4})\b",
        r"\b(?:posted|date posted|published|listing date)\s*[:\-]?\s*(\d{4}-\d{2}-\d{2})\b",
        r"\b([A-Za-z]{3,9}\s+\d{1,2},\s+\d{4})\b",
        r"\b(\d{1,2}/\d{1,2}/\d{4})\b",
        r"\b(\d{4}-\d{2}-\d{2})\b",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if not match:
            continue

        raw = match.group(1).strip()

        for fmt in ("%B %d, %Y", "%b %d, %Y", "%m/%d/%Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(raw, fmt), raw, "visible_text"
            except ValueError:
                pass

    return None, "", ""


def extract_relative_age_days(text: str):
    t = normalize_lower(text)

    hour_match = re.search(r"\b(\d+)\s+hour[s]?\s+ago\b", t)
    if hour_match:
        return int(hour_match.group(1)) / 24.0, hour_match.group(0), "relative_text"

    day_match = re.search(r"\b(\d+)\+?\s+day[s]?\s+ago\b", t)
    if day_match:
        return float(day_match.group(1)), day_match.group(0), "relative_text"

    if re.search(r"\b(today|just posted|posted today)\b", t):
        return 0.0, "today", "relative_text"

    if re.search(r"\b(yesterday|posted yesterday)\b", t):
        return 1.0, "yesterday", "relative_text"

    return None, "", ""


def extract_posted_date_status(soup: BeautifulSoup, full_text: str):
    now = datetime.now()
    jsonld_text = extract_jsonld_text(soup)

    for field_name in ["datePosted", "datePublished"]:
        match = re.search(rf'"{field_name}"\s*:\s*"([^"]+)"', jsonld_text, re.IGNORECASE)
        if match:
            raw = match.group(1).strip()
            dt = parse_iso_datetime(raw)
            if dt:
                naive_dt = dt.replace(tzinfo=None) if dt.tzinfo else dt
                age_days = (now - naive_dt).total_seconds() / 86400.0

                if age_days <= STRICT_DAYS_LIMIT:
                    return "recent", raw, f"jsonld:{field_name}", round(age_days, 2)

                return "old", raw, f"jsonld:{field_name}", round(age_days, 2)

    meta_candidates = [
        ("meta[property='article:published_time']", "content"),
        ("meta[name='article:published_time']", "content"),
        ("meta[name='publish-date']", "content"),
        ("meta[name='date']", "content"),
        ("meta[itemprop='datePosted']", "content"),
        ("meta[itemprop='datePublished']", "content"),
    ]

    for selector, attr in meta_candidates:
        tag = soup.select_one(selector)
        if tag and tag.get(attr):
            raw = tag.get(attr).strip()
            dt = parse_iso_datetime(raw)
            if dt:
                naive_dt = dt.replace(tzinfo=None) if dt.tzinfo else dt
                age_days = (now - naive_dt).total_seconds() / 86400.0

                if age_days <= STRICT_DAYS_LIMIT:
                    return "recent", raw, selector, round(age_days, 2)

                return "old", raw, selector, round(age_days, 2)

    for time_tag in soup.select("time"):
        raw = time_tag.get("datetime") or time_tag.get_text(" ", strip=True)
        if not raw:
            continue

        dt = parse_iso_datetime(raw)

        if dt:
            naive_dt = dt.replace(tzinfo=None) if dt.tzinfo else dt
            age_days = (now - naive_dt).total_seconds() / 86400.0

            if age_days <= STRICT_DAYS_LIMIT:
                return "recent", raw, "time", round(age_days, 2)

            return "old", raw, "time", round(age_days, 2)

    rel_days, rel_raw, rel_source = extract_relative_age_days(full_text)
    if rel_days is not None:
        if rel_days <= STRICT_DAYS_LIMIT:
            return "recent", rel_raw, rel_source, round(rel_days, 2)

        return "old", rel_raw, rel_source, round(rel_days, 2)

    dt, raw, source = extract_date_from_text(full_text)
    if dt:
        age_days = (now - dt).total_seconds() / 86400.0

        if age_days <= STRICT_DAYS_LIMIT:
            return "recent", raw, source, round(age_days, 2)

        return "old", raw, source, round(age_days, 2)

    return "no_date_found", "", "", ""


def find_matching_patterns(text: str, patterns: list[str]) -> list[str]:
    lower_text = normalize_lower(text)
    matches = []

    for pattern in patterns:
        if re.search(pattern, lower_text, re.IGNORECASE):
            matches.append(pattern)

    return matches


def split_sentences(text: str) -> list[str]:
    text = normalize_space(text)
    return re.split(r"(?<=[.!?])\s+", text)


def extract_matching_sentence(text: str, patterns: list[str], max_chars: int = 350) -> str:
    if not text:
        return ""

    sentences = split_sentences(text)

    for sentence in sentences:
        lower_sentence = sentence.lower()

        for pattern in patterns:
            if re.search(pattern, lower_sentence, re.IGNORECASE):
                return sentence[:max_chars]

    return ""


def infer_location_status(text: str) -> tuple[str, str]:
    lower_text = normalize_lower(text)

    non_us_hits = [x for x in NON_US_LOCATION_HINTS if x in lower_text]
    us_hits = [x for x in US_LOCATION_HINTS if x in lower_text]

    if non_us_hits and not us_hits:
        return "likely_non_us", ", ".join(non_us_hits[:5])

    if us_hits:
        return "likely_us", ", ".join(us_hits[:5])

    return "unknown", ""


def get_sponsorship_status(positive_matches: list[str], negative_matches: list[str]) -> str:
    if negative_matches:
        return "red_blocker_found"

    if positive_matches:
        return "green_positive_signal"

    return "yellow_no_info"


def build_known_no_sponsor_row(row: dict, memory_row: dict) -> dict:
    application_url = row.get("application_url", "")
    application_dedupe_key = get_application_dedupe_key(
        application_url=application_url,
        fallback_url=row.get("url", ""),
        company_job_key=row.get("canonical_company_job_key", ""),
    )

    return {
        **row,
        "application_url": application_url,
        "application_dedupe_key": application_dedupe_key,
        "decision": "rejected",
        "rejection_reasons": "known_company_no_sponsor",
        "posted_status": "skipped_known_company",
        "posted_value": "",
        "posted_source": "company_sponsorship_memory",
        "posted_age_days": "",
        "location_status": "unknown",
        "location_evidence": "",
        "sponsorship_status": "red_blocker_found",
        "positive_sponsorship_matches": "",
        "negative_sponsorship_matches": "company_memory_no_sponsor",
        "sponsorship_evidence_snippet": memory_row.get("evidence_snippet", ""),
        "positive_sponsorship_evidence_snippet": "",
        "clearance_matches": "",
        "clearance_evidence_snippet": "",
        "jd_quality_status": "skipped",
        "jd_quality_reasons": "known_company_no_sponsor",
        "jd_text_length": 0,
        "JD_Text": "",
        "extraction_method": "skipped_company_memory",
        "retry_attempted": "false",
        "error": "",
    }


def enrich_one_job_with_driver(driver, row: dict) -> dict:
    url = canonicalize_ats_job_url(row["url"])
    domain = row.get("display_domain") or normalize_domain(url)
    company_guess = row.get("company_guess", "")
    company_key = get_company_key(company_guess, domain)

    if SKIP_KNOWN_NO_SPONSOR_COMPANIES and COMPANY_MEMORY:
        if COMPANY_MEMORY.is_known_no_sponsor(company_key):
            RUN_SUMMARY.increment("known_no_sponsor_skipped")
            memory_row = COMPANY_MEMORY.get_memory_row(company_key)
            return build_known_no_sponsor_row(row, memory_row)

    retry_attempted = "false"
    extraction_method = "requests"

    try:
        soup, jd_text, extraction_method = extract_with_requests_or_selenium(
            driver=driver,
            url=url,
            domain=domain,
            title=row.get("title", ""),
            force_selenium=False,
        )

        quality_status, quality_reasons = evaluate_jd_quality(
            jd_text=jd_text,
            title=row.get("title", ""),
        )

        if quality_status != "good":
            retry_attempted = "true"
            RUN_SUMMARY.increment("jd_retries_attempted")

            soup, jd_text, extraction_method = extract_with_requests_or_selenium(
                driver=driver,
                url=url,
                domain=domain,
                title=row.get("title", ""),
                force_selenium=True,
            )

            quality_status, quality_reasons = evaluate_jd_quality(
                jd_text=jd_text,
                title=row.get("title", ""),
            )

            if quality_status == "good":
                RUN_SUMMARY.increment("jd_retries_successful")

        full_text = extract_visible_text(jd_text)

        structured_location = ""
        if domain == "jobs.ashbyhq.com":
            structured_location = extract_ashby_location(soup)
        elif domain.endswith(".myworkdayjobs.com"):
            structured_location = extract_workday_location(soup)

        application_url = extract_application_url_from_soup(soup, url)
        application_dedupe_key = get_application_dedupe_key(
            application_url=application_url,
            fallback_url=url,
            company_job_key=row.get("canonical_company_job_key", ""),
        )

        posted_status, posted_value, posted_source, posted_age_days = extract_posted_date_status(
            soup=soup,
            full_text=full_text,
        )

        positive_sponsorship_matches = find_matching_patterns(jd_text, SPONSORSHIP_POSITIVE_PATTERNS)
        negative_sponsorship_matches = find_matching_patterns(jd_text, SPONSORSHIP_REJECT_PATTERNS)
        clearance_matches = find_matching_patterns(jd_text, CLEARANCE_REJECT_PATTERNS)

        sponsorship_evidence = extract_matching_sentence(jd_text, SPONSORSHIP_REJECT_PATTERNS)
        positive_sponsorship_evidence = extract_matching_sentence(jd_text, SPONSORSHIP_POSITIVE_PATTERNS)
        clearance_evidence = extract_matching_sentence(jd_text, CLEARANCE_REJECT_PATTERNS)

        location_check_text = " ".join([
            row.get("title", ""),
            row.get("location_group", ""),
            row.get("display_domain", ""),
            structured_location,
            jd_text,
        ])

        location_status, location_evidence = infer_location_status(location_check_text)

        if structured_location:
            location_evidence = structured_location

        sponsorship_status = get_sponsorship_status(
            positive_matches=positive_sponsorship_matches,
            negative_matches=negative_sponsorship_matches,
        )

        rejection_reasons = []

        if posted_status == "old":
            rejection_reasons.append("old_posting")

        if negative_sponsorship_matches:
            rejection_reasons.append("sponsorship_blocker")

        if clearance_matches:
            rejection_reasons.append("clearance_or_citizenship_blocker")

        if location_status == "likely_non_us":
            rejection_reasons.append("likely_non_us_location")

        decision = "accepted" if not rejection_reasons else "rejected"

        if quality_status == "bad":
            decision = "needs_review"
            rejection_reasons.append("bad_or_incomplete_jd")
            rejection_reasons.extend(quality_reasons)

        elif quality_status == "weak":
            decision = "needs_review"
            rejection_reasons.append("weak_jd_quality")
            rejection_reasons.extend(quality_reasons)

        enriched_row = {
            **row,
            "url": url,
            "display_domain": domain,
            "application_url": application_url,
            "application_dedupe_key": application_dedupe_key,
            "decision": decision,
            "rejection_reasons": " | ".join(rejection_reasons),
            "posted_status": posted_status,
            "posted_value": posted_value,
            "posted_source": posted_source,
            "posted_age_days": posted_age_days,
            "location_status": location_status,
            "location_evidence": location_evidence,
            "sponsorship_status": sponsorship_status,
            "positive_sponsorship_matches": " | ".join(positive_sponsorship_matches),
            "negative_sponsorship_matches": " | ".join(negative_sponsorship_matches),
            "sponsorship_evidence_snippet": sponsorship_evidence,
            "positive_sponsorship_evidence_snippet": positive_sponsorship_evidence,
            "clearance_matches": " | ".join(clearance_matches),
            "clearance_evidence_snippet": clearance_evidence,
            "jd_quality_status": quality_status,
            "jd_quality_reasons": " | ".join(quality_reasons),
            "jd_text_length": len(jd_text),
            "JD_Text": jd_text,
            "extraction_method": extraction_method,
            "retry_attempted": retry_attempted,
            "error": "",
        }

        if COMPANY_MEMORY:
            COMPANY_MEMORY.update_from_enriched_row(enriched_row)

        return enriched_row

    except Exception as e:
        RUN_SUMMARY.increment("jd_errors")

        application_dedupe_key = get_application_dedupe_key(
            application_url="",
            fallback_url=url,
            company_job_key=row.get("canonical_company_job_key", ""),
        )

        return {
            **row,
            "url": url,
            "display_domain": domain,
            "application_url": "",
            "application_dedupe_key": application_dedupe_key,
            "decision": "needs_review",
            "rejection_reasons": "extraction_error",
            "posted_status": "error_no_date_found",
            "posted_value": "",
            "posted_source": "",
            "posted_age_days": "",
            "location_status": "unknown",
            "location_evidence": "",
            "sponsorship_status": "yellow_no_info",
            "positive_sponsorship_matches": "",
            "negative_sponsorship_matches": "",
            "sponsorship_evidence_snippet": "",
            "positive_sponsorship_evidence_snippet": "",
            "clearance_matches": "",
            "clearance_evidence_snippet": "",
            "jd_quality_status": "bad",
            "jd_quality_reasons": "extraction_error",
            "jd_text_length": 0,
            "JD_Text": "",
            "extraction_method": extraction_method,
            "retry_attempted": retry_attempted,
            "error": str(e),
        }


class ImmediateJDWriter:
    def __init__(self, date_suffix: str):
        self.date_suffix = date_suffix
        self.enriched_csv = os.path.join(CSV_DIR, f"job_details_enriched_{date_suffix}.csv")
        self.rejected_csv = os.path.join(CSV_DIR, f"job_details_rejected_{date_suffix}.csv")
        self.needs_review_csv = os.path.join(CSV_DIR, f"job_details_needs_review_{date_suffix}.csv")

        self.lock = threading.Lock()
        self.seen_urls = set()
        self.seen_application_keys = set()

        for path in [self.enriched_csv, self.rejected_csv, self.needs_review_csv]:
            self.seen_urls.update(get_existing_urls_from_csv(path))
            self.seen_application_keys.update(get_existing_application_keys_from_csv(path))
            self.ensure_file(path)

    def ensure_file(self, path: str):
        if not os.path.exists(path) or os.path.getsize(path) == 0:
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=ENRICHED_FIELDNAMES, extrasaction="ignore")
                writer.writeheader()

    def write_row(self, row: dict) -> bool:
        url = canonicalize_ats_job_url(row.get("url", ""))
        if not url:
            return False

        application_key = row.get("application_dedupe_key", "").strip()

        with self.lock:
            if url in self.seen_urls:
                return False

            if application_key and application_key in self.seen_application_keys:
                RUN_SUMMARY.increment("application_duplicates_skipped")
                print(f" -> Skipping duplicate application: {application_key}")
                return False

            self.seen_urls.add(url)

            if application_key:
                self.seen_application_keys.add(application_key)

            row["url"] = url
            row = {key: row.get(key, "") for key in ENRICHED_FIELDNAMES}

            decision = row.get("decision", "")

            if decision == "accepted":
                path = self.enriched_csv
                RUN_SUMMARY.increment("jd_accepted")
            elif decision == "rejected":
                path = self.rejected_csv
                RUN_SUMMARY.increment("jd_rejected")
            else:
                path = self.needs_review_csv
                RUN_SUMMARY.increment("jd_needs_review")

            with open(path, "a", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=ENRICHED_FIELDNAMES, extrasaction="ignore")
                writer.writerow(row)
                f.flush()

            return True


def load_jobs_from_input_csv(input_csv: str) -> list[dict]:
    if not os.path.exists(input_csv):
        raise FileNotFoundError(f"Input CSV not found: {input_csv}")

    rows = []
    seen_urls = set()

    with open(input_csv, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for raw_row in reader:
            url = get_url_from_row(raw_row)
            if not url:
                continue

            normalized_url = canonicalize_ats_job_url(url)

            if normalized_url in seen_urls:
                continue

            seen_urls.add(normalized_url)

            host = normalize_domain(normalized_url)
            company, job_id, company_job_key = extract_company_job_key(normalized_url)

            row = {
                "ats_group": raw_row.get("ats_group", ""),
                "location_group": raw_row.get("location_group", ""),
                "search_bucket": raw_row.get("search_bucket", ""),
                "title": raw_row.get("title", raw_row.get("Title", "")),
                "title_match_status": raw_row.get("title_match_status", ""),
                "title_reject_reason": raw_row.get("title_reject_reason", ""),
                "url": normalized_url,
                "display_domain": raw_row.get("display_domain", host),
                "company_guess": raw_row.get("company_guess", company),
                "job_id_guess": raw_row.get("job_id_guess", job_id),
                "canonical_company_job_key": raw_row.get("canonical_company_job_key", company_job_key),
                "application_url": raw_row.get("application_url", ""),
                "application_dedupe_key": raw_row.get("application_dedupe_key", ""),
                "page_number": raw_row.get("page_number", ""),
            }

            rows.append(row)

    print(f"\nLoaded rows from input CSV: {input_csv}")
    print(f"Unique valid links found: {len(rows)}")

    return rows


def safe_load_jobs_from_input_csv(input_csv: str) -> list[dict]:
    if not os.path.exists(input_csv):
        print(f"\nNo accepted CSV found yet: {input_csv}")
        print("Skipping JD extraction because there are no collected links.")
        return []

    return load_jobs_from_input_csv(input_csv)


def chunk_rows(rows: list[dict], num_chunks: int) -> list[list[dict]]:
    chunks = [[] for _ in range(num_chunks)]

    for index, row in enumerate(rows):
        chunks[index % num_chunks].append(row)

    return [chunk for chunk in chunks if chunk]


def build_driver_startup_error_row(row: dict, error: Exception) -> dict:
    url = canonicalize_ats_job_url(row.get("url", ""))
    application_dedupe_key = get_application_dedupe_key(
        application_url=row.get("application_url", ""),
        fallback_url=url,
        company_job_key=row.get("canonical_company_job_key", ""),
    )

    return {
        **row,
        "url": url,
        "application_url": row.get("application_url", ""),
        "application_dedupe_key": application_dedupe_key,
        "decision": "needs_review",
        "rejection_reasons": "chrome_driver_startup_error",
        "posted_status": "error_no_date_found",
        "posted_value": "",
        "posted_source": "",
        "posted_age_days": "",
        "location_status": "unknown",
        "location_evidence": "",
        "sponsorship_status": "yellow_no_info",
        "positive_sponsorship_matches": "",
        "negative_sponsorship_matches": "",
        "sponsorship_evidence_snippet": "",
        "positive_sponsorship_evidence_snippet": "",
        "clearance_matches": "",
        "clearance_evidence_snippet": "",
        "jd_quality_status": "bad",
        "jd_quality_reasons": "chrome_driver_startup_error",
        "jd_text_length": 0,
        "JD_Text": "",
        "extraction_method": "chrome_driver_startup_failed",
        "retry_attempted": "false",
        "error": str(error),
    }


def enrich_job_chunk(worker_id: int, rows: list[dict], writer: ImmediateJDWriter) -> int:
    driver = None
    written_count = 0

    try:
        driver = create_driver(headless=HEADLESS_JD_EXTRACTION)

    except Exception as e:
        RUN_SUMMARY.increment("jd_errors", len(rows))
        print(f"[Worker {worker_id}] Could not launch Chrome driver: {e}")
        print(f"[Worker {worker_id}] Writing all assigned rows to needs_review.")

        for row in rows:
            needs_review_row = build_driver_startup_error_row(row, e)
            if writer.write_row(needs_review_row):
                written_count += 1

        return written_count

    try:
        for index, row in enumerate(rows, start=1):
            print(f"[Worker {worker_id}] [{index}/{len(rows)}] Opening: {row.get('title', '')[:80]}")

            enriched_row = enrich_one_job_with_driver(driver, row)
            was_written = writer.write_row(enriched_row)

            if was_written:
                written_count += 1

            print(
                f"[Worker {worker_id}] "
                f"{enriched_row.get('decision', '')} | "
                f"{enriched_row.get('jd_quality_status', '')} | "
                f"{enriched_row.get('sponsorship_status', '')} | "
                f"{enriched_row.get('extraction_method', '')} | "
                f"{enriched_row.get('title', '')[:80]}"
            )

            time.sleep(random.uniform(1, 3))

    finally:
        safe_quit_driver(driver)

    return written_count


def enrich_jobs_parallel(rows: list[dict], date_suffix: str):
    if not rows:
        print("\nNo rows available for JD extraction.")
        return

    RUN_SUMMARY.increment("jd_total_input_rows", len(rows))

    print(f"\nStarting JD extraction for {len(rows)} unique links.")
    print(f"Persistent browser workers: {PARALLEL_JD_WORKERS}")

    writer = ImmediateJDWriter(date_suffix=date_suffix)
    chunks = chunk_rows(rows, PARALLEL_JD_WORKERS)

    with ThreadPoolExecutor(max_workers=len(chunks)) as executor:
        futures = [
            executor.submit(enrich_job_chunk, worker_id + 1, chunk, writer)
            for worker_id, chunk in enumerate(chunks)
        ]

        total_written = 0

        for future in as_completed(futures):
            try:
                total_written += future.result()
            except Exception as e:
                RUN_SUMMARY.increment("jd_errors")
                print(f"\nA JD worker failed unexpectedly: {e}")
                print("Continuing with remaining workers.")

    print(f"\nJD extraction finished. New rows written: {total_written}")
    print(f"Accepted enriched CSV: {writer.enriched_csv}")
    print(f"Rejected enriched CSV: {writer.rejected_csv}")
    print(f"Needs-review CSV: {writer.needs_review_csv}")
    print(f"Company sponsorship memory: {COMPANY_SPONSORSHIP_MEMORY_FILE}")


def main():
    global COMPANY_MEMORY
    print(datetime.now().strftime("%d/%m/%Y %H:%M:%S"))
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input-csv",
        type=str,
        default="",
        help="Optional CSV file with job links. If provided, skips Google search and extracts JDs from this CSV.",
    )
    parser.add_argument(
        "--fresh-start",
        action="store_true",
        help="Delete today’s checkpoint and start Google search from the beginning.",
    )
    args = parser.parse_args()

    start_time = time.perf_counter()
    date_suffix = now_chicago_suffix()

    # date_suffix = "15082026"

    if args.fresh_start:
        clear_checkpoint(date_suffix)

    ensure_output_dirs()
    COMPANY_MEMORY = CompanySponsorshipMemory(COMPANY_SPONSORSHIP_MEMORY_FILE)

    try:
        if args.input_csv:
            RUN_SUMMARY.set_value("mode", "input_csv_enrich_only")

            input_rows = safe_load_jobs_from_input_csv(args.input_csv)
            enrich_jobs_parallel(input_rows, date_suffix)

            end_time = time.perf_counter()
            RUN_SUMMARY.set_value("total_seconds", round(end_time - start_time, 2))
            RUN_SUMMARY.save(date_suffix)

            print("\nJD extraction from input CSV finished.")
            print(f"Took {end_time - start_time:.2f} seconds")
            return

        RUN_SUMMARY.set_value("mode", "google_search_plus_enrich")

        yesterday_links = load_yesterday_links()

        try:
            all_found_today_links = collect_google_links(
                start_time=start_time,
                yesterday_links=yesterday_links,
                date_suffix=date_suffix,
            )
            # all_found_today_links = set()

        except GoogleSearchStoppedError as e:
            print(f"\nGoogle search stopped early: {e}")
            print("Moving to JD extraction using whatever accepted CSV data is available.")
            all_found_today_links = set()

        except SystemExit:
            print("\nSystemExit received from runtime control flag.")
            print("Moving to JD extraction using whatever accepted CSV data is available.")
            all_found_today_links = set()

        today_link_history_file = get_link_history_file(date_suffix)
        save_links_to_file(all_found_today_links, today_link_history_file)
        print(f"\nToday link history saved to: {today_link_history_file}")

        accepted_csv = os.path.join(CSV_DIR, f"google_jobs_paginated_new_{date_suffix}.csv")
        accepted_rows = safe_load_jobs_from_input_csv(accepted_csv)

        enrich_jobs_parallel(accepted_rows, date_suffix)
        clear_checkpoint(date_suffix)

    except Exception as e:
        print(e)
    finally:
        end_time = time.perf_counter()
        RUN_SUMMARY.set_value("total_seconds", round(end_time - start_time, 2))
        RUN_SUMMARY.save(date_suffix)

    print("\nFull pipeline finished.")
    print(f"Took {end_time - start_time:.2f} seconds")


if __name__ == "__main__":
    a = datetime.now(pytz.timezone("Asia/Kolkata"))
    main()
    print(a.strftime("%d/%m/%Y %H:%M:%S"))
    print(datetime.now(pytz.timezone("Asia/Kolkata")).strftime("%d/%m/%Y %H:%M:%S"))
    """
    Runtime controls:

    touch CSV/control/skip_current_query.flag
    touch CSV/control/stop_full_run.flag
    """
