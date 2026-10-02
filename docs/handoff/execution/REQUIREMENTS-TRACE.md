# Feedback-to-build trace

This table prevents the refinement rounds being reduced to a visual restyle. The machine-readable acceptance cases specify target checks, not checks already passed by the prototype.

| Owner requirement | Current contract | Acceptance |
| --- | --- | --- |
| Clean monochrome UI, no logo/repeated text, functional status colour | UI-CONTRACT; PRODUCT navigation | AC25, AC31 |
| Today artist overview, contextual alerts, plan operations elsewhere | PRODUCT; USER-FLOWS D | AC06, AC31 |
| First-class campaign dates/calendar, phases secondary | PRODUCT execution; INTELLIGENCE timing | AC08, AC22 |
| Plans/Goals relationship reasoned, not visual-only decision | DECISIONS model comparison; reusable outcome links | AC06, AC07 |
| Campaign creation beyond singles, tidy conditional inputs | PRODUCT; USER-FLOWS A/B/C | AC05, AC06, AC21 |
| Canonical promoted object, known dates reused, pre-saves tracked distinctly | DATA-CONTRACTS; INTEGRATIONS | AC01, AC05, AC20 |
| Evidence-backed recommendations and progressive explanation | INTELLIGENCE pipeline; schema | AC16, AC21, AC26, AC28 |
| Practical activity brief and contextual references | PRODUCT activity; UI-CONTRACT | AC19, AC21, AC25 |
| Contextual and globally browsable inspiration | PRODUCT; USER-FLOWS G | AC19 |
| Experiments clarified and integrated into campaign work | PRODUCT states; USER-FLOWS E | AC24 |
| Review labels workflow explained, corrections improve context | USER-FLOWS F; DATA-CONTRACTS versions | AC17, AC32 |
| Evidence deeper data and reproducible findings | DATA-CONTRACTS; INTELLIGENCE | AC07, AC16, AC28 |
| Useful peer detail feeding decisions, no private metrics assumed | PRODUCT; INTEGRATIONS; USER-FLOWS G | AC17, AC19, AC26 |
| Sources and Ask preserved, operational and grounded | INTEGRATIONS; USER-FLOWS H | AC14, AC15, AC28, AC33 |
| Confined AI creates editable structured work, human decision | INTELLIGENCE; recommendation schema | AC21, AC23, AC32, AC33 |
| Observed/derived/interpreted/recommended/creative levels distinct | INTELLIGENCE five-layer table | AC16, AC21, AC32 |
| Real execution status relative to clock, completed/overdue | PRODUCT; DATA-CONTRACTS timestamps | AC08, AC09, AC22 |
| Realistic channels/formats, purpose-aware and constrained | INTEGRATIONS; capacity policy | AC19, AC21, AC22 |
| Evolving strategy with reviewed changes, never silent edits | INTELLIGENCE adaptation; ARCHITECTURE events | AC10, AC17, AC23 |
| Long generated text cannot break Review or activity panels | UI-CONTRACT layout/dialogs | AC13, AC25 |
| All dialogs scroll and actions stay accessible | UI-CONTRACT shared primitive | AC25 |
| Stable Findings/Observed data/Review context tabs | UI-CONTRACT Evidence | AC12 |
| Conventional nested Back navigation/state restoration | UI-CONTRACT typed frames | AC13 |
| Investigated Meta temporal capabilities, no fabricated dimensions | INTEGRATIONS temporal probe; research status | AC14, AC18 |
| Evidence informs date/time, compact Timing explanation | INTELLIGENCE scheduling | AC18, AC22 |
| Single SQLite/data folder instance, no complex login/workspaces | ARCHITECTURE; OPERATIONS | AC11, AC35 |
| Same code for another band later, empty DB/folders | ARCHITECTURE second instance; deferred provisioning | Documentation only in current scope |
| Agent-executable smooth development with testing/deployment gates | DEVELOPMENT-PLAN/backlog/checkpoint/TEST-STRATEGY | All 35 cases, four review points |
| Real integrations/data/model training must be testable | TEST-STRATEGY distinct live/semantic/numerical layers | AC01, AC14, AC20, AC30, AC32, AC34 |
| Full original work retained with decisions/provenance | archive; PROVENANCE; historical map | Package manifest + reference rerun |

Read contract references under `spec/` and acceptance definitions in `acceptance-cases.json`. All earlier 28 story IDs have a current/deferred mapping in `historical-backlog-map.json`.
