# portfolio-routines

Attachment repo for Claude Code cloud sessions and routines that serve **Portfolio OS** and **Tech Money Flow**. Cloud sessions require a repository to clone; this is that repository. It holds prompts, skills, and notes. It does not hold product code, secrets, or book contents.

Private. Keep it that way.

## What this repo is for

- The GitHub repo attached to every Portfolio OS / TMF routine and test session.
- A place to commit routine prompts and `.claude/skills/` so cloud sessions can read them instead of relying on pasted text.
- Run notes that don't belong in Notion.

## What never goes here

- **Secrets.** No API keys, tokens, `.env` files, or credentials of any kind. X and other API tokens live as *API credentials* on the Claude Code cloud environment, where the agent proxy attaches them and the session never sees them. Claude Code auto-loads `.env` files it finds; there must be none to find.
- **Book contents.** No holdings, weights, share counts, cost bases, theses, gate thresholds, or Decision Journal content. Prompts may name the ten owned tickers for string matching; nothing beyond the names.
- **Product code.** Zenoomi lives in its own repos. Nothing from those repos is copied here, and no routine attached here touches them.
- **Anything a routine should not be able to push.** Cloud sessions can push a branch to the attached repo. Assume anything here can be modified by a run.

## Routines that attach here

| Routine | Schedule (ET) | Reads | Writes |
|---|---|---|---|
| X Sweep | nightly 11:00 PM | X List `1764453609561825483` (bookmarks in phase 2) | Notion: Signal Inbox — X Intake · TMF Source Inbox (bridge only) · Routine Run Log — Portfolio OS |
| Friday Sourcing Sweep | Fri 8:00 PM | Web, 7-day window | Notion: Story Bank · Routine Run Log — TMF |
| Weekly Signal Review | Sun 7:00 AM | Signal Inbox · Story Bank · open gates from Notion | One page under Portfolio OS · Routine Run Log — Portfolio OS |
| Scorecard | Sat | Weights Pull Log | Scorecard Run Log — by Week |

Cron is fixed UTC. Every schedule above drifts one hour on Nov 1 (DST) and needs its cron adjusted in late October.

## Notion data sources

| Name | Data source ID |
|---|---|
| Signal Inbox — X Intake | `e23c4606-f1b9-45e3-8245-d8d6514a501d` |
| Story Bank (TMF) | `6badc0ad-0851-447e-9971-ac97c245d443` |
| Source Inbox (TMF) | `7a5a243f-a37f-405c-8256-943cf2f164d0` |
| Routine Run Log — Portfolio OS | `c092b0f7-1c03-4e74-8ab8-a38bb3b485ef` |
| Routine Run Log — TMF | `5148edab-be2d-429d-83ee-3ae1e9d6ff65` |
| Portfolio OS (parent page) | `34631d4f-7b77-8174-a91c-f61b31bef484` |

## Intended layout

```
README.md
prompts/
  x-sweep.md                  # X Sweep routine prompt (source of truth once committed)
  friday-sourcing-sweep.md    # TMF Friday sweep prompt
  weekly-signal-review.md     # Weekly Signal Review prompt
.claude/
  skills/                     # skills a cloud session may load
notes/
  runs/                       # anything worth keeping that isn't a Run Log row
```

Until the prompt files are committed, the source of truth for each prompt is its page in Notion under *Proposals — Sept 7 2026 — Intake pipeline*. When a prompt is committed here, update the Notion page to say so.

## Operating rules that apply to every routine attached here

- **Clerk, not judge.** Intake routines file facts. No summaries, relevance notes, grades, or adjectives about significance.
- **One-way valve.** Portfolio OS → TMF carries four public fields only: headline as published, underlying source URL, publication name, publication date. TMF → Portfolio OS is read only; board grades and tiers are never cited as portfolio evidence.
- **Every run writes a run row.** Counts, governors unmet, errors verbatim. A green session status is not evidence the run did anything.
- **Verify before filing.** Fetch the URL. Never invent a headline, date, or figure. If it can't be fetched, say so.
- **CEO rules.** Routines propose. Status, Gate Impact, and anything that moves a rule are set by Mitchell.

## Environment

Cloud environment: **Default** (or a dedicated one) with Network access → Full for news fetching. `api.x.com` is reached through the API credential, not the network allowlist. Environment variables hold non-secret values only, e.g. `X_LIST_ID=1764453609561825483`.

Educational only, not investment advice.
