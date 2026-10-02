"""HTTP layer: pages render real state, API envelope, and AC35 local-boundary controls (loopback, CSRF, keys, uploads)."""
import json
import re
import uuid

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings

from campaigns.models import Activity, Campaign
from core import clock

from .helpers import audience_csv, bootstrap, recording_csv, utc


def post(client, url, body=None, key=None, **extra):
    return client.post(url, data=json.dumps(body or {}), content_type="application/json",
                       HTTP_IDEMPOTENCY_KEY=key or f"test-{uuid.uuid4()}", **extra)


class WebFlow(TestCase):
    def setUp(self):
        self.artist = bootstrap()
        self.client = Client(REMOTE_ADDR="127.0.0.1")

    def upload(self, raw, name):
        res = self.client.post("/api/imports", {"file": SimpleUploadedFile(name, raw, content_type="text/csv")},
                               HTTP_IDEMPOTENCY_KEY=f"test-{uuid.uuid4()}")
        self.assertEqual(res.status_code, 200, res.content)
        return res.json()["data"]["batch_id"]

    def batch_revision(self, batch_id):
        from sources.models import ImportBatch

        return ImportBatch.objects.get(pk=batch_id).preview_revision

    def test_pages_render_empty_install(self):
        for url in ["/today", "/campaigns", "/calendar", "/evidence", "/evidence/findings", "/evidence/data", "/evidence/review",
                    "/sources", "/settings", "/peers", "/inspiration", "/ask", "/ui/campaign/new", "/ui/upload", "/ui/object/new"]:
            with self.subTest(url=url):
                res = self.client.get(url)
                self.assertEqual(res.status_code, 200, url)
                self.assertNotIn(b"Traceback", res.content)
        self.assertContains(self.client.get("/today"), "No Spotify data yet")
        self.assertRedirects(self.client.get("/"), "/today", fetch_redirect_response=False)

    def test_import_through_http_then_campaign_execute_and_evidence(self):
        audience = audience_csv([(f"2026-09-{d:02d}", 1, 90 + d, 90, 1, d, 0, 1, 20 + d) for d in range(1, 29)])
        a_id = self.upload(audience, "Band-audience-timeline.csv")
        self.assertContains(self.client.get(f"/sources/imports/{a_id}"), "28 rows")
        res = post(self.client, f"/api/imports/{a_id}/commit", {"revision": self.batch_revision(a_id)})
        self.assertEqual(res.status_code, 200, res.content)
        self.assertEqual(res.json()["data"]["new_facts"], 28 * 8)

        s_id = self.upload(recording_csv([("2026-09-24", 50), ("2026-09-25", 60)]), "My Song-timeline.csv")
        page = self.client.get(f"/sources/imports/{s_id}")
        self.assertContains(page, "a name is not proof of identity")
        res = post(self.client, f"/api/imports/{s_id}/commit", {"revision": self.batch_revision(s_id)})
        self.assertEqual(res.json()["error"]["code"], "mapping_required")
        res = post(self.client, f"/api/imports/{s_id}/mapping", {"revision": self.batch_revision(s_id), "target": "new", "new_label": "My Song"})
        self.assertEqual(res.status_code, 200, res.content)
        post(self.client, f"/api/imports/{s_id}/commit", {"revision": self.batch_revision(s_id)})

        today = self.client.get("/today")
        self.assertContains(today, "Artist streams")
        self.assertContains(today, "Data through")
        for kind in ("original", "source", "common"):
            self.assertEqual(self.client.get(f"/sources/imports/{s_id}/download/{kind}").status_code, 200)

        with clock.frozen(utc(2026, 9, 20, 2)):
            preview = post(self.client, "/api/campaigns/preview", {"campaign": {
                "type": "audience_growth", "name": "Grow", "start_date": "2026-09-10", "end_date": "2026-10-09",
                "primary_outcome": {"mode": "new", "metric_id": "spotify.artist.followers.v1", "outcome_mode": "gain", "target": 100}}})
            self.assertEqual(preview.status_code, 200, preview.content)
            self.assertIn("Import the starting snapshot", preview.json()["data"]["html"])
            self.assertEqual(Campaign.objects.count(), 0, "Preview persists nothing")
            created = post(self.client, "/api/campaigns", {"campaign": {
                "type": "audience_growth", "name": "Grow", "start_date": "2026-09-10", "end_date": "2026-10-09",
                "primary_outcome": {"mode": "new", "metric_id": "spotify.artist.followers.v1", "outcome_mode": "gain", "target": 100},
                "activities": [{"title": "Reel <b>teaser</b>", "date": "2026-09-20", "time": "17:00", "channel": "instagram", "format": "Reel"}]}})
            self.assertEqual(created.status_code, 200, created.content)
            cid = created.json()["data"]["campaign_id"]
            act = Activity.objects.get(campaign_id=cid)
            page = self.client.get(f"/campaigns/{cid}?month=2026-09")
            self.assertContains(page, "Reel &lt;b&gt;teaser&lt;/b&gt;")
            self.assertNotContains(page, "Reel <b>teaser</b>")
            self.assertContains(self.client.get(f"/ui/activity/{act.pk}"), "Due today")
            self.assertContains(self.client.get(f"/ui/activity/{act.pk}/why"), "Supporting finding")
            outcomes = self.client.get(f"/campaigns/{cid}/outcomes")
            self.assertContains(outcomes, "+100 spotify followers")
            res = post(self.client, f"/api/activities/{act.pk}/execute", {"revision": act.revision, "action": "complete", "actual_at": "2026-09-20T09:30"})
            self.assertEqual(res.status_code, 200, res.content)
            stale = post(self.client, f"/api/activities/{act.pk}/execute", {"revision": act.revision, "action": "skip", "reason": "x"})
            self.assertEqual(stale.status_code, 409)
            self.assertEqual(stale.json()["error"]["code"], "stale_revision")

        data = self.client.get("/evidence/data")
        self.assertContains(data, "Underlying data")
        song = Campaign.objects.none()
        from catalogue.models import PromotedObject

        song = PromotedObject.objects.get(kind="recording")
        series = self.client.get(f"/evidence/data/{song.pk}/spotify.recording.streams.v1?entity={song.pk}")
        self.assertContains(series, "‹ Observed data")
        self.assertContains(series, f'href="/evidence/data?entity={song.pk}"')
        version = re.search(r'/ui/observation/([0-9a-f-]{36})', series.content.decode()).group(1)
        self.assertContains(self.client.get(f"/ui/observation/{version}"), "Versions")
        self.assertEqual(self.client.get("/settings").status_code, 200)
        self.assertContains(self.client.get("/settings"), "Insufficient data")

    def test_invalid_upload_is_shown_not_stored(self):
        bad = self.upload(b"day,streams\n2026-01-01,1\n", "bad.csv")
        page = self.client.get(f"/sources/imports/{bad}")
        self.assertContains(page, "This file cannot be imported")

    def test_settings_update_and_validation(self):
        res = post(self.client, "/api/settings", {"timezone": "Mars/Base"})
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()["error"]["fields"], {"timezone": "Unknown timezone"})
        res = post(self.client, "/api/settings", {"artist_label": "New Name", "weekly_capacity_minutes": "300",
                                                  "spotify_artist_url": "https://open.spotify.com/artist/ArtistFixture000000001"})
        self.assertEqual(res.status_code, 200, res.content)
        self.assertContains(self.client.get("/settings"), "ArtistFixture000000001")


class Boundary(TestCase):
    def setUp(self):
        bootstrap()

    def test_non_loopback_refused(self):
        for addr in ("192.168.1.20", "10.0.0.5", "8.8.8.8", ""):
            res = Client(REMOTE_ADDR=addr).get("/today")
            self.assertEqual(res.status_code, 403, addr)

    def test_csrf_enforced_on_api(self):
        client = Client(enforce_csrf_checks=True, REMOTE_ADDR="127.0.0.1")
        res = post(client, "/api/settings", {"artist_label": "X"})
        self.assertEqual(res.status_code, 403)
        page = client.get("/settings")
        token = re.search(rb'name="csrf-token" content="([^"]+)"', page.content).group(1).decode()
        res = post(client, "/api/settings", {"artist_label": "X"}, HTTP_X_CSRFTOKEN=token)
        self.assertEqual(res.status_code, 200, res.content)

    def test_idempotency_key_required_and_get_refused(self):
        client = Client(REMOTE_ADDR="127.0.0.1")
        res = client.post("/api/settings", data="{}", content_type="application/json")
        self.assertEqual(res.json()["error"]["code"], "idempotency_key_required")
        self.assertEqual(client.get("/api/settings").status_code, 405)

    @override_settings(MAX_UPLOAD_BYTES=100)
    def test_upload_limit(self):
        client = Client(REMOTE_ADDR="127.0.0.1")
        res = client.post("/api/imports", {"file": SimpleUploadedFile("big.csv", b"date,streams\n" + b"2026-01-01,1\n" * 20)},
                          HTTP_IDEMPOTENCY_KEY=f"test-{uuid.uuid4()}")
        self.assertEqual(res.json()["error"]["code"], "file_too_large")

    def test_security_headers_and_static_scope(self):
        client = Client(REMOTE_ADDR="127.0.0.1")
        res = client.get("/today")
        self.assertIn("default-src 'self'", res["Content-Security-Policy"])
        self.assertEqual(res["X-Frame-Options"], "DENY")
        self.assertEqual(res["Cache-Control"], "no-store")
        self.assertEqual(client.get("/static/js/app.js").status_code, 200)
        self.assertEqual(client.get("/static/../settings.py").status_code, 404)
        self.assertEqual(client.get("/static/css/../../views.py").status_code, 404)

    def test_errors_do_not_leak_internals(self):
        client = Client(REMOTE_ADDR="127.0.0.1")
        res = post(client, f"/api/activities/{uuid.uuid4()}/execute", {"revision": 1, "action": "complete"})
        self.assertEqual(res.status_code, 404)
        self.assertEqual(set(res.json()["error"]), {"code", "message", "fields", "retryable"})
