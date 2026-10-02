# Target contracts

`recommendation.schema.json` defines structured proposal shape. Server checks additionally enforce real IDs/versions, permitted purpose, constraints, source strength, date/zone, asset/resource/metric scope and approval concurrency. Schema validity alone does not establish evidence truth. `recommendation.synthetic-example.json` is explicitly synthetic and unapproved.

`reference-schema.sql` is an executable relational design reference, not finished production migrations. It includes the essential shared-identity/version/link/observation/proposal/job/audit relationships. Translate it to audited ORM migrations and add complete provider-specific dimensions, revision selection, indexes and domain validation as described in spec/DATA-CONTRACTS.md. JSON extension fields are schema-validated by services; core relationships remain relational. Reference tests exercise foreign keys, unique contributions, multiple campaign links and atomic rollback, not full product correctness.

Instance/capability/support policy JSONs are examples, not actual account state, an audited model selection or validated thresholds. No secret is included. Numeric support/cooldown/evaluation thresholds should be versioned and fixed before the relevant holdout, rather than inferred from demo values.
