# Issue tracker: GitHub

Issues and PRDs for this repository live in GitHub Issues at `intake24/Menu_Tracker`. Use the `gh` CLI for operations and infer the repository from `origin` when possible.

- Create: `gh issue create --title "..." --body "..."`
- Read: `gh issue view <number> --comments`
- List: `gh issue list --state open`
- Comment: `gh issue comment <number> --body "..."`
- Label: `gh issue edit <number> --add-label "..."`
- Close: `gh issue close <number> --comment "..."`

When a workflow says to publish to the issue tracker, create a GitHub Issue. When it says to fetch a ticket, read the issue and its comments.
