# Employer discovery sources

Research date: 14 October 2026, Pacific/Auckland. These are independent employers, even where a shared ATS hosts public adverts. No paid services, credentials, restricted-board scraping or automatic application submission are used.

| Employer | Automated entry point | Verification and coverage |
| --- | --- | --- |
| Star Group | [Public sitemap](https://careers.stargroup.nz/sitemap.xml) | Existing adapter retained and expanded to recognised hospitality title slugs. Complete employer JobPosting and application action; existing local venue map. |
| Accor | [Public vacancy sitemap](https://careers.accor.com/vacanciessitemap.xml) | Filters Auckland hospitality roles before detail fetch. Reads individual public `/global/en/job/` adverts. Known central hotels and Novotel Ellerslie are mapped explicitly. |
| Hind Management / Sudima | [Public employer Workable feed](https://apply.workable.com/api/v1/widget/accounts/hindmanagement) | Feed contains public vacancy summaries. Auckland target roles require a complete specific JobPosting page and live application action. Sudima Auckland City is mapped; Sudima Airport is beyond the boundary. |
| Atomic Coffee Roasters | [Public employer LiveHire listing](https://www.livehire.com/careers/atomiccoffeeroasters/jobs) | Extracts unique individual advert links from server-rendered cards. Reads complete JobPosting and visible Apply button. Atomic Kingsland is identified from the description; broad city labels alone are insufficient. |

## Access checks

Robots rules are fetched at every fresh discovery invocation and checked for every requested URL and redirect. On the research date these configured paths were accessible to the application. No login, private APIs, screening forms, application POSTs, rate-limit circumvention or anti-bot bypass is used. A changed robots policy or unavailable robots file makes that source fail closed and leaves other employers running. Public availability and robots permission are operational checks, not a legal opinion; if an employer asks that access stop, disable its source entry. Review changed site terms before adding sources.

Accor's general career site advert paths are allowed, while `/heartists-opportunities`, workflows and some search routes are restricted. The application never accesses those restricted paths. Its separate SmartRecruiters API was rejected by robots during research and is not used. The official [public Posting API documentation](https://developers.smartrecruiters.com/docs/posting-api) was investigated, but documentation did not override the observed robots restriction.

## Restricted job boards and unverified leads

Checked 27 October 2026. These boards publish Auckland hospitality vacancies, but their robots.txt restricts what may be retrieved, so each is used only as far as it permits. Nothing here contributes to the verified catalogue; see the [README](../README.md) section on unverified leads.

| Board | robots.txt finding | What this release does |
| --- | --- | --- |
| SEEK NZ (`nz.seek.com`) | `Disallow: */job/` and `Disallow: /api/jobsearch/`; keyword search paths are allowed | Reads permitted Auckland search pages at listing level only. Advert pages are never requested; each lead links to the advert for manual checking. |
| Indeed NZ | `Disallow: /viewjob`, `/job/` and `/jobs/NZ/`, and the search page returns HTTP 403 to a plain client | No adapter is configured. A saved-search link is offered in the digest instead. |
| Trade Me | `Allow: /a/jobs/*/listing` and `Allow: /a/jobs/*/auckland/auckland-city` outrank the shorter `Disallow: /a/*listing/` | Reads Auckland City category pages for leads. Advert pages are permitted but carry no street address or coordinate, so they are deliberately not fetched. |

### Robots wildcard matching

These boards express rules with wildcards (`*/job/`, `*?`). Python's `urllib.robotparser` compares a rule as a plain prefix and ignores `*` and `$` entirely, so it reported every one of these paths as allowed: the previous "honours robots.txt" guarantee was not true in practice, and a SEEK advert page would have been fetched.

`jobs4jsr.robots` implements the matching the directives require: `*` matches any run of characters, a trailing `$` anchors the end, the longest matching pattern wins, `Allow` wins a tie, an empty value is a no-op, and user-agent groups are selected by the most specific matching token.

Matching does not use a regular expression at all. A wildcard rule is scanned with the standard greedy two-pointer algorithm, whose cost is bounded by pattern length × path length, so no rule can backtrack exponentially. Runs of consecutive `*` are still collapsed because they are equivalent to one; Trade Me's robots.txt contains a rule with roughly 180 of them, which hung the earlier version once each `*` became its own `.*`. Patterns are also length- and wildcard-limited, and a rule outside those limits raises rather than being guessed at, so that origin fails closed.

## Lead integrity

Leads are stored once per board and advert ID (the `board_leads` primary key), and a repeated card in one run is stored once. A SEEK card with no advert ID is skipped: it has no stable link and no way to be deduplicated, so storing it would add an unopenable duplicate on every run.

Every sighting updates `last_seen`. A lead is listed in reports and digests only while it has been seen within the retention window (`digest.lead_retention_days`, 21 by default); older rows remain in the database for audit and are no longer presented as current. Leads still never receive a distance, a score, a letter or a catalogue entry.

## Researched but excluded

- [Savor careers](https://savor.co.nz/careers/vacancies): public employer page uses JobAdder widgets. The widget host disallows automated retrieval; no widget request was made after denial and no stale search snippet became a recommendation.
- [Millennium careers](https://millenniumcareers.com/job-opportunities/): same blocked JobAdder widget limitation. The static hospitality department description is not a vacancy.
- [Foley Hospitality](https://www.foleyhospitality.co.nz/careers): employer page has role titles, but full details/application lead to SEEK. These incomplete and apparently old leads are excluded without fetching SEEK.
- [Cordis Auckland](https://cordishotelsauckland.readycareers.io/Job): public site researched; currently surfaced mainly unrelated or supervisory roles. No adapter is claimed in this release.
- [Cook Brothers Hospitality](https://www.cookbrothershospitality.co.nz/): public careers context researched; no sufficiently complete structured vacancy integration selected.

## Geographic evidence

The existing reference coordinates (-36.8485, 174.7633) and 10 km Haversine boundary are unchanged. Coordinates are approximate venue estimates, not travel distances. Each configured mapping includes its address evidence URL. Workplaces must match explicit venue tokens; multiple matches are excluded. Both airport and central Auckland hotels can appear in a feed, so an Auckland city name is never enough to assume the CBD.

Address references include [Pullman Auckland](https://www.pullmanauckland.co.nz/), [Mövenpick Auckland](https://all.accor.com/hotel/1721/index.en.shtml), [Novotel Ellerslie](https://all.accor.com/hotel/3060/index.en.shtml), [Sudima Auckland City](https://www.sudimahotels.com/en/our-hotels/auckland-city/), and [Atomic Kingsland](https://atomiccoffee.co.nz/pages/kingsland). Add mappings only after checking venue identity and actual work location. A source can succeed with zero nearby suitable vacancies.

## Manual validation and diagnostics

```powershell
.\.venv\Scripts\python.exe -m jobs4jsr.cli search --run-id employer-check
.\.venv\Scripts\python.exe -m jobs4jsr.cli report --run manual-employer-check
.\.venv\Scripts\python.exe -m jobs4jsr.cli sources
```

Manual IDs are always prefixed `manual-`; they cannot consume Monday/Wednesday/Friday scheduler IDs. Results are matched against all historical jobs and other candidates in the same run. At most three new jobs are selected across all sources, including retries. Existing letters are not regenerated when duplicates are encountered. Source checks are persisted locally and shown in the dated HTML and Markdown reports, including when no qualifying jobs exist. Future scheduled runs use the same adapters through the existing unchanged task and virtual environment.
