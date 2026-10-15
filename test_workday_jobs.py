"""Offline tests for workday_jobs.py (no network): python3 -m unittest test_workday_jobs.py"""
import unittest
import workday_jobs as wj


def fake_site(n_by_family):
    """A fake Workday /jobs endpoint: per-family job lists, a 2,000 cap and `total` only on page 1."""
    jobs = {fam: [{'title': f'{fam} job {i}', 'externalPath': f'/job/X/{fam}_{i}', 'locationsText': 'US, CA, Santa Clara',
                   'postedOn': 'Posted Today', 'bulletFields': [f'JR{fam}{i}']} for i in range(n)]
            for fam, n in n_by_family.items()}
    everything = [j for js in jobs.values() for j in js]
    calls = []

    def call(url, body=None):
        calls.append(body)
        if body is None:
            return {'jobPostingInfo': {'location': 'US, CA, Santa Clara', 'additionalLocations': ['US, NC, Durham'],
                                       'country': {'descriptor': 'United States of America'},
                                       'startDate': '2026-10-15', 'timeType': 'Full time'}}
        fam = (body['appliedFacets'].get('jobFamilyGroup') or [None])[0]
        pool = jobs[fam] if fam else everything
        page = pool[body['offset']:body['offset'] + body['limit']] if body['offset'] < wj.CAP else []
        total = min(len(pool), wj.CAP) if body['offset'] == 0 else 0
        facets = [{'facetParameter': 'jobFamilyGroup',
                   'values': [{'id': f, 'descriptor': f, 'count': len(js)} for f, js in jobs.items()]},
                  {'facetParameter': 'timeType', 'values': [{'id': 'ft', 'descriptor': 'Full time', 'count': 5}]}]
        return {'total': total, 'jobPostings': page, 'facets': facets if body['offset'] == 0 else []}
    return call, calls


class T(unittest.TestCase):
    def setUp(self):
        self.real = wj.call

    def tearDown(self):
        wj.call = self.real

    def test_small_site_reads_every_page_despite_total_zero_after_page_1(self):
        wj.call, calls = fake_site({'Eng': 45})
        jobs = wj.list_jobs('api', pause=0)
        self.assertEqual(len(jobs), 45)
        self.assertEqual(len({j['externalPath'] for j in jobs}), 45)

    def test_site_past_the_cap_is_split_by_its_biggest_filter(self):
        wj.call, calls = fake_site({'Eng': 1740, 'Sales': 332, 'Ops': 646})   # 2,718 jobs, like NVIDIA on 10-16
        jobs = wj.list_jobs('api', pause=0)
        self.assertEqual(len(jobs), 2718)
        self.assertTrue(any(c and c['appliedFacets'].get('jobFamilyGroup') for c in calls))

    def test_max_stops_early(self):
        wj.call, calls = fake_site({'Eng': 1740, 'Sales': 332, 'Ops': 646})
        jobs = wj.list_jobs('api', limit=30, pause=0)
        self.assertEqual(len(jobs), 30)
        self.assertLess(len(calls), 5)

    def test_details_fill_every_location_and_the_date(self):
        wj.call, _ = fake_site({'Eng': 1})
        p = wj.list_jobs('api', pause=0)[0]
        row = wj.row_for('https://x.wd5.myworkdayjobs.com', 'x', 'Site', p, wj.call('detail')['jobPostingInfo'])
        self.assertEqual(row['locations'], 'US, CA, Santa Clara; US, NC, Durham')
        self.assertEqual(row['posted'], '2026-10-15')
        self.assertEqual(row['country'], 'United States of America')
        self.assertEqual(row['url'], 'https://x.wd5.myworkdayjobs.com/en-US/Site/job/X/Eng_0')
        row = wj.row_for('https://wd1.myworkdaysite.com', 'fmr', 'FidelityCareers', p)
        self.assertEqual(row['url'], 'https://wd1.myworkdaysite.com/en-US/recruiting/fmr/FidelityCareers/job/X/Eng_0')

    def test_url_forms(self):
        for u, want in [('https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite',
                         ('https://nvidia.wd5.myworkdayjobs.com', 'nvidia', 'NVIDIAExternalCareerSite')),
                        ('https://nvidia.wd5.myworkdayjobs.com/en-US/NVIDIAExternalCareerSite/details/x',
                         ('https://nvidia.wd5.myworkdayjobs.com', 'nvidia', 'NVIDIAExternalCareerSite')),
                        ('https://wd1.myworkdaysite.com/en-US/recruiting/fmr/FidelityCareers',
                         ('https://wd1.myworkdaysite.com', 'fmr', 'FidelityCareers')),
                        ('https://boards.greenhouse.io/stripe', None)]:
            self.assertEqual(wj.parse_url(u), want)


if __name__ == '__main__':
    unittest.main()
