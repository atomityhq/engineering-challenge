# Task 6 acceptance mapping

Sources of truth: [Task 6](../../challenge/tasks/task-6.md) and [common challenge](../../challenge/challenge.md). All paths below are relative to this submission. Tests run via `python3.11 -B -m unittest discover -s tests -q`. The current suite has **96 tests** after the final-review stale-news correction. The [Stage 12 evidence](STAGE_12_RESULTS.md) distinguishes the historical 95-test rehearsal from the **2026-10-27 corrected-snapshot rehearsal, which passed all 96 tests**. This maps implemented checks, not hypothetical coverage. Stage 12 isolated-copy rehearsal is complete.

## Task definition of done

| Requirement | Implementation/artifact | Concrete automated evidence |
| --- | --- | --- |
| 1. Load supplied fixture in place | `g2/fixtures.py`; original `../../fixtures/g2-cases.json` | `test_reports.py::test_all_nine_original_outcomes_and_label_isolation`; `test_security.py::test_original_bytes_and_baseline_digest_preserved` |
| 2. Use fixed as_of | `g2/freshness.py`; serialized as_of | `test_freshness.py::test_supplied_age_limit_and_date`; `test_security.py::test_fresh_import_cli_denies_network_and_system_clock` |
| 3. Validate every starter case | Strict contracts/adaptation, nine JSON reports | `test_reports.py::test_all_nine_original_outcomes_and_label_isolation` |
| 4. Inspect hard checks | Report `checks`, statuses/reasons/basis | `test_hard_checks.py::test_exhaustive_flag_status_combinations`; `test_reports.py::test_serialized_schema_nulls_precision_and_determinism` |
| 5. Inspect timing/applicability | Report `freshness`, `date_basis`, `applicability`, `currently_applicable` | `test_freshness.py::test_news_age_boundaries`; `test_regulation_effective_boundaries`; `test_unknown_event_not_replaced_by_context_dates`; `test_exhaustive_content_status_supersession_matrix` |
| 6. Inspect criterion scores | Three `criteria`, floors and explanations | `test_evaluator.py::test_known_authority_values_and_independent_sums`; `test_supported_conflict_mapping_and_blocking` |
| 7. Inspect weights | `config/policy.json`; serialized weights/versions | `test_policy.py::test_valid_policy_preserves_inputs_and_precision`; README policy table |
| 8. Inspect eligible weighted score | `aggregate_score`, eligibility/blockers | `test_evaluator.py::test_known_authority_values_and_independent_sums`; `test_floor_and_threshold_full_precision_boundaries` |
| 9. Inspect final decision/reasons | `decision`, `primary_reason`, merged `findings` | `test_reports.py::test_exhaustive_precedence_and_retained_findings`; `test_supersession_merge_preserves_origins_and_basis` |
| 10. Hard failure cannot pass via score | Mandatory checks before aggregate; null blocked scores | `test_evaluator.py::test_all_flag_status_combinations_cannot_bypass_checks`; `test_reports.py::test_floor_threshold_and_competitor_review` |
| 11. Unknown is not zero | Null criterion/aggregate and review | `test_evaluator.py::test_unknown_required_criteria_block_zero_weights`; `test_supported_conflict_mapping_and_blocking` |
| 12. Reject invalid weights | Finite, nonnegative, absolute sum tolerance 1e-9 | `test_policy.py::test_invalid_weight_values`; `test_invalid_sums_and_overflow`; `test_absolute_tolerance_boundary_without_normalization` |
| 13. Three eligible cases/three weights | `fixtures/additional-cases.json`, `g2/sensitivity.py` | `test_sensitivity.py::test_additional_fixture_arithmetic_and_routes` |
| 14. Inspect ranking/routing changes | `examples/sensitivity-report.json`; case vectors/ties/unchanged IDs | `test_sensitivity.py::test_additional_fixture_arithmetic_and_routes`; `test_exact_ties_and_unranked_blockers` |
| 15. Local automated tests, no credentials | Standard-library tests/CLI; no installer | `test_cli.py::test_module_commands_and_deterministic_files`; `test_security.py::test_fresh_import_cli_denies_network_and_system_clock` |

Names after the first filename in a cell refer to the same test module. Test identifiers are unittest method names, not pytest invocation syntax.

## Additional required checks and failure paths

| Check | Tests/artifacts |
| --- | --- |
| Required keys, null versus missing, strict booleans/enums/dates | `test_validation.py::test_every_required_case_key`, `test_every_required_metadata_key`, `test_null_dates_are_explicit_unknowns`, `test_boolean_coercions_rejected_for_all_flags`, `test_invalid_dates_for_every_date_field`; `test_fixtures.py::test_missing_envelope_and_policy_fields` |
| Duplicate keys, nonfinite values and decoder limits | `test_validation.py::test_duplicate_keys_at_any_depth`, `test_nonfinite_tokens_and_float_overflow`, `test_malformed_json_and_decoder_limits_are_safe` |
| Typed output construction invariants | `test_evaluator.py::test_output_invariants_and_mismatched_basis`; `test_reports.py::test_report_construction_invariants`; `test_sensitivity.py::test_comparison_construction_invariants` |
| Promotion prohibited across source categories | `test_hard_checks.py::test_promotion_independent_of_source_category` |
| Supersession disagreement/conflicts retained | `test_hard_checks.py::test_all_findings_retained_and_deterministic`; `test_reports.py::test_supersession_merge_preserves_origins_and_basis` |
| Known stale news retains precedence over status uncertainty | `test_freshness.py::test_stale_news_retains_invalidity_for_every_status`; `test_reports.py::test_stale_news_precedes_status_uncertainty_but_not_promotion` |
| Future regulation valid but not applicable now | `test_evaluator.py::test_future_regulation_is_scoring_eligible`; `test_freshness.py::test_regulation_effective_boundaries` |
| Verification not invented expiry; date inconsistencies exposed | `test_freshness.py::test_verification_not_an_invented_expiry`, `test_known_invalidity_preserves_uncertainty`, `test_unrelated_evidence_and_date_ordering` |
| IDs/prose/expected labels never drive routing | `test_reports.py::test_identity_and_prose_never_affect_decision`; `test_security.py::test_instruction_prose_and_labels_cannot_change_reports`; `test_fixtures.py::test_separate_expected_outcomes` |
| Floor, threshold and full-precision numerical boundaries | `test_evaluator.py::test_floor_and_threshold_full_precision_boundaries`, `test_weight_sum_tolerance_does_not_clip_aggregate`, `test_competitor_requirement_survives_permissive_policy` |
| Only weights vary during sensitivity | `test_sensitivity.py::test_non_weight_changes_and_duplicate_versions_rejected` |
| CLI missing/malformed files/config and safe errors | `test_cli.py::test_malformed_missing_inputs_and_safe_errors`, `test_help_and_invalid_arguments`; `test_security.py::test_embedded_null_paths_fail_safely` |
| Existing output/input aliases/missing parent/permission denial | `test_cli.py::test_output_conflicts_and_existing_files`, `test_unwritable_output_and_missing_parent` |
| Deterministic valid JSON, no report logging | `test_cli.py::test_module_commands_and_deterministic_files`; `test_security.py::test_hash_seed_and_timezone_cannot_change_examples`, `test_malformed_content_never_logged_or_dumped` |
| Offline and no dynamic source execution | `test_security.py::test_fresh_import_cli_denies_network_and_system_clock`, `test_production_dependency_and_dynamic_execution_firewall` |

## Submission artifacts and design claims

- Python implementation and typed runtime-validated input/output contracts: `g2/`.
- G2 policy/weight configuration and explicit uncalibrated status: `config/policy.json`.
- Definitions and 0/0.5/1 anchor meanings, implemented mappings and conceptual-only partial-support/qualified-scope limitations, weight rationale, threshold/floors, precedence, unknown handling, trusted metadata boundary: `README.md`.
- Supplied starter fixture: original root file, not copied. Three additional synthetic cases/relationships: `fixtures/additional-cases.json` and `fixtures/README.md`.
- Actual executable examples: `examples/starter-report.json` and `examples/sensitivity-report.json`; invocations in `README.md` and `CLI_USAGE.md`.
- Architecture/trade-offs/limitations: `README.md`, `MASTER_PLAN.md`, `STAGE_6_RESULTS.md` (numerical tolerance), `STAGE_10_RESULTS.md` (security verification limits).
- PR explanation: `PR_DESCRIPTION.md`, prepared locally only. A local commit is user-authorized; pushing and opening a PR require separate authorization.

## Evidence boundaries

The security suite guards selected network/clock APIs before fresh imports and varies timezone/hash seed; it is not an OS sandbox or universal proof. Synthetic labels check routing consistency, not calibration. The additional family varies authority while support/timing stay 1, so unchanged ranks are expected, not omitted evidence. Partial-support and qualified-temporal 0.5 anchors are conceptual-only and not representable in the minimum schema; authority 0.5 is implemented. Large-input resource quotas, atomic file rollback and hostile concurrent path mutation are not implemented. Stage 12 records isolated HEAD-baseline-plus-submission rehearsals, including the corrected 96-test snapshot; these do not certify an already committed checkout. Push and PR creation still require separate authorization.

The current corrected implementation passed all 96 tests on Python 3.11.15/Linux in both the workspace and an isolated copy. All 24 Python files parsed, and default/explicit starter evaluation and weight comparison reproduced the saved examples byte-for-byte. The original fixture remains identical to HEAD. See the corrected-snapshot subsection of `STAGE_12_RESULTS.md`; the earlier 95-test evidence remains historical.
