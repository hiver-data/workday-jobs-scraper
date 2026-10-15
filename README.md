# Workday jobs scraper: every open job on a Workday careers site, as CSV (Python)

A free, standard-library Python script that reads every open job from one company's Workday careers site (`*.myworkdayjobs.com` or `*.myworkdaysite.com`) through the same JSON endpoint the careers page itself uses, and writes a CSV. No login, no API key, no browser, no dependencies.

```bash
python3 workday_jobs.py https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite
# 2000 reported (the cap); splitting by jobFamilyGroup: 15 values, 2718 jobs
# 2715 jobs -> workday_jobs.csv
```

```
title,locations,posted,id,url
ASIC Verification Engineer - GPU,2 Locations,Posted Today,JR2027466,https://nvidia.wd5.myworkdayjobs.com/en-US/NVIDIAExternalCareerSite/job/US-CA-Santa-Clara/ASIC-Verification-Engineer---GPU_JR2027466
Senior AI Application Developer - GPU and SOC Architecture Modeling,"US, CA, Santa Clara",Posted Today,JR2019994,https://nvidia.wd5.myworkdayjobs.com/en-US/NVIDIAExternalCareerSite/job/US-CA-Santa-Clara/Senior-AI-Application-Developer---GPU-and-SOC-Architecture-Modeling_JR2019994
```

Add `--details` to read each job's own record for every location, the country, the start date and full or part time (one extra request per job):

```
title,locations,country,posted,time_type,id,url
ASIC Verification Engineer - GPU,"US, CA, Santa Clara; US, NC, Durham",United States of America,2026-10-15,Full time,JR2027466,https://nvidia.wd5.myworkdayjobs.com/en-US/NVIDIAExternalCareerSite/job/US-CA-Santa-Clara/ASIC-Verification-Engineer---GPU_JR2027466
"Software Engineer, DGX Cloud AI Infrastructure","US, CA, Santa Clara; US, TX, Austin; US, OR, Remote; US, WA, Remote; US, WA, Redmond",United States of America,2026-10-15,Full time,JR2019248,https://nvidia.wd5.myworkdayjobs.com/en-US/NVIDIAExternalCareerSite/job/US-CA-Santa-Clara/Software-Engineer--DGX-Cloud-AI-Infrastructure_JR2019248
```

(Real rows from runs on 2026-10-16.)

## Usage

```bash
python3 workday_jobs.py <careers URL> [--details] [--max N] [-o jobs.csv]

python3 workday_jobs.py https://workday.wd5.myworkdayjobs.com/Workday
python3 workday_jobs.py https://wd1.myworkdaysite.com/en-US/recruiting/fmr/FidelityCareers --details --max 50
```

Python 3.9 or newer. Copy the career site's URL from your browser: the `tenant.wdN.myworkdayjobs.com/<site>` form and the `wdN.myworkdaysite.com/recruiting/<tenant>/<site>` form both work, with or without `/en-US/`.

## Three things that break a simple loop

The endpoint is `POST https://<tenant>.wdN.myworkdayjobs.com/wday/cxs/<tenant>/<site>/jobs` with `{"limit": 20, "offset": 0, "appliedFacets": {}, "searchText": ""}`. Paging through it looks easy. What we saw on NVIDIA's careers site on 2026-10-16:

1. **`total` is only on the first page.** Page 1 said `"total": 2000`; the page at offset 20 said `"total": 0`. Read the total once, from page 1.
2. **One search stops at 2,000 jobs, and past that it starts again.** NVIDIA had about 2,718 open jobs (the sum of its job-family filter counts), but page 1 reported 2,000. At offset 2,000 the endpoint returned page 1 again, with `"total": 2000`, so a loop that pages until it gets an empty page never ends. The script stops at 2,000, splits a capped site by the site's own filter whose counts add up to the most jobs (for NVIDIA: 15 job families), and merges the parts by job path. Result: 2,715 distinct jobs in about 4.5 minutes from our server, with a 0.2 s pause between requests.
3. **The list is a summary.** 1,028 of NVIDIA's 2,715 jobs (38%) showed only "2 Locations", "3 Locations" and so on, and 1,601 (59%) said "Posted 30+ Days Ago". `--details` fetches each job's record (`GET .../<site>/job/...`) for every location, the country and the start date, so a country filter or a "posted this week" filter works.

If one filter value is still at 2,000 jobs, the script says so; split that value by a second filter (`locationMainGroup`, `timeType`) the same way.

Tests run offline against a fake endpoint that copies these three behaviours: `python3 -m unittest test_workday_jobs.py`.

## Many companies, or companies by name

This script reads one Workday site you already have the URL for. For a list of companies, by name or website, on Workday and 16 other job systems, the [Workday Jobs Scraper & API on Apify](https://apify.com/hiver/all-open-jobs-by-company?utm_source=github&utm_campaign=workday-jobs-scraper) (built by us, hiver) finds each company's career board, does the splitting and the per-job detail reads for you, adds descriptions and salary ranges where the posting has them, and returns one table for all companies. It costs $0.03 per company for up to 1,000 jobs plus $0.01 per further 1,000 on Apify's free plan (NVIDIA's roughly 2,700 jobs: $0.05); companies that are not found cost nothing. Python and Node.js examples: [hiver-data/all-open-jobs-by-company](https://github.com/hiver-data/all-open-jobs-by-company).

## Notes

- Unofficial. Not affiliated with Workday or with any company whose jobs you read. The script reads only the public job listings each company publishes for job seekers on its careers site.
- Be polite: keep the pause between requests, and don't run it in a tight loop. Workday can answer 429 or 5xx; the script retries those with backoff.
- Something broke on a site? Open an issue here with the careers URL.

MIT licensed. Built by [hiver](https://apify.com/hiver?utm_source=github&utm_campaign=workday-jobs-scraper).
