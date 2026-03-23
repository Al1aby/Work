name: Fetch iCloud Calendar

on:
  schedule:
    - cron: '*/15 * * * *'
  workflow_dispatch:

jobs:
  fetch:
    runs-on: ubuntu-latest
    permissions:
      contents: write

    steps:
      - name: Checkout repo
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: pip install requests icalendar python-dateutil

      - name: Fetch calendar and write events.json
        run: python fetch_calendar.py

      - name: Commit changes
        run: |
          git config user.name  "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add events.json
          git diff --cached --quiet || git commit -m "chore: update events.json [skip ci]"
          git push
