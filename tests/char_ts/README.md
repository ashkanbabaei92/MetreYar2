# MetreYar2 — TypeScript Characterization Tests
#
# Usage:
#   Generate golden master:  GENERATE=1 npx vitest run tests/char_ts/ --reporter=verbose
#   Run comparison:          npx vitest run tests/char_ts/ --reporter=verbose
#
# Requirements: Node 20+, vitest (install separately), project deps from package.json
# Note: vitest.config.ts recommended to bypass vite-plugin-singlefile interference (BF-5)
# Note: crypto.randomUUID() is mocked in beforeEach for deterministic IDs
# Note: No production files are modified by these tests.
