# UI, interaction and responsive acceptance contract

## Reference and visual system

The current benchmark is `reference/current-prototype/prototype.html` and its `dist/` source, published at https://band-evidence-ux.access593931.chatgpt.site. Published prototype is a convenience; the packaged source is pinned to commit `e26ba792e5cf3c192c90fae4ba00cf3c3b1d980d`. Synthetic values/scripted answers are demonstration content, not initial production data.

Keep the clean monochrome foundation, light chrome, clear labels, one page heading, generous but responsive spacing and restrained green/amber/red for meaningful states. Status also has text/icon so colour is not the only signal. No decorative logo or repeated workspace/page headings. Inter can be locally bundled after licence/provenance review, with system sans fallback; no external font dependency is required for normal operation.

## Creation/review layout

Three tidy steps: Purpose/outcomes, Resources, Review. Keep primary input/action visible, secondary explanation collapsed and long generated content in expandable briefs. Review uses a single main column of cards, compact date/channel/format/support metadata and a concise summary/action region. A desktop side summary may be used only if it wraps/reflows predictably; at narrow widths it stacks and must not overlap cards.

No fixed-height text cells or a right-hand essay. Long words/URLs wrap, grid children shrink (`min-width: 0`), paragraphs never collide with controls. Loading/cancel/retry/evidence-gap states are explicit; committed campaign creation is distinct from draft generation. Back preserves inputs; stale approval returns a resolvable warning.

## Dialog primitive

Use one shared dialog primitive for every campaign/activity/reason/source/creation flow. Bound it to the dynamic viewport with safe margins. Flex-column wrapper, shrinking scrollable body, accessible header/actions; header/footer can wrap/scroll at extreme heights and whole-dialog fallback remains usable. Do not merely set `overflow-y` on a body whose flex parent cannot shrink.

Focus enters an appropriate heading/field, is contained while modal, and returns to the trigger or meaningful fallback. Body has a reachable scrolling region for keyboard navigation. Primary actions remain reachable at short/narrow viewports, landscape and 200% text enlargement. Inputs/errors remain visible after validation. Multiple hidden native dialogs must not trap focus.

Nested content uses one modal route stack: Activity → Why? → Observation/source. Back navigation appears above the heading as a chevron + destination (“Activity”, “Reasoning”), styled as navigation rather than a filled action. Back restores form draft, expansion, scroll and focus. Close/Escape dismisses the whole flow; a dirty draft is protected by a concise discard choice. After mutation, re-render current domain state instead of restoring obsolete HTML. Browser history/deep links return to the correct parent/tab.

## Evidence navigation

Always one tablist in the same order: **Findings / Observed data / Review context**. Canonical URLs: `/evidence/findings`, `/evidence/data`, `/evidence/review`. Keep selection/filter/return state. “Underlying data” is a drill-down title/link within a finding, never a different competing top-level tab taxonomy. A nested view shows a conventional return path and source context.

Review context is an exception queue: original caption/source, suggested labels/links/spans, Confirm/Correct/Leave unknown. Resolve only necessary fields; no bulk certainty forced. A saved review explains stale dependent findings/work in concise status, not a long architecture lesson.

## Campaign/calendar

Calendar and date-ordered list are two views of the same activities; list remains practical on small screens. Broad phase badges are secondary to concrete dates/time. Provide month/week or appropriate range navigation and local timezone indication. Dragging is enhancement; keyboard/date edit has equivalent capability. All-day tasks have explicit due date semantics.

Display state labels Upcoming, Due today, Overdue, Completed, Skipped, Cancelled or Unscheduled. Derived state uses server-now + IANA zone and refreshes on focus/minute boundaries without destroying drafts. Green marks completed, amber/red due/overdue, neutral inactive. No automatic reschedule for missed work.

Strategy gives the supported course of action and evidence gaps, Outcomes gives compatible measured progress/coverage, Learning gives reviewed results/experiments. Avoid duplicating full strategy prose throughout cards.

## Activity and progressive explanation

Primary: purpose/title, planned date/time + compact Timing link, channel/format, practical concept/brief/CTA/assets, matched references and execution controls. Use groups, subtle surfaces/rules and labelled states to distinguish making, reasoning and execution. Full rationale/evidence/audit/protocol stays secondary.

Why? shows concise recommendation reason, supporting finding and limitations, then optional observation/source detail. Default activity line: **Role**, **basis** (evidence-backed, transfer hypothesis, planning hypothesis, operational). Progressive disclosure: contribution rationale, supported proposition, transfer limits, planning decision codes from stored recommendation meta. Distinguish creative drafts and planning hypotheses from evidence-backed work. Sources show name/link, dates, extracted influence and scope rather than citations on every calendar cell.

Manual work remains allowed and visibly user-authored. A manually selected timestamp need not claim evidence support. Changes preserve original provenance and mark incompatible timing/protocol assumptions for review.

## Daily overview and other sections

Today spans all active campaigns/outcomes/account movement. Short trend cards show comparison window and data-through/freshness. No unlabeled “one next step” or hidden plan selector. Useful alerts name their owner and navigate directly. Unknown movement displays the recovery action.

Peers has identity, inclusion/relevance, comparable public behaviour and useful examples, not a bare list. Sources retains the existing calm import/connection structure with per-metric gaps. Inspiration is browsable and contextual; skip empty filler like “matched by purpose…” when metadata/context communicates it. Ask stays clean and context-aware with grounded answers, source drill-down and proposed-edit review.

## Required states and accessibility

For every screen/action cover: empty/new install, loading, success, stale/partial data, unsupported source, offline, validation error, stale revision, denied policy and model unavailable. Unknown is a useful state. Sanitize/escape arbitrary captions/creative output; support reduced motion and semantic controls with labels/errors.

Production browser matrix: at least 360×640, 768×1024, 1440×900 and 812×375 landscape; 200% zoom/text enlargement; short/long content, 5,000-character rationale and unbroken URLs; keyboard-only, Escape/Back/focus return and screen-reader tab/dialog semantics. Test actual geometry and button reachability, not just CSS strings. Current 103 Node VM checks do not prove these browser behaviours.
