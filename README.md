# Carleton Schedule Builder

An unofficial, fast, visual schedule builder for Carleton University course registration.

**Use it here → https://aap0n.github.io/carleton-schedule-builder/**

## Features

Search any course by code, title, instructor, or CRN — for **every term Carleton has opened** (pick the term in the header) — with a Carleton-Central-style subject dropdown and course-number field for narrowing down. Expanding a course shows its full calendar description, prerequisites, and precludes. Professors with a RateMyProfessors profile get a rating tag next to their name; click it for difficulty, would-take-again %, the rating distribution, and a link to the full profile. Hover a section to preview it on the weekly calendar before committing; click to add it. Conflicts are flagged instantly, linked labs/tutorials ("also register in") are surfaced, and the right panel tracks your credits, class hours per week, and full semester build — plus a CRN box where each CRN copies individually (or all at once) for quick registration in Carleton Central. Each term keeps its own saved schedule automatically in your browser, and the whole schedule exports to an .ics calendar file.

## Data

Course data is scraped automatically from Carleton Central's public course search (draft timetable) by [`scraper/scrape.py`](scraper/scrape.py), which runs on GitHub Actions once a day and commits per-term files to [`data/`](data/) (`courses-<termCode>.json` plus a `terms.json` index). The same run pulls course descriptions, prerequisites, and precludes from the [public calendar](https://calendar.carleton.ca/) into `descriptions.json`. New terms are picked up automatically as Carleton opens them. The header shows the scrape date for the data you're looking at.

Professor ratings come from RateMyProfessors via [`scraper/rmp.py`](scraper/rmp.py), which runs weekly, looks up every instructor in the term data (keeping only confident name matches), and commits `professors.json`.

Rooms are **not** included because Carleton doesn't publish them on the public course search — they're only visible to logged-in students in Carleton Central.

**Manual refresh:** Actions → "Scrape course data" (or "Scrape RateMyProfessors data") → Run workflow.

Times and offerings may change before registration — always confirm in Carleton Central before registering.

## Development

The app is a single `index.html` (vanilla JS/CSS, no build step) that fetches its data from `data/`. Because it uses `fetch`, opening the file directly from disk won't work — serve it locally:

```sh
python3 -m http.server
# then open http://localhost:8000
```

Run the scraper locally with `python3 scraper/scrape.py` (Python 3 stdlib only, no dependencies; ~2–4 min per term).

## Disclaimer

Not affiliated with or endorsed by Carleton University. This is a planning aid; Carleton Central is the source of truth for registration.
