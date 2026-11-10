# ADR-0001: Record architecture decisions

- **Status**: Accepted
- **Date**: 2026-11-10
- **Deciders**: project owner

## Context
WorldSim is expected to grow through many mechanisms (sensors, open genome,
multicellularity) and possibly an engine port for a game. Choices such as the
save format, the RNG strategy or the genome representation are expensive to
reverse, and the reasoning behind them is easily lost.

## Options considered
- **No formal record** — zero overhead, but the "why" disappears and decisions
  get re-litigated.
- **A decisions section inside ARCHITECTURE.md** — easy, but that file is
  rewritten as the system changes and history is lost at the first reorganisation.
- **Numbered, append-only ADR files in `docs/adr/`** — small overhead, durable history.

## Decision
Use numbered ADRs (`NNNN-short-slug.md`) in `docs/adr/`, with the sections
Context, Options considered, Decision, Consequences. ADRs are never edited after
acceptance; a superseded ADR gets status `Superseded by ADR-NNNN`.

## Consequences
- Expensive-to-reverse choices (save/load format, determinism approach, engine
  port language) each get an ADR before implementation.
- `docs/ARCHITECTURE.md` describes the present; ADRs hold the history.
