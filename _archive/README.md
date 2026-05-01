# _archive/

Items moved here during the canonical-CV-template standardization
(branch `chore/standardize-cv-template`).

These files were preserved (not deleted) so the original solution
can be restored if anything was misclassified as cruft.

| Path in _archive/ | Origin path | Reason |
| ----------------- | ----------- | ------ |
| scripts/annotate_real_images.py | scripts/ | Exploratory; not in Makefile/CI |
| scripts/estimate_real_diameters.py | scripts/ | Coupled with annotate_real_images |
| scripts/annotate_v2.py | scripts/ | Exploratory; replaced by src/tad/processing/annotate.py |
| scripts/test_real_images.py | scripts/ | Manual ad-hoc testing; superseded by unit tests |
| scripts/check_db.py | scripts/ | Debug utility; not in automated flows |
| fixtures_images_archived/cam18jdleofhtlhj6_comparison.jpg | tests/fixtures/images/ | Output of archived annotate_real_images.py |
| fixtures_images_archived/cam18jdleofhtlhj6_comparison_v2.jpg | tests/fixtures/images/ | Output of archived annotate_v2.py |
| fixtures_images_archived/cam18jdleofhtlhj6_L_annotated_v2.jpg | tests/fixtures/images/ | Output of archived annotate_v2.py |
| fixtures_images_archived/cam18jdleofhtlhj6_R_annotated_v2.jpg | tests/fixtures/images/ | Output of archived annotate_v2.py |
| fixtures_images_archived/cam18jdleofhtlhj6_L_measured.jpg | tests/fixtures/images/ | Output of archived estimate_real_diameters.py |
| fixtures_images_archived/cam18jdleofhtlhj6_R_measured.jpg | tests/fixtures/images/ | Output of archived estimate_real_diameters.py |
| tests_fixtures_calibration_empty/calibration | tests/fixtures/calibration | Empty placeholder; real calibration lives in configs/calibration/ |

NOTE: PLAN.md is moved separately to `docs/extras/PLAN.md` in Phase C
(it stays inside `docs/` because it is a doc, not cruft).
