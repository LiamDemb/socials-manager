# Instagram / Meta setup for @opalseason_

## What the probe found (your current `.env`)

With **Instagram Login** (`INSTAGRAM_ACCESS_TOKEN`), the app can read:

- `user_id`, `username`, `account_type` (e.g. `MEDIA_CREATOR`) via `graph.instagram.com`

It **cannot** read (with this route):

- `followers_count`, `media_count`, insights, `online_followers`
- **Business Discovery** for peers

**Reason:** Business Discovery and professional insights require **Facebook Login for Business** with a **Facebook Page** linked to the Instagram professional account, and a Page access token on the Graph API (`graph.facebook.com`). Selecting the Instagram use case in the Meta developer console alone does **not** enable Business Discovery.

Run anytime (sanitised output, no secrets):

```sh
python manage.py probe_meta
# optional peer username once Page-linked token works:
python manage.py probe_meta --peer someconfirmedpeer
```

## Required configuration change for peers (~50) and full own-account metrics

1. In [Meta for Developers](https://developers.facebook.com/), use (or create) an app with **Facebook Login for Business** (not Instagram Login only).
2. Add **Instagram Graph API** and **Pages** products.
3. Connect the **Facebook Page** that owns @opalseason_.
4. Generate a **Page access token** with permissions such as:
   - `instagram_basic`
   - `instagram_manage_insights`
   - `pages_read_engagement`
   - `pages_show_list`
5. Store in `.env` (never commit):
   - `META_ACCESS_TOKEN=` Page or System User token
   - `META_APP_ID=`
   - Keep `INSTAGRAM_ACCESS_TOKEN` only if you still use the basic route for smoke tests
6. Re-run `probe_meta`. Expect `business_discovery_supported: true` and `facebook_page_id` set.

## Peer collection in the app

1. **Discover** candidates: Peers → **Discover similar (Last.fm)** or `lastfm_discover`.
2. **Promote** with a confirmed **Instagram @username** (not guessed from the artist name).
3. **Collect:** worker job `collect.source` / `python manage.py collect_peers` uses Business Discovery when supported.

## Token storage

- Preferred: `.env` in the repository root (gitignored).
- Optional legacy: `secrets/instagram.json` in the data folder (mode `600`).

Do not paste tokens into chat, commits or screenshots.
