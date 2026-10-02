# Instagram / Meta setup for @opalseason_

Live integration is **Blocked** until you complete these steps. The app will not call Meta without a stored token and a successful capability probe.

## What you need

1. **Meta developer account** with access to [developers.facebook.com](https://developers.facebook.com/).
2. **Facebook Page** linked to the Opal Season Instagram professional account **@opalseason_**.
3. **Meta app** (Business type) with:
   - Instagram Graph API product added
   - A pinned Graph API version (record it in the app; the probe will store the version string, not secrets)
4. **Permissions** (exact names depend on the route; typical own-account insights need combinations such as):
   - `instagram_basic`
   - `instagram_manage_insights`
   - `pages_read_engagement`
   - Page access via the linked Facebook Page

   App Review is required for production data. Development mode only sees test users you add.

5. **Long-lived access token** for the Page or a System User in Business Manager. Generate it in Meta’s tools; do not paste it into chat or commit it.

## What to run locally

With the app **stopped**, save the token (example shape only):

```json
{
  "api_version": "v21.0",
  "page_id": "YOUR_PAGE_ID",
  "instagram_business_account_id": "YOUR_IG_USER_ID",
  "access_token": "YOUR_TOKEN"
}
```

Store as `secrets/instagram.json` inside your data folder (`~/Library/Application Support/SocialsManager/secrets/instagram.json`). File mode should be `600`.

Then:

```sh
export SOCIALS_MANAGER_DATA_ROOT="$HOME/Library/Application Support/SocialsManager"
bin/socials-manager status
python manage.py probe_instagram
```

The probe writes a **sanitised** capability report under `reports/` (no token, no fan data). Until `live_integration` is not Blocked, the collector records **Blocked** and does not invent metrics.

## If you are unsure

Mark **Meta developer/app access: UNSURE** is fine. Independent work (adapters, fixtures, UI, policy gates) continues. Only live collection and authenticated probes stay blocked.
