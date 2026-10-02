"""AC01/AC02 against the exact private owner-supplied CSVs (read in place, never copied). Fixture class: real."""
import csv
import io
import unittest

from django.test import TestCase

from campaigns.measurement import aggregate
from sources.models import Observation, ObservationContribution, ObservationVersion, RawFile
from sources.services import export_common, export_source_shaped, read_raw, series

from .helpers import bootstrap, import_file, real_fixture

AUDIENCE = real_fixture("opal-season-audience.csv")
SONG = real_fixture("better-man-streams.csv")


@unittest.skipUnless(AUDIENCE and SONG, "Not run: set BAND_EVIDENCE_REAL_FIXTURES to the private real-inputs folder")
class RealSpotifyImport(TestCase):
    def setUp(self):
        self.artist = bootstrap()
        self.audience_batch, self.audience_result = import_file(AUDIENCE, "Opal Season-audience-timeline (1).csv")
        self.song_batch, self.song_result = import_file(SONG, "Better Man-timeline.csv", new_recording_label="Song from streams file")
        self.song = self.song_batch.mapped_entity

    def test_ac01_exact_rows_metrics_and_scoped_totals(self):
        self.assertEqual(self.audience_batch.summary["source_rows"] + self.song_batch.summary["source_rows"], 2004)
        self.assertEqual(Observation.objects.filter(active_version__isnull=False).count(), 9018)
        self.assertEqual(self.audience_batch.summary["first_date"], "2024-01-01")
        self.assertEqual(self.audience_batch.summary["last_date"], "2026-09-28")

        def total(entity, metric):
            return aggregate("flow", [(d, v) for d, v, _ in series(entity, metric)])[0]

        def latest(entity, metric, kind="stock"):
            return aggregate(kind, [(d, v) for d, v, _ in series(entity, metric)])[0]

        a = self.artist.entity
        self.assertEqual(total(self.song, "spotify.recording.streams.v1"), 200)
        self.assertEqual(total(a, "spotify.artist.streams.v1"), 200)
        self.assertEqual(total(a, "spotify.artist.saves.v1"), 25)
        self.assertEqual(total(a, "spotify.artist.playlist_adds.v1"), 15)
        self.assertEqual(latest(a, "spotify.artist.followers.v1"), 22)
        self.assertEqual(latest(a, "spotify.artist.monthly_listeners.v1", "rolling_stock"), 94)
        self.assertEqual(latest(a, "spotify.artist.monthly_active_listeners.v1", "nested_stock"), 94)
        self.assertEqual(latest(a, "spotify.artist.super_listeners.v1", "nested_stock"), 1)
        # Artist and recording streams are different scopes and are never combined.
        self.assertFalse(Observation.objects.filter(entity=a, metric_id="spotify.recording.streams.v1").exists())
        nonzero = [d for d, v, _ in series(self.song, "spotify.recording.streams.v1") if v]
        self.assertEqual(len(nonzero), 5)
        self.assertEqual((min(nonzero).isoformat(), max(nonzero).isoformat()), ("2026-09-24", "2026-09-28"))

    def test_ac01_lossless_source_and_common_round_trip(self):
        def parsed(raw):
            text = raw.decode("utf-8-sig")
            return [tuple(r) for r in csv.reader(io.StringIO(text)) if r]

        self.assertEqual(parsed(export_source_shaped(self.artist.entity)), parsed(AUDIENCE))
        self.assertEqual(parsed(export_source_shaped(self.song)), parsed(SONG))
        common = list(csv.DictReader(io.StringIO(export_common().decode())))
        self.assertEqual(len(common), 9018)
        # Original bytes are retained exactly.
        self.assertEqual(read_raw(self.audience_batch.raw_file), AUDIENCE)
        self.assertEqual(read_raw(self.song_batch.raw_file), SONG)

    def test_ac02_replay_and_rename_add_no_facts(self):
        before = (Observation.objects.count(), ObservationVersion.objects.count())
        batch, result = import_file(AUDIENCE, "renamed-copy.csv")
        self.assertEqual(result["new_facts"], 0)
        self.assertEqual(result["unchanged"], 8016)
        self.assertEqual((Observation.objects.count(), ObservationVersion.objects.count()), before)
        self.assertEqual(RawFile.objects.count(), 2, "Same bytes reuse one stored original")
        # Provenance records the second import as an additional contribution, not a new fact.
        self.assertEqual(ObservationContribution.objects.filter(batch=batch).count(), 8016)
        _, song_again = import_file(SONG, "Some other name.csv", recording=self.song_batch.mapped_entity.promoted_object)
        self.assertEqual(song_again["new_facts"], 0)
