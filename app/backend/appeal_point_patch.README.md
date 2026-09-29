# Appeal point patch safety

This build-time patch adds a dedicated 30-character `appeal_point` field to puppy listings.

Safety constraints:
- Runs after existing build patches and before the final release gate.
- Every source replacement asserts the expected match count and aborts the build on mismatch.
- Does not modify `puppy-detail.html`, photo handling, favorites, login, or inquiry flows.
- Backend validation enforces 30 Unicode characters.
- Public search renders the appeal point directly under the coat-color row.
- Existing DOG44 open Standard Poodle listings born 2026-07-01 are initialized only when the appeal point is empty.
