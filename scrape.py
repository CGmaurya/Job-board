#!/usr/bin/env python3
"""
Remote design-leadership job scraper for India.

Roles: Principal Designer, Staff Designer, UX Manager, UX Lead, Design Director / Head of Design.
Scope: remote roles located in India, plus worldwide-remote roles open to India.

Usage:
    pip install requests
    python scrape.py                     # open sources -> jobs.json + board.html
    python scrape.py --linkedin          # also try LinkedIn's public guest search (see note)
    python scrape.py --max-age 60        # drop listings older than 60 days

Optional: set SERPAPI_KEY (Google Jobs via SerpApi, free plan 250 searches/month) and edit
companies.txt (Greenhouse/Lever/Ashby boards). Runs daily via .github/workflows/daily.yml.

Run it daily with cron / launchd / GitHub Actions and open board.html.

Note on --linkedin: LinkedIn's terms restrict automated collection and it rate-limits
aggressively. It is off by default and best-effort. Indeed and Naukri block bots outright,
so they are not implemented; open their saved-search alerts by email instead.
"""
import argparse, html, json, re, sys, time
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from xml.etree import ElementTree as ET

import requests

HERE = Path(__file__).parent
UA = {"User-Agent": "Mozilla/5.0 (jobboard-personal-use)"}

QUERIES = ["principal designer", "staff designer", "ux manager", "ux lead",
           "design manager", "lead product designer", "principal product designer",
           "staff product designer", "head of design", "design director",
           "director of design", "vp design", "head of ux", "director of ux",
           "head of product design"]

# Title must look like a design role AND one of the target seniorities.
DESIGN = re.compile(r"\b(design(er)?|ux|ui|uxd|product design|experience)\b", re.I)
LEVEL = re.compile(r"\b(principal|staff|lead|manager|head of|head|director|vp|vice president|group)\b", re.I)
NOISE = re.compile(r"\b(engineer|developer|consultant(?!.*ux)|architect|analyst|"
                   r"game designer|combat|economy|level designer|bim|character|"
                   r"civil|structural|electrical|mechanical|learning experience|"
                   r"customer experience|patient experience)\b", re.I)

KEEP_DAYS = 14
INDIA = re.compile(r"\b(india|apac|asia|worldwide|anywhere|global|remote)\b", re.I)


def wanted(title: str) -> bool:
    if not (DESIGN.search(title) and LEVEL.search(title)):
        return False
    # keep "Principal Consultant, UXD" style titles but drop engineering/etc.
    return not NOISE.search(title) or re.search(r"\b(ux|uxd|product design)", title, re.I) is not None


def scope_of(location: str):
    """Return 'india', 'worldwide' or None (not open to India)."""
    loc = (location or "").strip()
    if re.search(r"india", loc, re.I):
        return "india"
    if not loc or re.search(r"worldwide|anywhere|global|apac|asia|remote$|^remote$", loc, re.I):
        return "worldwide"
    return None


def job(title, company, location, url, posted, source, scope=None):
    return {"title": html.unescape(title).strip(), "company": html.unescape(company).strip(),
            "location": location or "Worldwide", "scope": scope or scope_of(location),
            "url": url, "posted": int(posted) if posted else None, "source": source}


def get(url, **kw):
    r = requests.get(url, headers=UA, timeout=25, **kw)
    r.raise_for_status()
    return r


def himalayas():
    out = []
    for q in QUERIES:
        for country in ("IN", None):
            params = {"q": q, "sort": "recent"}
            if country:
                params["country"] = country
            try:
                data = get("https://himalayas.app/jobs/api/search", params=params).json()
            except Exception as e:
                print(f"  himalayas {q!r}: {e}", file=sys.stderr); continue
            for j in data.get("jobs", []):
                loc = ", ".join(j.get("locationRestrictions") or [])
                out.append(job(j["title"], j.get("companyName", ""), loc,
                               j.get("applicationLink") or j.get("guid"),
                               j.get("pubDate"), "Himalayas"))
            time.sleep(0.5)
    return out


def remotive():
    out = []
    for cat in ("design",):
        try:
            data = get("https://remotive.com/api/remote-jobs", params={"category": cat}).json()
        except Exception as e:
            print(f"  remotive: {e}", file=sys.stderr); continue
        for j in data.get("jobs", []):
            ts = datetime.fromisoformat(j["publication_date"]).replace(tzinfo=timezone.utc).timestamp()
            out.append(job(j["title"], j["company_name"], j.get("candidate_required_location"),
                           j["url"], ts, "Remotive"))
    return out


def remoteok():
    out = []
    try:
        data = get("https://remoteok.com/api").json()
    except Exception as e:
        print(f"  remoteok: {e}", file=sys.stderr); return out
    for j in data[1:]:
        out.append(job(j.get("position", ""), j.get("company", ""), j.get("location"),
                       j.get("url"), j.get("epoch"), "RemoteOK"))
    return out


def jobicy():
    out = []
    try:
        data = get("https://jobicy.com/api/v2/remote-jobs",
                   params={"count": 100, "industry": "design-multimedia"}).json()
    except Exception as e:
        print(f"  jobicy: {e}", file=sys.stderr); return out
    for j in data.get("jobs", []):
        geo = j.get("jobGeo")
        geo = ", ".join(geo) if isinstance(geo, list) else geo
        ts = datetime.fromisoformat(j["pubDate"]).replace(tzinfo=timezone.utc).timestamp()
        out.append(job(j["jobTitle"], j["companyName"], geo, j["url"], ts, "Jobicy"))
    return out


def weworkremotely():
    out = []
    try:
        root = ET.fromstring(get("https://weworkremotely.com/categories/remote-design-jobs.rss").content)
    except Exception as e:
        print(f"  weworkremotely: {e}", file=sys.stderr); return out
    for it in root.iter("item"):
        raw = it.findtext("title", "")
        company, _, title = raw.partition(": ")
        region = it.findtext("region", "") or "Anywhere in the World"
        ts = parsedate_to_datetime(it.findtext("pubDate")).timestamp()
        out.append(job(title or raw, company, region, it.findtext("link"), ts, "We Work Remotely"))
    return out


def linkedin():
    """Best effort against the public guest endpoint. f_WT=2 is 'Remote'."""
    out = []
    card = re.compile(r'<a class="base-card__full-link[^"]*" href="([^"?]+)[^"]*".*?'
                      r'base-search-card__title">\s*(.*?)\s*</h3>.*?'
                      r'base-search-card__subtitle">.*?>\s*(.*?)\s*</a>.*?'
                      r'job-search-card__location">\s*(.*?)\s*</span>.*?'
                      r'datetime="([\d-]+)"', re.S)
    for q in QUERIES[:4]:
        try:
            page = get("https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search",
                       params={"keywords": q, "location": "India", "f_WT": 2, "start": 0}).text
        except Exception as e:
            print(f"  linkedin {q!r}: {e}", file=sys.stderr); continue
        for url, title, company, loc, day in card.findall(page):
            ts = datetime.fromisoformat(day).replace(tzinfo=timezone.utc).timestamp()
            out.append(job(title, company, loc or "India", url, ts, "LinkedIn", scope="india"))
        time.sleep(2)
    return out


REMOTE = re.compile(r"remote|work from home|anywhere|distributed", re.I)


def remote_scope(loc, is_remote=None):
    """Scope for ATS boards, where location strings look like 'Remote - India'."""
    loc = loc or ""
    if re.search(r"india", loc, re.I) and (is_remote or REMOTE.search(loc)):
        return "india"
    if re.fullmatch(r"\s*(remote|anywhere|worldwide|global|remote\s*[-,(]\s*(global|worldwide|apac|asia))\s*\)?\s*", loc, re.I) \
            or re.search(r"worldwide|anywhere|apac|asia", loc, re.I) and REMOTE.search(loc):
        return "worldwide"
    return None


def load_companies():
    f = HERE / "companies.txt"
    if not f.exists():
        return []
    out = []
    for line in f.read_text().splitlines():
        line = line.split("#")[0].strip()
        if ":" in line:
            ats, token = line.split(":", 1)
            out.append((ats.strip().lower(), token.strip()))
    return out


def ats_boards():
    """Greenhouse, Lever and Ashby public job-board APIs for companies in companies.txt."""
    out, dead = [], []
    for ats, token in load_companies():
        name = token.replace("-", " ").title()
        try:
            if ats == "greenhouse":
                data = get(f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs").json()
                for j in data.get("jobs", []):
                    loc = (j.get("location") or {}).get("name", "")
                    ts = datetime.fromisoformat(j["updated_at"].replace("Z", "+00:00")).timestamp()
                    out.append(job(j["title"], j.get("company_name") or name, loc,
                                   j["absolute_url"], ts, "Greenhouse", remote_scope(loc)))
            elif ats == "lever":
                data = get(f"https://api.lever.co/v0/postings/{token}", params={"mode": "json"}).json()
                for j in data:
                    cat = j.get("categories") or {}
                    loc = cat.get("location") or ""
                    remote = j.get("workplaceType") == "remote"
                    out.append(job(j["text"], name, loc, j["hostedUrl"], (j.get("createdAt") or 0) / 1000,
                                   "Lever", remote_scope(loc, remote)))
            elif ats == "ashby":
                data = get(f"https://api.ashbyhq.com/posting-api/job-board/{token}").json()
                for j in data.get("jobs", []):
                    loc = j.get("location") or ""
                    ts = datetime.fromisoformat(j["publishedAt"].replace("Z", "+00:00")).timestamp() \
                        if j.get("publishedAt") else None
                    out.append(job(j["title"], name, loc, j["jobUrl"], ts, "Ashby",
                                   remote_scope(loc, j.get("isRemote"))))
        except Exception as e:
            dead.append(f"{ats}:{token}")
        time.sleep(0.2)
    if dead:
        print(f"  {len(dead)} boards failed (wrong token or no public board): {', '.join(dead)}", file=sys.stderr)
    return out


# Highest-yield queries first. The free SerpApi plan is 250 searches/month, so the daily
# run is capped by SERPAPI_MAX (default 8, about 240/month).
SERP_QUERIES = ["principal designer", "staff designer", "design director", "head of design",
                "ux manager", "ux lead", "principal product designer", "design manager"]


def relative_to_ts(text):
    m = re.match(r"(\d+)\s*(hour|day|week|month)", text or "")
    if not m:
        return None
    n, unit = int(m.group(1)), m.group(2)
    return time.time() - n * {"hour": 3600, "day": 86400, "week": 7 * 86400, "month": 30 * 86400}[unit]


def serpapi():
    """Google Jobs via SerpApi (covers LinkedIn, Indeed, Naukri, Foundit and more)."""
    import os
    key = os.environ.get("SERPAPI_KEY")
    if not key:
        print("  SERPAPI_KEY not set, skipping", file=sys.stderr)
        return []
    limit = int(os.environ.get("SERPAPI_MAX", "8"))
    out = []
    for q in SERP_QUERIES[:limit]:
        try:
            data = get("https://serpapi.com/search.json",
                       params={"engine": "google_jobs", "q": q, "location": "India",
                               "hl": "en", "gl": "in", "ltype": 1, "api_key": key}).json()
        except Exception as e:
            print(f"  serpapi {q!r}: {e}", file=sys.stderr); continue
        for j in data.get("jobs_results", []):
            ext = j.get("detected_extensions") or {}
            link = (j.get("apply_options") or [{}])[0].get("link") or j.get("share_link")
            loc = j.get("location", "")
            via = (j.get("via") or "").replace("via ", "") or "Google Jobs"
            out.append(job(j["title"], j.get("company_name", ""), loc, link,
                           relative_to_ts(ext.get("posted_at")), via, scope="india"))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--linkedin", action="store_true")
    ap.add_argument("--max-age", type=int, default=90, help="days")
    args = ap.parse_args()

    sources = [himalayas, remotive, remoteok, jobicy, weworkremotely, ats_boards, serpapi]
    if args.linkedin:
        sources.append(linkedin)

    raw = []
    for fn in sources:
        print(f"Scraping {fn.__name__} ...")
        got = fn()
        print(f"  {len(got)} raw")
        raw += got

    cutoff = time.time() - args.max_age * 86400
    seen, keep = set(), []
    for j in raw:
        if not j["url"] or not j["scope"] or not wanted(j["title"]):
            continue
        if j["posted"] and j["posted"] < cutoff:
            continue
        key = (j["title"].lower(), j["company"].lower())
        if key in seen:
            continue
        seen.add(key)
        keep.append(j)
    # carry over listings from previous runs for KEEP_DAYS after they were last seen
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    for j in keep:
        j["last_seen"] = today
    prev_file = HERE / "jobs.json"
    if prev_file.exists():
        try:
            prev = json.loads(prev_file.read_text()).get("jobs", [])
        except Exception:
            prev = []
        have = {j["url"] for j in keep}
        limit = (datetime.now(timezone.utc) - timedelta(days=KEEP_DAYS)).strftime("%Y-%m-%d")
        for j in prev:
            if j["url"] not in have and j.get("last_seen", "") >= limit:
                key = (j["title"].lower(), j["company"].lower())
                if key not in seen:
                    seen.add(key)
                    keep.append(j)
    keep.sort(key=lambda j: j["posted"] or 0, reverse=True)

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    payload = {"scraped": stamp, "jobs": keep}
    (HERE / "jobs.json").write_text(json.dumps(payload, indent=1))
    tpl = (HERE / "board_template.html").read_text()
    page = "<!doctype html><html lang=en><head><meta charset=utf-8>" \
           "<meta name=viewport content='width=device-width,initial-scale=1'></head><body>" \
           + tpl.replace("__DATA__", json.dumps(payload).replace("</", "<\\/")) + "</body></html>"
    (HERE / "board.html").write_text(page)
    print(f"Kept {len(keep)} jobs -> jobs.json, board.html")


if __name__ == "__main__":
    main()
