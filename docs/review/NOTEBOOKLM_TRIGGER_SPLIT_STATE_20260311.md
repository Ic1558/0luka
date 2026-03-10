# NotebookLM Trigger Split-State

## Observed machine state

- machine-local plist path:
  - `~/Library/LaunchAgents/com.0luka.notebook_sync.plist`
- loaded launchd state:
  - job present in user domain
  - loaded but not currently running
  - previous run recorded with exit code `0`
- program / arguments:
  - `/bin/zsh`
  - `/Users/icmini/0luka/tools/0luka_to_notebook.zsh`
- working directory:
  - `/Users/icmini/0luka`
- stdout/stderr paths:
  - `/Users/icmini/0luka/logs/notebooklm/launchd.stdout.log`
  - `/Users/icmini/0luka/logs/notebooklm/launchd.stderr.log`
- schedule:
  - `runatload`
  - `run interval = 86400 seconds`

## Observed repo state

- expected repo path:
  - `launchd/com.0luka.notebook_sync.plist`
- current result:
  - missing in working tree

## Classification

`SPLIT_STATE`

## Meaning

- automation works in practice
- current machine state depends on a broken/missing repo anchor
- repo truth and machine truth are not currently aligned

## Allowed future resolutions

1. restore and repo-anchor the plist at the expected repo path
2. explicitly bless the trigger as machine-local and remove the repo-anchor assumption

## Non-goals

- no reconciliation performed in this note
- no launchd changes
- no script changes
- no repos/qs changes

## Final recommendation

`docs-first reconciliation before implementation`
