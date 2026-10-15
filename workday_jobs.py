#!/usr/bin/env python3
"""Every open job on one Workday careers site (myworkdayjobs.com / myworkdaysite.com), as CSV.

Python 3.9+, standard library only. It handles the three things that trip up a simple paging loop:
  1. `total` is only sent on the first page; later pages say `"total": 0`.
  2. One search returns at most 2,000 jobs, so a bigger site is split by one of the site's own filters
     (the facet whose counts add up to the most jobs, e.g. job family) and the parts are merged.
  3. The list shows "2 Locations" and "Posted 30+ Days Ago". With --details the script reads each job's
     own record for every location, the country and the start date (one extra request per job).

usage:
  python3 workday_jobs.py https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite
  python3 workday_jobs.py <careers URL> --details --max 50 -o jobs.csv
"""
import argparse, csv, json, re, sys, time, urllib.request

PAGE, CAP = 20, 2000
# tenant.wdN.myworkdayjobs.com/[en-US/]<site>   and   wdN.myworkdaysite.com/[en-US/]recruiting/<tenant>/<site>
URL_JOBS = re.compile(r'https?://([a-z0-9-]+)\.(wd\d+)\.myworkdayjobs\.com/(?:[a-z]{2}-[A-Za-z]{2}/)?([A-Za-z0-9_-]+)', re.I)
URL_SITE = re.compile(r'https?://(wd\d+)\.myworkdaysite\.com/(?:[a-z]{2}-[A-Za-z]{2}/)?recruiting/([a-z0-9-]+)/([A-Za-z0-9_-]+)', re.I)


def parse_url(u):
    """Careers URL -> (host base, tenant, site), or None."""
    m = URL_JOBS.match(u)
    if m:
        tenant, wd, site = m.groups()
        return f'https://{tenant}.{wd}.myworkdayjobs.com', tenant, site
    m = URL_SITE.match(u)
    if m:
        wd, tenant, site = m.groups()
        return f'https://{wd}.myworkdaysite.com', tenant, site
    return None


def call(url, body=None):
    """GET (body None) or POST JSON; retries 429/5xx/timeouts with backoff."""
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers={
        'Content-Type': 'application/json', 'Accept': 'application/json', 'User-Agent': 'workday-jobs-example/1.0'})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except Exception:
            if attempt == 3:
                raise
            time.sleep(2 ** attempt)


def search(api, facets, seen, out, limit=0, pause=0.2):
    """Page through one search, appending new jobs to `out`. Returns the total page 1 reported."""
    offset, total = 0, None
    while True:
        d = call(api + '/jobs', {'limit': PAGE, 'offset': offset, 'appliedFacets': facets, 'searchText': ''}) or {}
        if total is None:                      # only page 1 carries the real total
            total = d.get('total') or 0
        posts = d.get('jobPostings') or []
        for p in posts:
            path = p.get('externalPath')
            if path and path not in seen:      # split searches overlap; keep each job once
                seen.add(path)
                out.append(p)
        offset += PAGE
        if not posts or offset >= min(total, CAP) or (limit and len(out) >= limit):
            return total
        time.sleep(pause)


def split_facet(first):
    """(parameter, values, jobs) of the site's filter whose counts add up to the most jobs."""
    best = None
    for f in first.get('facets') or []:
        vals = [v for v in f.get('values') or [] if v.get('id') and v.get('count')]
        n = sum(v['count'] for v in vals)
        if vals and (best is None or n > best[2]):
            best = (f.get('facetParameter'), vals, n)
    return best


def list_jobs(api, limit=0, pause=0.2, log=lambda *a: None):
    first = call(api + '/jobs', {'limit': PAGE, 'offset': 0, 'appliedFacets': {}, 'searchText': ''}) or {}
    jobs, seen = [], set()
    split = split_facet(first)
    if (first.get('total') or 0) >= CAP and split and not (limit and limit < CAP):
        name, vals, n = split
        log(f'{first.get("total")} reported (the cap); splitting by {name}: {len(vals)} values, {n} jobs')
        for v in vals:
            got = search(api, {name: [v['id']]}, seen, jobs, limit, pause)
            if got >= CAP:
                log(f'  {v.get("descriptor")}: {got} jobs, still at the cap; split it by a second filter')
            if limit and len(jobs) >= limit:
                break
    else:
        search(api, {}, seen, jobs, limit, pause)
    return jobs[:limit] if limit else jobs


def row_for(base, tenant, site, p, info=None):
    page = f'{base}/en-US/recruiting/{tenant}/{site}' if 'myworkdaysite' in base else f'{base}/en-US/{site}'
    row = {'title': p.get('title'), 'locations': p.get('locationsText'), 'posted': p.get('postedOn'),
           'id': (p.get('bulletFields') or [None])[0], 'url': page + p['externalPath']}
    if info is not None:
        locs = [info.get('location')] + list(info.get('additionalLocations') or [])
        row['locations'] = '; '.join(x for x in locs if x) or row['locations']
        row['posted'] = info.get('startDate') or row['posted']
        row['country'] = (info.get('country') or {}).get('descriptor')
        row['time_type'] = info.get('timeType')
    return row


def main():
    ap = argparse.ArgumentParser(description='Every open job on one Workday careers site, as CSV.')
    ap.add_argument('url', help='careers site URL, e.g. https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite')
    ap.add_argument('--details', action='store_true', help="read each job's record: all locations, country, start date")
    ap.add_argument('--max', type=int, default=0, help='stop after N jobs (0 = all)')
    ap.add_argument('-o', '--out', default='workday_jobs.csv')
    a = ap.parse_args()
    parsed = parse_url(a.url)
    if not parsed:
        sys.exit('not a Workday careers URL: ' + a.url)
    base, tenant, site = parsed
    api = f'{base}/wday/cxs/{tenant}/{site}'
    log = lambda s: print(s, file=sys.stderr)

    jobs = list_jobs(api, a.max, log=log)
    rows = []
    for i, p in enumerate(jobs, 1):
        info = None
        if a.details:
            info = (call(api + p['externalPath']) or {}).get('jobPostingInfo') or {}
            time.sleep(0.2)
            if i % 100 == 0:
                log(f'  details {i}/{len(jobs)}')
        rows.append(row_for(base, tenant, site, p, info))

    cols = ['title', 'locations', 'country', 'posted', 'time_type', 'id', 'url'] if a.details else \
           ['title', 'locations', 'posted', 'id', 'url']
    with open(a.out, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction='ignore')
        w.writeheader()
        w.writerows(rows)
    log(f'{len(rows)} jobs -> {a.out}')


if __name__ == '__main__':
    main()
