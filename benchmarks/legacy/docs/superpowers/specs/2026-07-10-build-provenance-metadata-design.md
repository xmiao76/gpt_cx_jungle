# Build Provenance Metadata Design

## Objective

Record the approved build provenance in both the repository README and every generated release README:

- Model: `GPT 5.6-Sol`
- Reasoning effort: `Ultra`
- Code agent: `Codex`

## Design

`README.md` will contain a dedicated Build Provenance section so the source repository exposes all three values directly. `tools/package_release.py` will keep the release values as constants and render them into `release/README.txt`; rebuilding the package will therefore preserve the disclosures instead of relying on a manual edit to generated output.

Packaging validation will require the model, reasoning-effort, and code-agent lines. Unit and integration tests will assert those exact disclosures in generated and packaged README content.

## Release Flow

Run the existing packaging command to regenerate `release/README.txt`, rebuild `release/Jungle.zip`, and execute the packaged smoke test. Verify the ZIP's README contains all three exact values and that required runtime artifacts remain present.

## Scope

No engine, gameplay, UI, or executable behavior changes are included. Existing user-supplied release evidence files remain preserved by the packaging workflow.
