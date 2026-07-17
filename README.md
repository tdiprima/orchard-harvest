# ORCID harvester 🍊 

Lists researchers affiliated with an institution (Example University by default) and their publications, using the **ORCID public API**.

Output looks like:

```
Josiah Carberry (0000-0002-1825-0097)
- Toward a Unified Theory of High-Energy Metaphysics
- The Memory Bus Considered Harmful

Sofia Garcia (0000-0001-5109-3700)
- A Longitudinal Study of Example Data
- Bulk Loading of Synthetic Records: Methods and Pitfalls
```

## Do I need to register with ORCID?

**No.** This tool uses the ORCID **Public API** at `https://pub.orcid.org/v3.0`, which serves anonymous read-only requests with no account, no client ID, and no token. Everything in this README works out of the box.

Registration only matters if you hit rate limits or need private data:

| | Anonymous (what this tool does) | Public API + token | Member API |
|---|---|---|---|
| Cost | Free | Free | Paid membership |
| Registration | None | Free ORCID account | Institutional membership |
| Reads public records | Yes | Yes | Yes |
| Reads limited-access / private data | No | No | Yes |
| Writes to records | No | No | Yes |
| Rate limit | Shared IP-based pool | Higher, per-client | Higher, per-client |

ORCID's published public-API ceiling is **24 requests/second, burst 40**. This tool sends roughly 2 requests/second, so anonymous use is well under it. If you get HTTP 429, add a token (below).

### How to find out if you're already registered

1. Go to <https://orcid.org/signin> and try "Forgot your password?" with your `@example.com` address. If ORCID has an account for it, you'll get a reset email. If not, it says no account exists.
2. Search your name at <https://orcid.org/orcid-search/search> — if a record shows your affiliation, you (or your institution) already created an iD.
3. Example University is an ORCID member institution. Check with the your university library / Office of Research before creating a second iD — duplicate iDs are a real problem and have to be merged manually.
4. Being *registered as a researcher* (having an ORCID iD) is separate from having *API credentials*. For credentials, sign in and look under **Developer Tools** in your account settings. If Developer Tools shows a client ID, you're set up for the token flow below.

### Optional: getting a public API token

Only needed for higher rate limits.

1. Register a free ORCID account, sign in, open **Developer Tools**, and register a public API client. You get a client ID and client secret.
2. Exchange them for a read-public token:

```bash
curl -X POST https://orcid.org/oauth/token \
  -H "Accept: application/json" \
  -d "client_id=${ORCID_CLIENT_ID}" \
  -d "client_secret=${ORCID_CLIENT_SECRET}" \
  -d "grant_type=client_credentials" \
  -d "scope=/read-public"
```

3. Export the returned `access_token`:

```bash
export ORCID_ACCESS_TOKEN='...'
```

The tool picks it up automatically. Tokens are secrets — keep them in your environment, never in a config file or in git.

## Requirements

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) (or plain `python3`; there are no third-party runtime dependencies — only the standard library)
- Outbound HTTPS to `pub.orcid.org`

Tested on Ubuntu, RHEL, and Rocky Linux.

## Usage

```bash
uv run main.py
```

Or without uv:

```bash
python3 main.py
```

Defaults to 10 Example University authors with up to 5 works each. Tune with environment variables:

```bash
ORCID_MAX_AUTHORS=25 ORCID_MAX_WORKS=10 uv run main.py

# Any institution, not just Example University
ORCID_AFFILIATION="Some Laboratory" uv run main.py

# Save to a file
uv run main.py > authors.txt
```

## Configuration

All configuration comes from environment variables and is validated at startup — a bad value exits immediately with a clear message rather than failing halfway through.

| Variable | Default | Meaning |
|---|---|---|
| `ORCID_AFFILIATION` | `Example University` | Institution name matched against `affiliation-org-name` |
| `ORCID_MAX_AUTHORS` | `10` | Authors to fetch, 1–1000 (ORCID caps one search page at 1000 rows) |
| `ORCID_MAX_WORKS` | `5` | Works listed per author, 1–100 |
| `ORCID_REQUEST_TIMEOUT` | `30` | Per-request timeout in seconds, 1–300 |
| `ORCID_API_BASE_URL` | `https://pub.orcid.org/v3.0` | Override for the sandbox (`https://pub.sandbox.orcid.org/v3.0`) |
| `ORCID_ACCESS_TOKEN` | unset | Optional bearer token for higher rate limits |
| `LOG_LEVEL` | `INFO` | Standard Python logging level |

## How it works

1. `GET /expanded-search/?q=affiliation-org-name:"<affiliation>"` returns matching ORCID iDs plus names.
2. For each iD, `GET /<orcid-id>/works` returns the works summary, grouped so that the same paper reported from several sources collapses into one group.
3. The first summary in each group supplies the title.
4. Results print as author blocks.

One request per author means N+1 round trips, which is unavoidable — ORCID has no bulk-works endpoint. Requests are throttled to ~2/second. `ORCID_MAX_AUTHORS=1000` therefore takes several minutes.

## Layout

```
main.py                      Orchestration only: load config, harvest, print
orcid_harvest/config.py      Environment config + validation + logging setup
orcid_harvest/client.py      ORCID public API calls, response parsing
orcid_harvest/formatter.py   Pure text formatting, no I/O
tests/                       Unit tests for parsing and formatting
```

Network access is confined to `client.py`, so parsing and formatting are testable without touching the network.

## Tests

```bash
uv run --with pytest==8.4.2 python -m pytest -q
```

Tests cover empty results, missing names, missing titles, malformed ORCID iDs, and multi-author output. They never hit the network.

## Caveats

- **Coverage is partial.** Only researchers who created an ORCID iD *and* recorded a Example University affiliation appear — This is not a complete faculty roster.
- **Affiliation matching is by string.** `Example University` will not match records that say only `Example State University` or `Example University Medicine`. Vary `ORCID_AFFILIATION` to catch those.
- **Works lists are self-reported** and may be incomplete, duplicated across groups, or stale. Some records list no public works at all.
- **Names can be private.** Records with name visibility restricted show `(name not public)`.
- Data from ORCID is licensed CC0, but individual records reflect what researchers chose to make public. Respect that when redistributing.

## References

- ORCID public API docs: <https://info.orcid.org/documentation/features/public-api/>
- API tutorial and endpoint reference: <https://info.orcid.org/documentation/api-tutorials/>
- Rate limits: <https://info.orcid.org/ufaqs/what-are-the-api-limits/>

<br>
