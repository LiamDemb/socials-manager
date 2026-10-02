"""AC12 Evidence tabs, AC13 nested dialog navigation and a rendered layout check, in installed Chrome.

Runs a real server against a fresh synthetic data root. Skipped (Not run) when Playwright or Chrome is unavailable.
"""
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.request
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

try:
    from playwright.sync_api import expect, sync_playwright
except ImportError:  # runtime environment does not install test-only dependencies
    sync_playwright = None

ROOT = Path(settings.BASE_DIR)
LONG_TITLE = "Teaser" + "x" * 140
LONG_BRIEF = ("Long brief line with ordinary words that should wrap inside the panel. " * 70)[:5000]

SEED = """
import json
from datetime import date, timedelta
from zoneinfo import ZoneInfo
from django.utils import timezone
from catalogue.services import create_object
from campaigns.services import create_campaign, add_activity
from sources.services import preview_upload, set_mapping, commit

today = timezone.now().astimezone(ZoneInfo('Australia/Perth')).date()
days = [today - timedelta(days=40 - i) for i in range(36)]
head = 'date,listeners,monthly listeners,monthly active listeners,super listeners,streams,playlist adds,saves,followers'
rows = [f'{d},{10+i},{100+i},{40+i},{i % 5},{20+i},{i % 3},{i % 4},{50+i}' for i, d in enumerate(days)]
b = preview_upload(('\\ufeff' + '\\n'.join([head] + rows) + '\\n').encode(), 'fixture-audience.csv')
commit(b.pk, b.preview_revision, 'browser-audience')
song = create_object('recording', 'Fixture song')
b = preview_upload(('\\ufeff' + '\\n'.join(['date,streams'] + [f'{d},{5+i}' for i, d in enumerate(days)]) + '\\n').encode(), 'fixture-song.csv')
b = set_mapping(b.pk, b.preview_revision, entity_id=song.pk)
commit(b.pk, b.preview_revision, 'browser-song')
c = create_campaign({'type': 'single', 'name': 'Fixture single', 'start_date': str(today - timedelta(days=5)),
    'end_date': str(today + timedelta(days=25)), 'object': {'mode': 'existing', 'id': str(song.pk)},
    'primary_outcome': {'mode': 'new', 'metric_id': 'spotify.recording.streams.v1', 'outcome_mode': 'total', 'target': 500}},
    'browser-campaign')
a = add_activity(c['campaign_id'], {'title': TITLE, 'date': str(today), 'purpose': 'Purpose ' * 200, 'brief': BRIEF,
    'cta': 'Pre-save the single', 'checklist': ['Film', 'Edit', 'Caption']}, 'browser-activity')
print(json.dumps({'activity': str(a['activity_id']), 'campaign': str(c['campaign_id'])}))
"""

VIEWPORTS = [(360, 640), (768, 1024), (1440, 900), (812, 375)]


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@unittest.skipIf(sync_playwright is None, "Not run: Playwright is not installed (requirements-test.txt)")
class Browser(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tmp = Path(tempfile.mkdtemp(prefix="be-browser-"))
        cls.env = {k: v for k, v in os.environ.items() if not k.startswith(("SOCIALS_MANAGER_", "BAND_EVIDENCE_")) and k != "DJANGO_SETTINGS_MODULE"}
        cls.env.update(SOCIALS_MANAGER_DATA_ROOT=str(cls.tmp / "data"), DJANGO_SETTINGS_MODULE="socials_manager.settings")
        cls.manage("init_instance", "--artist", "Fixture Band", "--timezone", "Australia/Perth", "--synthetic")
        script = f"TITLE = {LONG_TITLE!r}\nBRIEF = {LONG_BRIEF!r}\n" + SEED
        cls.ids = json.loads(cls.manage("shell", "-c", script).stdout.strip().splitlines()[-1])
        cls.port = free_port()
        cls.base = f"http://127.0.0.1:{cls.port}"
        cls.server = subprocess.Popen([sys.executable, str(ROOT / "manage.py"), "serve", "--port", str(cls.port)],
                                      cwd=ROOT, env=cls.env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(100):
            try:
                urllib.request.urlopen(cls.base + "/today", timeout=1)
                break
            except OSError:
                time.sleep(0.1)
        cls.pw = sync_playwright().start()
        try:
            cls.browser = cls.pw.chromium.launch(channel="chrome", headless=True)
        except Exception as exc:  # Chrome not installed
            cls.tearDownClass()
            raise unittest.SkipTest(f"Not run: Chrome channel unavailable ({exc.__class__.__name__})")

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "browser", None):
            cls.browser.close()
        if getattr(cls, "pw", None):
            cls.pw.stop()
        if getattr(cls, "server", None):
            cls.server.terminate()
            cls.server.wait(timeout=10)
        super().tearDownClass()

    @classmethod
    def manage(cls, *args):
        proc = subprocess.run([sys.executable, str(ROOT / "manage.py"), *args], cwd=ROOT, env=cls.env,
                              capture_output=True, text=True, timeout=120)
        if proc.returncode != 0:
            raise AssertionError(f"{args[0]} failed: {proc.stdout}\n{proc.stderr}")
        return proc

    def setUp(self):
        self.context = self.browser.new_context(viewport={"width": 1440, "height": 900}, timezone_id="Australia/Perth")
        self.page = self.context.new_page()
        self.errors = []
        self.page.on("pageerror", lambda e: self.errors.append(str(e)))
        self.page.on("console", lambda m: m.type == "error" and self.errors.append(m.text))

    def tearDown(self):
        self.context.close()
        self.assertEqual(self.errors, [], "No script or CSP errors in the console")

    def heading(self):
        return self.page.locator("#app-dialog #dialog-title")

    def back_nav(self):
        return self.page.locator("#app-dialog [data-frame-nav] .back-nav")

    # ---------- AC12 ----------

    def test_ac12_evidence_tabs(self):
        p = self.page
        p.goto(self.base + "/evidence")
        tablists = p.get_by_role("tablist")
        expect(tablists).to_have_count(1)
        tab_names = ["Findings", "Observed data", "Review context"]
        self.assertEqual([t.inner_text().strip() for t in p.get_by_role("tab").all()], tab_names)
        expect(p.get_by_role("tab", name="Findings")).to_have_attribute("aria-selected", "true")

        p.get_by_role("tab", name="Observed data").click()
        p.wait_for_url("**/evidence/data")
        p.get_by_label("Metric").select_option("spotify.recording.streams.v1")
        p.get_by_role("button", name="Filter").click()
        p.wait_for_url("**/evidence/data?*metric=spotify.recording.streams.v1*")
        expect(p.locator("table.data tbody tr")).to_have_count(1)

        p.get_by_role("tab", name="Review context").click()
        p.wait_for_url("**/evidence/review")
        self.assertEqual([t.inner_text().strip() for t in p.get_by_role("tab").all()], tab_names)
        p.get_by_role("tab", name="Observed data").click()
        p.wait_for_url("**/evidence/data?*metric=spotify.recording.streams.v1*")
        expect(p.get_by_label("Metric")).to_have_value("spotify.recording.streams.v1")

        p.get_by_role("link", name="Underlying data").click()
        p.wait_for_url("**/evidence/data/*/spotify.recording.streams.v1?*")
        self.assertEqual([t.inner_text().strip() for t in p.get_by_role("tab").all()], tab_names)
        expect(p.get_by_role("tab", name="Observed data")).to_have_attribute("aria-selected", "true")
        series_url = p.url

        p.locator("table.data a", has_text="Source").first.click()
        expect(self.heading()).to_have_text("Song streams")
        p.locator("#app-dialog .modal-body a[data-dialog-push]").first.click()
        expect(self.back_nav()).to_contain_text("Observation")
        self.back_nav().click()
        expect(self.heading()).to_have_text("Song streams")
        expect(self.back_nav()).to_have_count(0)
        p.go_back()
        expect(p.locator("#app-dialog")).not_to_be_visible()
        self.assertEqual(p.url, series_url)

        p.locator("[data-back-link]").click()
        p.wait_for_url("**/evidence/data?*metric=spotify.recording.streams.v1*")
        expect(p.get_by_label("Metric")).to_have_value("spotify.recording.streams.v1")
        p.go_back()
        self.assertEqual(p.url, series_url)

    # ---------- AC13 ----------

    def test_ac13_nested_dialog_navigation(self):
        p = self.page
        p.goto(self.base + "/today")
        trigger = p.locator("#main a[data-dialog-open]", has_text=LONG_TITLE[:20]).first
        trigger.click()
        expect(self.heading()).to_have_text(LONG_TITLE)
        expect(self.back_nav()).to_have_count(0)

        dialog = p.locator("#app-dialog")
        dialog.locator("textarea[name=notes]").fill("Draft note kept across navigation")
        dialog.locator("details summary", has_text="Skip or cancel").click()
        dialog.locator("details summary", has_text="Brief").click()
        body = dialog.locator(".modal-body")
        why = dialog.get_by_role("link", name="Why?")
        why.evaluate("el => el.focus({ preventScroll: true })")
        body.evaluate("el => { el.scrollTop = 350; }")
        scroll_before = body.evaluate("el => el.scrollTop")
        self.assertGreater(scroll_before, 0, "Long activity content scrolls inside the dialog body")
        why.evaluate("el => el.click()")
        expect(self.heading()).to_have_text("Why this activity?")
        expect(self.back_nav()).to_contain_text("Activity")
        nav_box = self.back_nav().bounding_box()
        head_box = self.heading().bounding_box()
        self.assertLess(nav_box["y"], head_box["y"], "Back navigation sits above the heading")

        dialog.get_by_role("link", name="Spotify for Artists").first.click()
        expect(self.back_nav()).to_contain_text("Reasoning")
        self.back_nav().click()
        expect(self.heading()).to_have_text("Why this activity?")
        self.back_nav().click()
        expect(self.heading()).to_have_text(LONG_TITLE)

        expect(dialog.locator("textarea[name=notes]")).to_have_value("Draft note kept across navigation")
        self.assertTrue(dialog.locator("details", has=p.locator("summary", has_text="Skip or cancel")).evaluate("d => d.open"))
        self.assertTrue(dialog.locator("details.brief").evaluate("d => d.open"))
        self.assertAlmostEqual(body.evaluate("el => el.scrollTop"), scroll_before, delta=2)
        expect(dialog.get_by_role("link", name="Why?")).to_be_focused()

        # Browser history moves through the same frames.
        dialog.get_by_role("link", name="Why?").click()
        expect(self.heading()).to_have_text("Why this activity?")
        p.go_back()
        expect(self.heading()).to_have_text(LONG_TITLE)
        p.go_forward()
        expect(self.heading()).to_have_text("Why this activity?")
        p.go_back()
        expect(self.heading()).to_have_text(LONG_TITLE)

        # A dirty draft asks before closing.
        p.keyboard.press("Escape")
        expect(dialog.get_by_role("button", name="Keep editing")).to_be_visible()
        dialog.get_by_role("button", name="Keep editing").click()
        expect(dialog).to_be_visible()

        # Save a mutation in a nested frame, then return: the activity is re-fetched.
        dialog.get_by_role("link", name="Edit").click()
        expect(self.heading()).to_have_text("Edit activity")
        dialog.get_by_label("Title").fill("Renamed teaser")
        dialog.get_by_role("button", name="Save").click()
        expect(self.heading()).to_have_text("Renamed teaser")
        expect(self.back_nav()).to_have_count(0)
        expect(dialog.locator("textarea[name=notes]")).to_have_value("Draft note kept across navigation")
        expect(p.locator("#main")).to_contain_text("Renamed teaser")

        p.keyboard.press("Escape")
        dialog.get_by_role("button", name="Discard").click()
        expect(dialog).not_to_be_visible()
        self.assertNotIn("d=", p.url)
        focused = p.evaluate("document.activeElement && document.activeElement.getAttribute('href')")
        self.assertEqual(focused, f"/ui/activity/{self.ids['activity']}")

    def test_ac13_deep_link_restores_stack(self):
        p = self.page
        a = self.ids["activity"]
        p.goto(f"{self.base}/today?d=/ui/activity/{a}&d=/ui/activity/{a}/why")
        expect(self.heading()).to_have_text("Why this activity?")
        expect(self.back_nav()).to_be_visible()
        self.back_nav().click()
        expect(self.heading()).not_to_have_text("Why this activity?")
        self.assertIn(f"d=%2Fui%2Factivity%2F{a}", p.url)
        self.assertNotIn("why", p.url)

    # ---------- Core flow through the interface ----------

    def test_import_then_create_campaign_and_execute(self):
        p = self.page
        p.goto(self.base + "/sources")
        p.locator('a[href="/ui/upload"]').first.click()
        expect(self.heading()).to_have_text("Import a Spotify for Artists CSV")
        csv = "\ufeffdate,streams\n" + "".join(f"2026-08-{d:02d},{d * 3}\n" for d in range(1, 11))
        p.get_by_label("CSV file").set_input_files({"name": "ui-song-streams.csv", "mimeType": "text/csv", "buffer": csv.encode()})
        p.get_by_role("button", name="Preview import").click()
        p.wait_for_url("**/sources/imports/*")
        expect(p.locator("#main")).to_contain_text("Preview, nothing stored yet")
        p.get_by_label("A new recording").check()
        p.locator("input[name=new_label]").fill("Interface song")
        p.get_by_role("button", name="Use this recording").click()
        expect(p.get_by_role("button", name="Import 10 values")).to_be_visible()
        p.get_by_role("button", name="Import 10 values").click()
        expect(p.get_by_role("heading", name="Imported")).to_be_visible()

        p.goto(self.base + "/campaigns")
        p.locator(".top-actions").get_by_role("link", name="Create campaign").click()
        expect(self.heading()).to_have_text("Create campaign")
        dialog = p.locator("#app-dialog")
        dialog.get_by_label("Campaign name").fill("Interface single")
        end = p.evaluate("() => { const d = new Date(); d.setDate(d.getDate() + 20); return d.toISOString().slice(0, 10); }")
        dialog.get_by_label("Ends").fill(end)
        dialog.get_by_label("Item").select_option(label="Interface song")
        expect(dialog.get_by_label("Measure").first).to_have_value("spotify.recording.streams.v1")
        dialog.get_by_label("Target").first.fill("300")
        dialog.get_by_role("button", name="Continue").click()
        expect(dialog.locator("[data-step-label]")).to_have_text("2 of 3 · Resources")
        dialog.get_by_role("button", name="Continue").click()
        expect(dialog.locator("[data-step-label]")).to_have_text("3 of 3 · Review")
        dialog.get_by_role("button", name="Create campaign").click()
        p.wait_for_url("**/campaigns/*")
        expect(p.locator(".page-title")).to_contain_text("Interface single")

        item = p.locator("#main a[data-dialog-open][href^='/ui/activity/']").first
        item.click()
        expect(dialog.get_by_role("button", name="Mark complete")).to_be_visible()
        dialog.get_by_role("button", name="Mark complete").click()
        expect(dialog.locator(".activity-when .badge")).to_have_text("Completed")
        expect(dialog.get_by_role("button", name="Mark complete")).to_have_count(0)

    # ---------- Rendered layout ----------

    def test_layout_long_content_at_viewports(self):
        a = self.ids["activity"]
        for width, height in VIEWPORTS:
            with self.subTest(viewport=f"{width}x{height}"):
                p = self.page
                p.set_viewport_size({"width": width, "height": height})
                for path in ("/today", f"/campaigns/{self.ids['campaign']}", "/evidence/data", "/sources", "/settings"):
                    p.goto(self.base + path)
                    overflow = p.evaluate("document.documentElement.scrollWidth - window.innerWidth")
                    self.assertLessEqual(overflow, 1, f"{path} has no horizontal page overflow")
                p.goto(f"{self.base}/today?d=/ui/activity/{a}")
                dialog = p.locator("#app-dialog")
                expect(self.heading()).to_be_visible()
                dialog.locator("details.brief summary").click()
                box = dialog.bounding_box()
                self.assertGreaterEqual(box["x"], -1)
                self.assertGreaterEqual(box["y"], -1)
                self.assertLessEqual(box["x"] + box["width"], width + 1, "Dialog fits horizontally")
                self.assertLessEqual(box["y"] + box["height"], height + 1, "Dialog fits vertically")
                wide = dialog.evaluate("d => Array.from(d.querySelectorAll('*')).filter(e => e.scrollWidth > d.clientWidth + 1 && getComputedStyle(e).overflowX === 'visible').length")
                self.assertEqual(wide, 0, "Long words and briefs wrap inside the dialog")
                for name in ("Close", "Mark complete", "Edit"):
                    target = dialog.get_by_role("button", name=name) if name != "Edit" else dialog.get_by_role("link", name="Edit")
                    target.scroll_into_view_if_needed()
                    tb = target.bounding_box()
                    self.assertTrue(tb and 0 <= tb["y"] and tb["y"] + tb["height"] <= height + 1, f"{name} reachable")
                    hit = target.evaluate("el => { const r = el.getBoundingClientRect(); const h = document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2); return el === h || el.contains(h); }")
                    self.assertTrue(hit, f"{name} is not covered by other content")
