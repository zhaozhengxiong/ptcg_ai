# PTCG AI Prototype

This repository contains a Python prototype for the Pokémon Trading Card Game (PTCG) AI battle platform described in `doc/requirement.md`. The goal of the prototype is to model the interaction between a referee agent, player agents, a toolbox of atomic game operations, and a persistence layer compatible with PostgreSQL.

## Project layout

```
src/ptcg_ai/
    __init__.py          # Public API shortcuts
    models.py            # Dataclasses representing the game state
    database.py          # PostgreSQL client with in-memory fallback
    card_loader.py       # Utilities to load official card data dumps
    rulebook.py          # Lightweight searchable rule knowledge base
    game_tools.py        # Atomic state mutations invoked by the referee
    referee.py           # Rule enforcement and orchestration logic
    player.py            # Base AI player agent with memory support
    simulation.py        # Convenience helpers to wire agents together
```

## Running tests

```
pytest
```

The tests currently validate the deck-construction constraints enforced by the referee.

## Next steps

* Extend `GameTools` with additional atomic actions for conditions, attachments, and game flow phases.
* Implement richer `PlayerAgent` behaviours powered by reinforcement learning or heuristic search.
* Connect `DatabaseClient` to a live PostgreSQL instance and mirror the schema referenced in the requirement document.
