# Notes for working on this repository

- Every user-visible change (entities, card options, setup steps, troubleshooting)
  must be reflected in **both** `README.md` (English, primary) and `README.de.md`
  (German) in the same commit.
- Bump `version` in `custom_components/bambuddy/manifest.json` (and `CARD_VERSION`
  in `frontend/bambuddy-card.js`) for every change users should receive; the
  Release workflow publishes a GitHub release from it, which is what HACS offers
  as an update.
- Add a `## <version>` section to `CHANGELOG.md` for every version bump; the
  Release workflow uses it as the release notes shown in Home Assistant's
  update dialog.
- Keep `translations/en.json`, `translations/de.json` and `strings.json` in sync.
- Run `python -m pytest` before pushing; CI runs hassfest, the HACS action and the tests.
- `docs/card.png` is rendered from sample data; refresh it when the card's look changes.
- Never push when the test run is red; the Release workflow publishes on every
  manifest version bump, so a red push ships a release.
- Load the card only via the dashboard resource. Home Assistant swaps in a
  scoped `window.customElements` while its app starts; anything defined before
  that (e.g. via `add_extra_js_url`) is invisible to the card picker and edit
  mode. `registerCard()` in the card re-registers as a safety net. To verify
  frontend behaviour, run a real HA with `home-assistant-frontend` and drive it
  with Playwright – mock pages don't show registry problems.
