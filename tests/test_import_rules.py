"""AC02 (synthetic revisions), AC03, AC04, AC05. Fixture class: synthetic."""
from datetime import date

from django.test import TestCase, override_settings

from catalogue.services import create_object, set_artist_spotify, update_object
from core.errors import DomainError
from sources.models import ImportBatch, Observation, ObservationVersion, SourcePolicyVersion
from sources.services import (
    approve_conflicts,
    commit,
    ensure_spotify_source,
    preview_upload,
    read_raw,
    series,
    set_mapping,
    undo,
)

from .helpers import audience_csv, bootstrap, import_file, key, recording, recording_csv


def days(*pairs):
    return list(pairs)


class RevisionsAndOverlap(TestCase):
    def setUp(self):
        self.artist = bootstrap()
        self.song = recording("Fixture song")
        _, self.first = import_file(recording_csv([("2026-09-01", 5), ("2026-09-02", 7)]), "a.csv", recording=self.song)

    def values(self):
        return [(d.isoformat(), v) for d, v, _ in series(self.song.entity, "spotify.recording.streams.v1")]

    def test_overlap_adds_only_new_day(self):
        _, result = import_file(recording_csv([("2026-09-02", 7), ("2026-09-03", 4)]), "b.csv", recording=self.song)
        self.assertEqual((result["new_facts"], result["unchanged"]), (1, 1))
        self.assertEqual(self.values(), [("2026-09-01", 5), ("2026-09-02", 7), ("2026-09-03", 4)])

    def test_unapproved_conflict_rolls_back_then_approved_revision_is_immutable(self):
        raw = recording_csv([("2026-09-02", 9), ("2026-09-03", 1)])
        batch = preview_upload(raw, "corrected.csv")
        batch = set_mapping(batch.pk, batch.preview_revision, entity_id=self.song.pk)
        self.assertEqual((batch.summary["conflict"], batch.summary["new"]), (1, 1))
        with self.assertRaises(DomainError) as err:
            commit(batch.pk, batch.preview_revision, key())
        self.assertEqual(err.exception.code, "unapproved_revisions")
        self.assertEqual(self.values(), [("2026-09-01", 5), ("2026-09-02", 7)], "Whole batch rolled back, new day included")
        with self.assertRaises(DomainError):
            approve_conflicts(batch.pk, batch.preview_revision, "all", "")
        batch = approve_conflicts(batch.pk, batch.preview_revision, "all", "Spotify corrected this day")
        commit(batch.pk, batch.preview_revision, key())
        self.assertEqual(self.values(), [("2026-09-01", 5), ("2026-09-02", 9), ("2026-09-03", 1)])
        obs = Observation.objects.get(entity=self.song.entity, period_start=date(2026, 9, 2))
        versions = list(obs.versions.order_by("version").values_list("version", "value", "revision_reason"))
        self.assertEqual(versions, [(1, 7, ""), (2, 9, "Spotify corrected this day")])
        self.assertEqual(read_raw(batch.raw_file), raw)

    def test_stale_preview_after_other_commit(self):
        raw = recording_csv([("2026-09-05", 3)])
        a = set_mapping(*(lambda b: (b.pk, b.preview_revision))(preview_upload(raw, "x.csv")), entity_id=self.song.pk)
        b = preview_upload(recording_csv([("2026-09-05", 4)]), "y.csv")
        b = set_mapping(b.pk, b.preview_revision, entity_id=self.song.pk)
        commit(a.pk, a.preview_revision, key())
        with self.assertRaises(DomainError) as err:
            commit(b.pk, b.preview_revision, key())
        self.assertEqual(err.exception.code, "stale_preview")


class InvalidInput(TestCase):
    def setUp(self):
        self.artist = bootstrap()

    def preview_issues(self, raw):
        batch = preview_upload(raw, "bad.csv")
        return batch, set(batch.issues.values_list("code", flat=True))

    def test_ac03_rejections(self):
        good = ("2026-09-01", 0, 0, 0, 0, 0, 0, 0, 0)
        cases = {
            "unknown_header": b"day,streams\n2026-09-01,1\n",
            "blank_count": audience_csv([("2026-09-01", "", 0, 0, 0, 0, 0, 0, 0)]),
            "negative_count": audience_csv([("2026-09-01", -1, 0, 0, 0, 0, 0, 0, 0)]),
            "not_integer": audience_csv([("2026-09-01", "1.5", 0, 0, 0, 0, 0, 0, 0)]),
            "oversize_count": audience_csv([("2026-09-01", 2**63, 0, 0, 0, 0, 0, 0, 0)]),
            "duplicate_date": audience_csv([good, good]),
            "invalid_date": audience_csv([("2026-02-30", 0, 0, 0, 0, 0, 0, 0, 0)]),
            "encoding": b"\xff\xfe\x00d\x00a",
        }
        for code, raw in cases.items():
            with self.subTest(code=code):
                batch, codes = self.preview_issues(raw)
                self.assertIn(code, codes)
                self.assertEqual(batch.state, "invalid")
                with self.assertRaises(DomainError):
                    commit(batch.pk, batch.preview_revision, key())
        self.assertEqual(Observation.objects.count(), 0, "No invalid or partial facts")

    def test_ac03_size_and_empty(self):
        with self.assertRaises(DomainError) as err:
            preview_upload(b"", "e.csv")
        self.assertEqual(err.exception.code, "empty_file")
        with override_settings(MAX_UPLOAD_BYTES=10):
            with self.assertRaises(DomainError) as err:
                preview_upload(b"date,streams\n2026-01-01,1\n", "big.csv")
        self.assertEqual(err.exception.code, "file_too_large")

    def test_ac03_stale_policy_blocks_commit(self):
        batch = preview_upload(audience_csv([("2026-09-01", 1, 1, 1, 0, 1, 0, 0, 1)]), "p.csv")
        source = ensure_spotify_source()
        SourcePolicyVersion.objects.create(source=source, version=2, purposes=source.policies.first().purposes,
                                           assessment_ref="changed", effective_at=batch.created_at)
        with self.assertRaises(DomainError) as err:
            commit(batch.pk, batch.preview_revision, key())
        self.assertEqual(err.exception.code, "stale_policy")
        self.assertEqual(Observation.objects.count(), 0)

    def test_ac03_stale_preview_revision(self):
        song = recording()
        batch = preview_upload(recording_csv([("2026-09-01", 1)]), "s.csv")
        old = batch.preview_revision
        set_mapping(batch.pk, old, entity_id=song.pk)
        with self.assertRaises(DomainError) as err:
            commit(batch.pk, old, key())
        self.assertEqual(err.exception.code, "stale_preview")

    def test_ac03_mapping_required_for_song(self):
        batch = preview_upload(recording_csv([("2026-09-01", 1)]), "Song-timeline.csv")
        self.assertIsNone(batch.mapped_entity_id, "A filename never establishes identity")
        with self.assertRaises(DomainError) as err:
            commit(batch.pk, batch.preview_revision, key())
        self.assertEqual(err.exception.code, "mapping_required")


class UndoContributions(TestCase):
    def setUp(self):
        bootstrap()
        self.song = recording()

    def value(self, day="2026-09-01"):
        obs = Observation.objects.get(entity=self.song.entity, period_start=date.fromisoformat(day))
        return obs.active_version.value if obs.active_version else None

    def test_ac04_two_supporting_imports_then_revision_undo(self):
        a, _ = import_file(recording_csv([("2026-09-01", 5)]), "a.csv", recording=self.song)
        b, _ = import_file(recording_csv([("2026-09-01", 5), ("2026-09-02", 2)]), "b.csv", recording=self.song)
        undo(a.pk, "wrong file", key())
        self.assertEqual(self.value(), 5, "Value independently supported by b survives")
        c, _ = import_file(recording_csv([("2026-09-01", 6)]), "c.csv", recording=self.song, approve_reason="restated")
        self.assertEqual(self.value(), 6)
        undo(c.pk, "restatement withdrawn", key())
        self.assertEqual(self.value(), 5, "Undoing the revision restores the prior supported version")
        undo(b.pk, "remove", key())
        self.assertIsNone(self.value())
        self.assertEqual(ObservationVersion.objects.filter(observation__entity=self.song.entity).count(), 3, "History retained")
        with self.assertRaises(DomainError):
            undo(b.pk, "again", key())
        self.assertEqual(ImportBatch.objects.get(pk=b.pk).state, "undone")

    def test_undo_requires_reason(self):
        a, _ = import_file(recording_csv([("2026-09-01", 5)]), "a.csv", recording=self.song)
        with self.assertRaises(DomainError):
            undo(a.pk, " ", key())


class IdentityAndScope(TestCase):
    def setUp(self):
        self.artist = bootstrap()

    def test_ac05_audience_maps_only_to_own_artist(self):
        song = recording()
        batch = preview_upload(audience_csv([("2026-09-01", 1, 1, 1, 0, 1, 0, 0, 1)]), "a.csv")
        self.assertEqual(batch.mapped_entity_id, self.artist.pk)
        with self.assertRaises(DomainError) as err:
            set_mapping(batch.pk, batch.preview_revision, entity_id=song.pk)
        self.assertEqual(err.exception.code, "scope_mismatch")

    def test_ac05_song_file_cannot_map_to_artist_or_event(self):
        event = create_object("event", "Show", key_date=date(2026, 11, 12), timezone="Australia/Perth")
        batch = preview_upload(recording_csv([("2026-09-01", 1)]), "s.csv")
        for target in (self.artist.pk, event.pk):
            with self.assertRaises(DomainError) as err:
                set_mapping(batch.pk, batch.preview_revision, entity_id=target)
            self.assertEqual(err.exception.code, "scope_mismatch")

    def test_ac05_recording_identity_pending_until_link_and_confirmed_date(self):
        song = recording()
        self.assertEqual(song.identity_state, "pending")
        song = update_object(song.pk, song.revision, spotify_url="https://open.spotify.com/track/TrackFixture0000000001?si=x")
        self.assertEqual(song.identity_state, "pending", "Date not yet confirmed")
        song = update_object(song.pk, song.revision, key_date=date(2026, 9, 24), date_confirmed=True)
        self.assertEqual(song.identity_state, "confirmed")
        with self.assertRaises(DomainError):
            update_object(song.pk, song.revision, spotify_url="https://open.spotify.com/artist/TrackFixture0000000001")
        other = recording("Other")
        with self.assertRaises(DomainError) as err:
            update_object(other.pk, other.revision, spotify_url="https://open.spotify.com/track/TrackFixture0000000001")
        self.assertEqual(err.exception.code, "identity_in_use")

    def test_ac05_release_membership_and_isrc(self):
        from catalogue.services import relate, release_recordings

        release = create_object("release", "EP")
        a, b = recording("A"), recording("B")
        relate(release.pk, a.pk)
        relate(release.pk, b.pk)
        relate(release.pk, a.pk)
        self.assertEqual({o.pk for o in release_recordings(release.pk)}, {a.pk, b.pk})
        with self.assertRaises(DomainError):
            relate(a.pk, b.pk)
        with self.assertRaises(DomainError):
            update_object(a.pk, a.revision, isrc="nope")
        a = update_object(a.pk, a.revision, isrc="au-abc-26-00001")
        self.assertEqual(a.entity.external_ids.get(provider="isrc").external_id, "AUABC2600001")

    def test_artist_spotify_url_parsing(self):
        ident = set_artist_spotify(self.artist, "https://open.spotify.com/artist/ArtistFixture000000001?si=abc")
        self.assertEqual(ident.external_id, "ArtistFixture000000001")
        with self.assertRaises(DomainError):
            set_artist_spotify(self.artist, "https://example.com/artist/ArtistFixture000000001")
