# Notes for working on this repository

- Every user-visible change (entities, card options, setup steps, troubleshooting)
  must be reflected in **both** `README.md` (English, primary) and `README.de.md`
  (German) in the same commit.
- Bump `version` in `custom_components/bambuddy/manifest.json` (and `CARD_VERSION`
  in `frontend/bambuddy-card.js`) for every change users should receive; the
  Release workflow publishes a GitHub release from it, which is what HACS offers
  as an update.
- Keep `translations/en.json`, `translations/de.json` and `strings.json` in sync.
- Run `python -m pytest` before pushing; CI runs hassfest, the HACS action and the tests.
- `docs/card.png` is rendered from sample data; refresh it when the card's look changes.
