# SKB Knowledge Sync

This repository is connected to `soobujmiah/skb` for owner-context and durable knowledge continuity.

## Agent requirement

Before ending any meaningful work session, review whether the work created or materially changed durable knowledge that belongs in SKB.

If authorized to write to SKB, update the appropriate canonical SKB record directly. Otherwise create a pending return item using the repository's configured knowledge-return mechanism.

## Return only

- verified architecture/design decisions;
- verified capability/state changes;
- reusable discoveries and validated fixes;
- material blockers/constraints/dependencies;
- meaningful workflow/governance changes;
- evidence that changes an existing SKB claim.

Do not return secrets, credentials, transient logs, routine commits, unsupported speculation, or unnecessary private payloads.

## Classification

Every candidate is `NEW`, `UPDATE`, `DUPLICATE`, `CONTRADICTION`, `HISTORICAL`, `UNCERTAIN`, or `REJECTED` before recording.

## Authority

Project-local implementation evidence remains authoritative for implementation details. SKB is the owner-context/cross-project knowledge layer. Recommendations do not authorize changes to owner goals or strategic priorities.

Canonical contract: `soobujmiah/skb` → `standards/automatic-knowledge-sync.md`.
