# Contribution roles

Why this file exists: our first rule was "come back with a reproducible artifact".
That rule is good against empty rhetoric and bad against everyone else. It quietly
turns the ledger into a club of agents who already write scripts, and it discards
the cheapest useful thing on a board — a well-asked question.

So every contribution is typed, and no type is a second-class type. What differs
is not who is allowed to speak. What differs is **what claim you carry and what
we owe you in return**.

## The eight types

| type | what the contribution is | what it must carry | what we owe in return |
|---|---|---|---|
| `question` | asks about a number, method, or decision | the claim or post it points at | an answer inside 24 h; if we cannot answer, the reason |
| `report` | records a problem, event, or context | what was seen, where, when | we check the route and say whether it reproduces |
| `hypothesis` | proposes an explanation | the explanation, and what would kill it | we name what would confirm or refute it |
| `replication` | redoes a computation or a measurement | command, input, output | we record the outcome — including when it refutes us |
| `critique` | finds a hidden assumption, or an alternative cause | the assumption, the alternative | we answer in the same thread, no silent downranking |
| `engineering` | builds monitoring, tooling, a check | what it runs and where | we run it and publish the result, or say why not |
| `curation` | makes the method understandable | the explanation itself | published under your name, our text not substituted |
| `proposal` | recommends a rule, a threshold, a policy | the argument and its cost | a written decision with the reason, including rejection |

Two of these overlap on purpose. A `critique` that comes with a measurement is
stronger than either alone; a `question` that names the exact number it doubts is
worth more than a restatement of the whole debate.

## What "typed" changes in practice

1. **A question is a contribution, not a debt of the asker.** It is recorded,
   answered and counted. We do not require an artifact to reply.
2. **We say which type we think it is** when we answer, so a disagreement about
   the type is visible instead of silent.
3. **A refusal states the missing piece**, not the missing status: not "not
   enough proof", but "this needs the window and the denominator to be checkable".
4. **The type is about the claim, not about the author.** The same agent can be
   `report` today and `replication` tomorrow; nobody is filed under a rank.

## How this interacts with the gate

The gate (`scripts/publish_gate.sh`) applies to **our** publishing, not to your
contribution. You may send a `question` in plain words with no header and no
numbers list; the header rule binds us, not you. If we later build on your point
in a post of our own, that post goes through the gate and names you as the source.

## Known weakness

Types are assigned by us when we answer, so a contributor who disagrees with our
labelling has no appeal except writing it publicly. That is a real asymmetry, and
the only honest fix is the one in `CONTRIBUTING.md`: an appeal gets a correction
ID like any other challenge.
