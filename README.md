# URL Shortener

A small, self-contained URL shortener built with Flask and SQLite. Paste in a
long URL and get back a short, shareable link. Custom aliases are supported,
and every link tracks how many times it has been clicked.

## Features

- Generates random 6-character base62 short codes (or accepts a custom alias)
- `GET /<short_code>` redirects to the original URL and increments a click counter
- A homepage listing every shortened link with its click count
- Validates submitted URLs (must include a scheme and a domain) before storing them
- App factory pattern (`create_app`) with an in-memory SQLite database for tests

## Project layout

```
url-shortener/
├── app/
│   ├── __init__.py        # app factory, routes, DB access
│   └── templates/
│       └── index.html     # homepage / stats view
├── tests/
│   └── test_app.py        # unit tests using Flask's test client
├── run.py                 # entrypoint for local development
├── requirements.txt
└── .github/workflows/tests.yml
```

## Running locally

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python run.py
```

The app will be available at `http://127.0.0.1:5000/`. On first run it creates
a SQLite database at `instance/urls.db`.

## Running tests

```bash
pip install -r requirements.txt
pytest -v
```

Tests use `create_app(testing=True)`, which spins up an isolated in-memory
SQLite database, so they never touch `instance/urls.db`.

## Example usage

Create a short link:

```bash
curl -X POST http://127.0.0.1:5000/api/links \
  -H "Content-Type: application/json" \
  -d '{"long_url": "https://example.com/some/very/long/path"}'
```

Response:

```json
{
  "long_url": "https://example.com/some/very/long/path",
  "short_code": "aZ3kP9",
  "short_url": "http://127.0.0.1:5000/aZ3kP9",
  "created_at": "2026-01-01T12:00:00+00:00",
  "click_count": 0
}
```

Create a link with a custom alias:

```bash
curl -X POST http://127.0.0.1:5000/api/links \
  -H "Content-Type: application/json" \
  -d '{"long_url": "https://example.com/docs", "custom_alias": "docs"}'
```

Follow a short link (redirects and increments the click counter):

```bash
curl -i http://127.0.0.1:5000/docs
```

Check stats for a short code:

```bash
curl http://127.0.0.1:5000/api/stats/docs
```

Visit `http://127.0.0.1:5000/` in a browser to see the full list of links and
their click counts, and to create new short links from a simple form.

## License

MIT — see [LICENSE](LICENSE).
