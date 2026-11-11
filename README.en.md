한국어: [README.md](README.md)

# claude-code-guards

**The reply that ends with "Shall I proceed?", the plan that flipped after one question, the subagent that quietly spawns more subagents. Hooks and rules that stop Claude Code from doing these things.**

Runs on plain Node.js. One repo, growing over time. This is the first batch.

## Install

Two lines inside Claude Code.

```
/plugin marketplace add doul735/claude-code-guards
/plugin install code-guards@jeondaeli
```

From a shell: `claude plugin marketplace add doul735/claude-code-guards`, then `claude plugin install code-guards@jeondaeli`. After installing, start a new session and run `/hooks` to confirm the hooks are registered. Anything added later arrives through the same plugin.

## Sound familiar?

| Name | Sound familiar? | What it does | Type |
|---|---|---|---|
| enforce-start-not-offer | The work is done, yet the turn ends with "Want me to proceed?" | Blocks replies that only offer to act, and sends Claude back to just do it | hook |
| enforce-no-plan-flip | You asked one question and the agreed plan got swapped out | Blocks flipping a plan without an instruction to change it, and makes Claude explain its reasoning first | hook |
| block-subagent-nesting | A subagent calls another subagent and the result vanishes | Blocks Agent calls made from inside a subagent | hook |
| assumptions-and-corrections | You corrected Claude, it patched its earlier answer, and things got worse | Separates what you confirmed from what the AI assumed; after a correction, rebuilds from the confirmed list only | rule |

The research paper behind the rule is cited at the top of the rule file.

## Rule files are copied separately

A plugin does not load `CLAUDE.md` or rule files into context. You place the rule yourself.

1. Copy `rules/assumptions-and-corrections.md` to `~/.claude/rules/` (or `.claude/rules/` in a project)
2. Have your `CLAUDE.md` read that file

## Manual install

To skip the plugin, copy `hooks/*.cjs` to `~/.claude/hooks/` and register them in `~/.claude/settings.json`. If you already have a `hooks` section, merge into its arrays.

```json
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          { "type": "command", "command": "node ~/.claude/hooks/enforce-start-not-offer.cjs" },
          { "type": "command", "command": "node ~/.claude/hooks/enforce-no-plan-flip.cjs" }
        ]
      }
    ],
    "PreToolUse": [
      {
        "matcher": "Agent|Monitor|Bash",
        "hooks": [
          { "type": "command", "command": "node ~/.claude/hooks/block-subagent-nesting.cjs" }
        ]
      }
    ]
  }
}
```

How to switch each hook off (environment variables) and its known limits are in the comment at the top of each file. The sentence detection covers Korean and English.

## Still growing: what is coming

- A skill that asks several models the same question and collects independent counterarguments
- A skill that scrubs keys and personal data locally before anything is sent to an outside AI
- A debate skill where you and the AI keep pushing back until one of you is convinced
- A procedure for processing files with personal data without the AI ever seeing them
- A skill that batches review findings into one audit instead of one at a time
- Two skills that listen to your requirements and produce a first draft in one pass

If a habit of Claude's trips you up, or one is missing, open an issue.

## License

MIT. See LICENSE.
