# Manual scraper repair

See `COLLECTION_WORKFLOW.md` for the collection command, artifact definitions,
and initial diagnosis sequence.

1. Open the repair issue and find the matching local bundle under `evidence/<run-id>/<scraper>/`.
2. Read `result.json`, `output_validation.json`, `stdout.txt`, and `stderr.txt`; do not copy raw logs into GitHub.
3. Create a feature branch and reproduce the failing scraper with the smallest possible run.
4. Make the smallest compatible repair. Preserve both notebook/Colab and scheduled-run use.
5. Run the exact scraper through `run_scripts_parallel()` and confirm every manifest output contract passes.
6. Open a pull request containing `Closes #<issue-number>`. The runner never closes issues itself.

Do not add credentials, collected data, evidence bundles, automatic retries, or autonomous repair-agent invocation.
