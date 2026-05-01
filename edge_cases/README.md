# edge_cases/

Catalog of CV edge cases this system must handle correctly. Each entry
points to the test that asserts the expected behavior. Source fixtures
live in `tests/fixtures/images/` (do not duplicate here).

| ID | Case | Expected behavior | Fixture | Test |
| -- | ---- | ----------------- | ------- | ---- |
| EC-01 | Blurry image | Image rejected with quality error | tests/fixtures/images/blurry.jpg | tests/unit/test_image_validator.py |
| EC-02 | Overexposed | Image rejected | tests/fixtures/images/overexposed.jpg | tests/unit/test_image_validator.py |
| EC-03 | Underexposed | Image rejected | tests/fixtures/images/underexposed.jpg | tests/unit/test_image_validator.py |
| EC-04 | Truncated JPEG | Read fails safely; user-visible error | tests/fixtures/images/truncated.jpg | tests/unit/test_safe_read.py |
| EC-05 | Too small dimensions | Image rejected | tests/fixtures/images/too_small.jpg | tests/unit/test_image_validator.py |
| EC-06 | Bad filename | Filename parse fails with clear error | tests/fixtures/images/bad_name.jpg | tests/unit/test_filename_parser.py |
| EC-07 | Real-pair asymmetry | 0.4 mm asymmetry → PASS | tests/fixtures/images/cam18jdleofhtlhj6_{L,R}.jpg | tests/integration/test_session_flow.py |

To add a new edge case: append a row, then add the asserting test.
