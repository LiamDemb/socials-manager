-- Design reference only. Production uses versioned ORM migrations and service validation.
PRAGMA foreign_keys = ON;
CREATE TABLE entity (
 id TEXT PRIMARY KEY, kind TEXT NOT NULL CHECK(kind IN ('artist','object','account','content')),
 label TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE artist (
 id TEXT PRIMARY KEY REFERENCES entity(id), is_own INTEGER NOT NULL DEFAULT 0 CHECK(is_own IN (0,1)),
 aliases_json TEXT NOT NULL DEFAULT '[]', metadata_json TEXT NOT NULL DEFAULT '{}'
);
CREATE UNIQUE INDEX one_own_artist ON artist(is_own) WHERE is_own=1;
CREATE TABLE promoted_object (
 id TEXT PRIMARY KEY REFERENCES entity(id), artist_id TEXT NOT NULL REFERENCES artist(id),
 kind TEXT NOT NULL CHECK(kind IN ('recording','release','event','video','merch')),
 key_date TEXT, timezone TEXT, date_precision TEXT, identity_state TEXT NOT NULL DEFAULT 'pending',
 revision INTEGER NOT NULL DEFAULT 1 CHECK(revision>0), metadata_json TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE object_relation (
 parent_id TEXT NOT NULL REFERENCES promoted_object(id), child_id TEXT NOT NULL REFERENCES promoted_object(id),
 relation TEXT NOT NULL, verified_at TEXT, PRIMARY KEY(parent_id,child_id,relation), CHECK(parent_id<>child_id)
);
CREATE TABLE external_identity (
 id TEXT PRIMARY KEY, entity_id TEXT NOT NULL REFERENCES entity(id), provider TEXT NOT NULL,
 external_id TEXT NOT NULL, state TEXT NOT NULL, evidence_json TEXT NOT NULL DEFAULT '{}',
 valid_from TEXT NOT NULL, valid_to TEXT
);
CREATE UNIQUE INDEX unique_active_external_identity ON external_identity(provider,external_id) WHERE valid_to IS NULL;
CREATE TABLE source (
 id TEXT PRIMARY KEY, provider TEXT NOT NULL, account_entity_id TEXT REFERENCES entity(id),
 label TEXT NOT NULL, url TEXT, secret_ref TEXT, capability_json TEXT NOT NULL DEFAULT '{}',
 state TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE source_policy_version (
 id TEXT PRIMARY KEY, source_id TEXT NOT NULL REFERENCES source(id), version INTEGER NOT NULL,
 purposes_json TEXT NOT NULL, assessment_ref TEXT NOT NULL, effective_at TEXT NOT NULL,
 expires_at TEXT, retention_json TEXT NOT NULL DEFAULT '{}', UNIQUE(source_id,version)
);
CREATE TABLE raw_file (
 id TEXT PRIMARY KEY, sha256 TEXT NOT NULL UNIQUE, relative_path TEXT NOT NULL UNIQUE,
 original_name TEXT NOT NULL, size_bytes INTEGER NOT NULL CHECK(size_bytes>=0), received_at TEXT NOT NULL
);
CREATE TABLE import_batch (
 id TEXT PRIMARY KEY, source_id TEXT NOT NULL REFERENCES source(id), policy_version_id TEXT NOT NULL REFERENCES source_policy_version(id),
 raw_file_id TEXT REFERENCES raw_file(id), mapped_entity_id TEXT NOT NULL REFERENCES entity(id),
 parser_version TEXT NOT NULL, state TEXT NOT NULL CHECK(state IN ('staged','committed','rejected','undone')),
 preview_revision INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, committed_at TEXT,
 idempotency_key TEXT NOT NULL UNIQUE, mapping_json TEXT NOT NULL
);
CREATE TABLE metric_definition (
 id TEXT PRIMARY KEY, provider TEXT NOT NULL, code TEXT NOT NULL, version INTEGER NOT NULL,
 unit TEXT NOT NULL, grain TEXT NOT NULL, aggregation TEXT NOT NULL,
 dimensions_json TEXT NOT NULL DEFAULT '{}', UNIQUE(provider,code,version)
);
CREATE TABLE observation (
 id TEXT PRIMARY KEY, source_id TEXT NOT NULL REFERENCES source(id), entity_id TEXT NOT NULL REFERENCES entity(id),
 metric_id TEXT NOT NULL REFERENCES metric_definition(id), period_start TEXT NOT NULL, period_end TEXT NOT NULL,
 dimension_key TEXT NOT NULL DEFAULT '', CHECK(period_end>period_start),
 UNIQUE(source_id,entity_id,metric_id,period_start,period_end,dimension_key)
);
CREATE TABLE observation_version (
 id TEXT PRIMARY KEY, observation_id TEXT NOT NULL REFERENCES observation(id), version INTEGER NOT NULL,
 value_text TEXT, missing_reason TEXT, observed_at TEXT, available_at TEXT NOT NULL,
 policy_version_id TEXT NOT NULL REFERENCES source_policy_version(id), source_row_ref TEXT NOT NULL,
 supersedes_id TEXT REFERENCES observation_version(id), state TEXT NOT NULL DEFAULT 'valid',
 UNIQUE(observation_id,version), CHECK((value_text IS NOT NULL AND missing_reason IS NULL) OR (value_text IS NULL AND missing_reason IS NOT NULL))
);
CREATE TABLE observation_contribution (
 observation_version_id TEXT NOT NULL REFERENCES observation_version(id), import_batch_id TEXT NOT NULL REFERENCES import_batch(id),
 active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)), PRIMARY KEY(observation_version_id,import_batch_id)
);
CREATE TABLE interpretation_version (
 id TEXT PRIMARY KEY, content_entity_id TEXT NOT NULL REFERENCES entity(id), version INTEGER NOT NULL,
 labels_json TEXT NOT NULL, evidence_spans_json TEXT NOT NULL, links_json TEXT NOT NULL DEFAULT '[]',
 method_json TEXT NOT NULL, human_state TEXT NOT NULL, available_at TEXT NOT NULL,
 supersedes_id TEXT REFERENCES interpretation_version(id), UNIQUE(content_entity_id,version)
);
CREATE TABLE cohort_version (
 id TEXT PRIMARY KEY, purpose TEXT NOT NULL, selected_at TEXT NOT NULL, rules_json TEXT NOT NULL, exclusions_json TEXT NOT NULL
);
CREATE TABLE cohort_member (
 cohort_version_id TEXT NOT NULL REFERENCES cohort_version(id), artist_id TEXT NOT NULL REFERENCES artist(id),
 inclusion_state TEXT NOT NULL, relevance_json TEXT NOT NULL, PRIMARY KEY(cohort_version_id,artist_id)
);
CREATE TABLE campaign (
 id TEXT PRIMARY KEY, artist_id TEXT NOT NULL REFERENCES artist(id), object_id TEXT REFERENCES promoted_object(id),
 type TEXT NOT NULL, name TEXT NOT NULL, start_date TEXT NOT NULL, end_date TEXT NOT NULL,
 timezone TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('draft','active','paused','completed','cancelled')),
 revision INTEGER NOT NULL DEFAULT 1 CHECK(revision>0), resources_json TEXT NOT NULL,
 CHECK(end_date>=start_date)
);
CREATE TABLE outcome (
 id TEXT PRIMARY KEY, name TEXT NOT NULL
);
CREATE TABLE outcome_version (
 id TEXT PRIMARY KEY, outcome_id TEXT NOT NULL REFERENCES outcome(id), version INTEGER NOT NULL,
 metric_id TEXT NOT NULL REFERENCES metric_definition(id), scope_entity_id TEXT NOT NULL REFERENCES entity(id),
 mode TEXT NOT NULL CHECK(mode IN ('gain','total','rate')), target_text TEXT NOT NULL,
 period_start TEXT NOT NULL, period_end TEXT NOT NULL, timezone TEXT NOT NULL,
 baseline_json TEXT NOT NULL, coverage_json TEXT NOT NULL, calculation_json TEXT NOT NULL,
 created_at TEXT NOT NULL, UNIQUE(outcome_id,version), CHECK(period_end>period_start)
);
CREATE TABLE campaign_outcome (
 campaign_id TEXT NOT NULL REFERENCES campaign(id), outcome_version_id TEXT NOT NULL REFERENCES outcome_version(id),
 role TEXT NOT NULL CHECK(role IN ('primary','supporting')), PRIMARY KEY(campaign_id,outcome_version_id)
);
CREATE UNIQUE INDEX one_primary_outcome ON campaign_outcome(campaign_id) WHERE role='primary';
CREATE TABLE activity (
 id TEXT PRIMARY KEY, campaign_id TEXT NOT NULL REFERENCES campaign(id), title TEXT NOT NULL,
 purpose TEXT NOT NULL, channel TEXT, format TEXT, brief_json TEXT NOT NULL,
 planned_at_utc TEXT, local_datetime TEXT, timezone TEXT NOT NULL, all_day_date TEXT,
 actual_at_utc TEXT, status TEXT NOT NULL CHECK(status IN ('planned','completed','skipped','cancelled')),
 effort_minutes INTEGER NOT NULL DEFAULT 0 CHECK(effort_minutes>=0), revision INTEGER NOT NULL DEFAULT 1,
 CHECK(NOT(planned_at_utc IS NOT NULL AND all_day_date IS NOT NULL)),
 CHECK(status<>'completed' OR actual_at_utc IS NOT NULL)
);
CREATE TABLE activity_outcome (
 activity_id TEXT NOT NULL REFERENCES activity(id), outcome_version_id TEXT NOT NULL REFERENCES outcome_version(id),
 PRIMARY KEY(activity_id,outcome_version_id)
);
CREATE TABLE execution_event (
 id TEXT PRIMARY KEY, activity_id TEXT NOT NULL REFERENCES activity(id), prior_state TEXT NOT NULL,
 new_state TEXT NOT NULL, actual_at TEXT, url TEXT, reason TEXT, actor TEXT NOT NULL, recorded_at TEXT NOT NULL,
 idempotency_key TEXT NOT NULL UNIQUE
);
CREATE TABLE evidence_bundle (
 id TEXT PRIMARY KEY, purpose TEXT NOT NULL, scope_json TEXT NOT NULL, cutoff TEXT NOT NULL,
 fingerprint TEXT NOT NULL UNIQUE, transformations_json TEXT NOT NULL, state TEXT NOT NULL
);
CREATE TABLE bundle_observation (
 bundle_id TEXT NOT NULL REFERENCES evidence_bundle(id), observation_version_id TEXT NOT NULL REFERENCES observation_version(id),
 PRIMARY KEY(bundle_id,observation_version_id)
);
CREATE TABLE bundle_interpretation (
 bundle_id TEXT NOT NULL REFERENCES evidence_bundle(id), interpretation_version_id TEXT NOT NULL REFERENCES interpretation_version(id),
 PRIMARY KEY(bundle_id,interpretation_version_id)
);
CREATE TABLE finding_version (
 id TEXT PRIMARY KEY, bundle_id TEXT NOT NULL REFERENCES evidence_bundle(id), cohort_version_id TEXT REFERENCES cohort_version(id),
 method_version TEXT NOT NULL, result_json TEXT NOT NULL, support TEXT NOT NULL, limits_json TEXT NOT NULL,
 created_at TEXT NOT NULL, state TEXT NOT NULL
);
CREATE TABLE inspiration_reference (
 id TEXT PRIMARY KEY, content_entity_id TEXT REFERENCES entity(id), source_id TEXT NOT NULL REFERENCES source(id),
 url TEXT NOT NULL, reviewed_context_json TEXT NOT NULL, observable_limits_json TEXT NOT NULL,
 preference_state TEXT NOT NULL DEFAULT 'unreviewed'
);
CREATE TABLE activity_reference (
 activity_id TEXT NOT NULL REFERENCES activity(id), reference_id TEXT NOT NULL REFERENCES inspiration_reference(id),
 PRIMARY KEY(activity_id,reference_id)
);
CREATE TABLE proposal_batch (
 id TEXT PRIMARY KEY, campaign_id TEXT NOT NULL REFERENCES campaign(id), base_revision INTEGER NOT NULL,
 fingerprint TEXT NOT NULL UNIQUE, state TEXT NOT NULL, created_at TEXT NOT NULL, diff_json TEXT NOT NULL
);
CREATE TABLE recommendation (
 id TEXT PRIMARY KEY, batch_id TEXT NOT NULL REFERENCES proposal_batch(id), bundle_id TEXT REFERENCES evidence_bundle(id),
 kind TEXT NOT NULL CHECK(kind IN ('evidence_backed_tactic','operational_dependency')),
 proposal_json TEXT NOT NULL, generation_json TEXT NOT NULL, validation_state TEXT NOT NULL,
 CHECK(kind<>'evidence_backed_tactic' OR bundle_id IS NOT NULL)
);
CREATE TABLE recommendation_finding (
 recommendation_id TEXT NOT NULL REFERENCES recommendation(id), finding_version_id TEXT NOT NULL REFERENCES finding_version(id),
 PRIMARY KEY(recommendation_id,finding_version_id)
);
CREATE TABLE scheduling_decision (
 id TEXT PRIMARY KEY, activity_id TEXT REFERENCES activity(id), recommendation_id TEXT REFERENCES recommendation(id),
 chosen_at_utc TEXT, timezone TEXT NOT NULL, basis TEXT NOT NULL, candidates_json TEXT NOT NULL,
 constraints_json TEXT NOT NULL, evidence_json TEXT NOT NULL, rule_version TEXT NOT NULL, override_json TEXT,
 CHECK(activity_id IS NOT NULL OR recommendation_id IS NOT NULL)
);
CREATE TABLE decision (
 id TEXT PRIMARY KEY, batch_id TEXT REFERENCES proposal_batch(id), recommendation_id TEXT REFERENCES recommendation(id),
 action TEXT NOT NULL CHECK(action IN ('accept','modify','reject')), reason TEXT, actor TEXT NOT NULL,
 recorded_at TEXT NOT NULL, idempotency_key TEXT NOT NULL UNIQUE
);
CREATE TABLE experiment_version (
 id TEXT PRIMARY KEY, campaign_id TEXT NOT NULL REFERENCES campaign(id), outcome_version_id TEXT NOT NULL REFERENCES outcome_version(id),
 hypothesis TEXT NOT NULL, variable TEXT NOT NULL, protocol_json TEXT NOT NULL, state TEXT NOT NULL,
 approved_at TEXT, supersedes_id TEXT REFERENCES experiment_version(id)
);
CREATE TABLE experiment_activity (
 experiment_version_id TEXT NOT NULL REFERENCES experiment_version(id), activity_id TEXT NOT NULL REFERENCES activity(id),
 role TEXT NOT NULL, PRIMARY KEY(experiment_version_id,activity_id)
);
CREATE TABLE learning_record (
 id TEXT PRIMARY KEY, campaign_id TEXT NOT NULL REFERENCES campaign(id), experiment_version_id TEXT REFERENCES experiment_version(id),
 bundle_id TEXT REFERENCES evidence_bundle(id), conclusion TEXT NOT NULL, decision TEXT NOT NULL,
 limits_json TEXT NOT NULL, reviewed_at TEXT NOT NULL
);
CREATE TABLE model_run (
 id TEXT PRIMARY KEY, purpose TEXT NOT NULL, model_ref TEXT NOT NULL, dataset_manifest_ref TEXT NOT NULL,
 cutoff TEXT NOT NULL, configuration_json TEXT NOT NULL, validation_report_ref TEXT, state TEXT NOT NULL
);
CREATE TABLE forecast_record (
 id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES model_run(id), outcome_version_id TEXT NOT NULL REFERENCES outcome_version(id),
 issued_at TEXT NOT NULL, period_start TEXT NOT NULL, period_end TEXT NOT NULL,
 prediction_json TEXT NOT NULL, actual_bundle_id TEXT REFERENCES evidence_bundle(id), evaluation_json TEXT
);
CREATE TABLE audit_event (
 id TEXT PRIMARY KEY, entity_kind TEXT NOT NULL, entity_id TEXT NOT NULL, revision INTEGER,
 action TEXT NOT NULL, actor TEXT NOT NULL, recorded_at TEXT NOT NULL, details_json TEXT NOT NULL
);
CREATE TABLE outbox_event (
 id TEXT PRIMARY KEY, kind TEXT NOT NULL, fingerprint TEXT NOT NULL UNIQUE, payload_json TEXT NOT NULL,
 created_at TEXT NOT NULL, handled_at TEXT
);
CREATE TABLE job (
 id TEXT PRIMARY KEY, task TEXT NOT NULL, scope_key TEXT NOT NULL, input_key TEXT NOT NULL,
 state TEXT NOT NULL CHECK(state IN ('queued','leased','done','failed','cancelled')),
 due_at TEXT NOT NULL, lease_owner TEXT, lease_until TEXT, attempts INTEGER NOT NULL DEFAULT 0,
 safe_error TEXT, cursor_json TEXT, UNIQUE(task,scope_key,input_key)
);
CREATE INDEX observation_scope_window ON observation(entity_id,metric_id,period_start,period_end);
CREATE INDEX observation_available ON observation_version(available_at);
CREATE INDEX activity_calendar ON activity(campaign_id,planned_at_utc,status);
CREATE INDEX job_due ON job(state,due_at);
