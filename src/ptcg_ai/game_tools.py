"""Atomic operations available to the referee agent."""
from __future__ import annotations

import random
import secrets
from dataclasses import dataclass, field
from typing import Callable, Dict, Iterable, List, Optional, Sequence

from .database import DatabaseClient
from .models import CardInstance, GameLogEntry, GameState, Zone


def _make_seed() -> str:
    return secrets.token_hex(16)


@dataclass
class ToolCallContext:
    """Context object injected into every tool call."""

    match_id: str
    referee_id: str
    db: DatabaseClient


@dataclass
class GameTools:
    """Collection of stateful atomic operations.

    The tools never perform rule validation. They simply manipulate the game
    state as instructed by the referee agent while generating detailed logs.
    """

    context: ToolCallContext
    state: GameState
    _rng: Callable[[], str] = field(default=_make_seed, repr=False)

    # ------------------------------------------------------------------
    # deck and card queries
    # ------------------------------------------------------------------
    def deck_query(self, player_id: str, predicate: Callable[[CardInstance], bool]) -> List[CardInstance]:
        deck = self.state.players[player_id].zone(Zone.DECK)
        return [card for card in deck.cards if predicate(card)]

    def reveal_top(self, player_id: str, count: int) -> List[CardInstance]:
        deck = self.state.players[player_id].zone(Zone.DECK)
        self._record_zone(player_id, Zone.DECK)
        return deck.cards[:count]

    # ------------------------------------------------------------------
    # selection helpers
    # ------------------------------------------------------------------
    def select_from_candidates(self, candidates: Sequence[CardInstance], max_n: int) -> List[CardInstance]:
        return list(candidates[:max_n])

    # ------------------------------------------------------------------
    # card movement
    # ------------------------------------------------------------------
    def move_card(self, player_id: str, source: Zone, target: Zone, card: CardInstance, position_hint: Optional[int] = None) -> None:
        source_zone = self.state.players[player_id].zone(source)
        target_zone = self.state.players[player_id].zone(target)
        if card not in source_zone.cards:
            raise ValueError(f"Card {card.uid} not found in {source.value}")
        source_zone.cards.remove(card)
        if position_hint is None or position_hint >= len(target_zone.cards):
            target_zone.cards.append(card)
        else:
            target_zone.cards.insert(position_hint, card)
        self._log(
            actor=self.context.referee_id,
            action="move_card",
            payload={
                "card": card.uid,
                "source": source.value,
                "target": target.value,
                "position_hint": position_hint,
            },
        )

    def shuffle(self, player_id: str, zone: Zone) -> None:
        zone_state = self.state.players[player_id].zone(zone)
        seed = self._rng()
        rng = random.Random(int(seed, 16))
        rng.shuffle(zone_state.cards)  # type: ignore[arg-type]
        self._log(
            actor=self.context.referee_id,
            action="shuffle",
            payload={"player_id": player_id, "zone": zone.value},
            random_seed=seed,
        )

    def draw(self, player_id: str, count: int) -> List[CardInstance]:
        deck = self.state.players[player_id].zone(Zone.DECK)
        hand = self.state.players[player_id].zone(Zone.HAND)
        drawn = deck.cards[:count]
        del deck.cards[:count]
        hand.cards.extend(drawn)
        self._log(
            actor=self.context.referee_id,
            action="draw",
            payload={"player_id": player_id, "count": count, "cards": [card.uid for card in drawn]},
        )
        return drawn

    def discard(self, player_id: str, cards: Iterable[CardInstance], reason: str) -> None:
        discard_pile = self.state.players[player_id].zone(Zone.DISCARD)
        hand = self.state.players[player_id].zone(Zone.HAND)
        for card in cards:
            if card in hand.cards:
                hand.cards.remove(card)
            discard_pile.cards.append(card)
        self._log(
            actor=self.context.referee_id,
            action="discard",
            payload={
                "player_id": player_id,
                "reason": reason,
                "cards": [card.uid for card in cards],
            },
        )

    def take_prize(self, player_id: str, count: int = 1) -> List[CardInstance]:
        prize_zone = self.state.players[player_id].zone(Zone.PRIZE)
        hand = self.state.players[player_id].zone(Zone.HAND)
        taken = prize_zone.cards[:count]
        del prize_zone.cards[:count]
        hand.cards.extend(taken)
        self.state.players[player_id].prizes_remaining -= len(taken)
        self._log(
            actor=self.context.referee_id,
            action="take_prize",
            payload={"player_id": player_id, "count": count, "cards": [card.uid for card in taken]},
        )
        return taken

    def random_discard(self, player_id: str, count: int) -> List[CardInstance]:
        hand = self.state.players[player_id].zone(Zone.HAND)
        if count > len(hand.cards):
            raise ValueError("Cannot discard more cards than available in hand")
        seed = self._rng()
        rng = random.Random(int(seed, 16))
        selected = rng.sample(hand.cards, count)
        for card in selected:
            hand.cards.remove(card)
            self.state.players[player_id].zone(Zone.DISCARD).cards.append(card)
        self._log(
            actor=self.context.referee_id,
            action="random_discard",
            payload={"player_id": player_id, "count": count, "cards": [card.uid for card in selected]},
            random_seed=seed,
        )
        return selected

    # ------------------------------------------------------------------
    # zone queries (for deck1 support)
    # ------------------------------------------------------------------
    def query_discard(self, player_id: str, predicate: Optional[Callable[[CardInstance], bool]] = None) -> List[CardInstance]:
        """Query discard pile with optional filter predicate."""
        discard_pile = self.state.players[player_id].zone(Zone.DISCARD)
        if predicate is None:
            return list(discard_pile.cards)
        return [card for card in discard_pile.cards if predicate(card)]
    
    def query_prize_count(self, player_id: str) -> int:
        """Query remaining prize card count."""
        return self.state.players[player_id].prizes_remaining

    # ------------------------------------------------------------------
    # card movement (enhanced for deck1)
    # ------------------------------------------------------------------
    def swap_active_with_bench(self, player_id: str, bench_card_id: str, opponent: bool = False) -> None:
        """Swap active Pokémon with a benched Pokémon.
        
        Args:
            player_id: The player performing the swap (or owner of the active Pokémon if opponent=True)
            bench_card_id: UID of the benched Pokémon to swap with
            opponent: If True, swap opponent's active Pokémon instead
        """
        target_player = player_id if not opponent else [p for p in self.state.players.keys() if p != player_id][0]
        active_zone = self.state.players[target_player].zone(Zone.ACTIVE)
        bench_zone = self.state.players[target_player].zone(Zone.BENCH)
        
        # Find bench card
        bench_card = None
        for card in bench_zone.cards:
            if card.uid == bench_card_id:
                bench_card = card
                break
        
        if bench_card is None:
            raise ValueError(f"Bench card {bench_card_id} not found")
        
        # Swap: move active to bench, bench to active
        if active_zone.cards:
            active_card = active_zone.cards[0]
            active_zone.cards.remove(active_card)
            bench_zone.cards.append(active_card)
        
        bench_zone.cards.remove(bench_card)
        active_zone.cards.append(bench_card)
        
        self._log(
            actor=self.context.referee_id,
            action="swap_active_with_bench",
            payload={
                "player_id": target_player,
                "bench_card": bench_card_id,
                "opponent": opponent,
            },
        )
    
    def shuffle_hand_into_deck(self, player_id: str) -> None:
        """Shuffle hand into deck (bottom of deck)."""
        hand = self.state.players[player_id].zone(Zone.HAND)
        deck = self.state.players[player_id].zone(Zone.DECK)
        
        # Move all hand cards to bottom of deck
        deck.cards.extend(hand.cards)
        hand.cards.clear()
        
        # Shuffle the deck
        self.shuffle(player_id, Zone.DECK)
        
        self._log(
            actor=self.context.referee_id,
            action="shuffle_hand_into_deck",
            payload={"player_id": player_id},
        )
    
    def evolve_pokemon(self, player_id: str, base_card_id: str, evolution_card_id: str, skip_stage1: bool = False) -> None:
        """Evolve a Pokémon by replacing base with evolution.
        
        Args:
            player_id: Owner of the Pokémon
            base_card_id: UID of the base Pokémon to evolve
            evolution_card_id: UID of the evolution card (must be in hand)
            skip_stage1: If True, allows evolving Basic directly to Stage 2 (Rare Candy)
        """
        hand = self.state.players[player_id].zone(Zone.HAND)
        active = self.state.players[player_id].zone(Zone.ACTIVE)
        bench = self.state.players[player_id].zone(Zone.BENCH)
        
        # Find evolution card in hand
        evolution_card = None
        for card in hand.cards:
            if card.uid == evolution_card_id:
                evolution_card = card
                break
        
        if evolution_card is None:
            raise ValueError(f"Evolution card {evolution_card_id} not found in hand")
        
        # Find base card (in active or bench)
        base_card = None
        target_zone = None
        
        for card in active.cards:
            if card.uid == base_card_id:
                base_card = card
                target_zone = active
                break
        
        if base_card is None:
            for card in bench.cards:
                if card.uid == base_card_id:
                    base_card = card
                    target_zone = bench
                    break
        
        if base_card is None:
            raise ValueError(f"Base card {base_card_id} not found in active or bench")
        
        # Transfer damage and energy from base to evolution
        evolution_card.damage = base_card.damage
        evolution_card.attached_energy = list(base_card.attached_energy)
        evolution_card.special_conditions = list(base_card.special_conditions)
        
        # Replace base with evolution
        target_zone.cards.remove(base_card)
        target_zone.cards.append(evolution_card)
        hand.cards.remove(evolution_card)
        
        self._log(
            actor=self.context.referee_id,
            action="evolve_pokemon",
            payload={
                "player_id": player_id,
                "base_card": base_card_id,
                "evolution_card": evolution_card_id,
                "skip_stage1": skip_stage1,
            },
        )

    # ------------------------------------------------------------------
    # damage and combat (for deck1 support)
    # ------------------------------------------------------------------
    def update_damage(self, pokemon_id: str, delta: int) -> None:
        """Update damage on a Pokémon. Delta can be positive (damage) or negative (heal).
        
        Args:
            pokemon_id: UID of the Pokémon card
            delta: Amount of damage to add (positive) or remove (negative)
        """
        # Find the Pokémon in active or bench
        pokemon = None
        for player_id, player_state in self.state.players.items():
            for card in player_state.zone(Zone.ACTIVE).cards:
                if card.uid == pokemon_id:
                    pokemon = card
                    break
            if pokemon is None:
                for card in player_state.zone(Zone.BENCH).cards:
                    if card.uid == pokemon_id:
                        pokemon = card
                        break
            if pokemon is not None:
                break
        
        if pokemon is None:
            raise ValueError(f"Pokémon {pokemon_id} not found in active or bench")
        
        old_damage = pokemon.damage
        pokemon.damage = max(0, pokemon.damage + delta)
        
        self._log(
            actor=self.context.referee_id,
            action="update_damage",
            payload={
                "pokemon_id": pokemon_id,
                "delta": delta,
                "old_damage": old_damage,
                "new_damage": pokemon.damage,
            },
        )
    
    def check_ko(self, pokemon_id: str) -> bool:
        """Check if a Pokémon is knocked out and handle prize card if so.
        
        Returns:
            True if the Pokémon is knocked out, False otherwise
        """
        # Find the Pokémon
        pokemon = None
        owner_id = None
        for player_id, player_state in self.state.players.items():
            for card in player_state.zone(Zone.ACTIVE).cards:
                if card.uid == pokemon_id:
                    pokemon = card
                    owner_id = player_id
                    break
            if pokemon is None:
                for card in player_state.zone(Zone.BENCH).cards:
                    if card.uid == pokemon_id:
                        pokemon = card
                        owner_id = player_id
                        break
            if pokemon is not None:
                break
        
        if pokemon is None:
            raise ValueError(f"Pokémon {pokemon_id} not found")
        
        if pokemon.is_ko:
            # Determine opponent (prize taker)
            opponent_id = [p for p in self.state.players.keys() if p != owner_id][0]
            
            # Take prize card
            if self.state.players[opponent_id].prizes_remaining > 0:
                self.take_prize(opponent_id, 1)
            
            # Move to discard
            active = self.state.players[owner_id].zone(Zone.ACTIVE)
            discard = self.state.players[owner_id].zone(Zone.DISCARD)
            
            if pokemon in active.cards:
                active.cards.remove(pokemon)
                discard.cards.append(pokemon)
            
            self._log(
                actor=self.context.referee_id,
                action="check_ko",
                payload={
                    "pokemon_id": pokemon_id,
                    "owner": owner_id,
                    "prize_taker": opponent_id,
                    "prizes_remaining": self.state.players[opponent_id].prizes_remaining,
                },
            )
            return True
        
        return False

    # ------------------------------------------------------------------
    # energy attachment (for deck1 support)
    # ------------------------------------------------------------------
    def attach_energy(self, energy_card_id: str, target_pokemon_id: str) -> None:
        """Attach an energy card to a Pokémon.
        
        Args:
            energy_card_id: UID of the energy card (must be in hand)
            target_pokemon_id: UID of the target Pokémon (in active or bench)
        """
        # Find energy card in hand
        energy_card = None
        owner_id = None
        for player_id, player_state in self.state.players.items():
            for card in player_state.zone(Zone.HAND).cards:
                if card.uid == energy_card_id:
                    energy_card = card
                    owner_id = player_id
                    break
            if energy_card is not None:
                break
        
        if energy_card is None:
            raise ValueError(f"Energy card {energy_card_id} not found in hand")
        
        if energy_card.definition.card_type != "Energy":
            raise ValueError(f"Card {energy_card_id} is not an energy card")
        
        # Find target Pokémon
        target_pokemon = None
        for player_id, player_state in self.state.players.items():
            for card in player_state.zone(Zone.ACTIVE).cards:
                if card.uid == target_pokemon_id:
                    target_pokemon = card
                    break
            if target_pokemon is None:
                for card in player_state.zone(Zone.BENCH).cards:
                    if card.uid == target_pokemon_id:
                        target_pokemon = card
                        break
            if target_pokemon is not None:
                break
        
        if target_pokemon is None:
            raise ValueError(f"Target Pokémon {target_pokemon_id} not found")
        
        # Attach energy
        hand = self.state.players[owner_id].zone(Zone.HAND)
        hand.cards.remove(energy_card)
        target_pokemon.attached_energy.append(energy_card_id)
        
        self._log(
            actor=self.context.referee_id,
            action="attach_energy",
            payload={
                "energy_card": energy_card_id,
                "target_pokemon": target_pokemon_id,
                "owner": owner_id,
            },
        )

    # ------------------------------------------------------------------
    # usage tracking (for deck1 support)
    # ------------------------------------------------------------------
    def track_usage(self, player_id: str, entity_id: str, counter_type: str, scope: str = "turn") -> None:
        """Track usage of an ability/attack for limiting purposes.
        
        Args:
            player_id: Owner of the entity
            entity_id: UID of the card or ability
            counter_type: Type of usage (e.g., "ability", "attack")
            scope: "turn" for once per turn, "game" for once per game
        """
        self.state.players[player_id].track_usage(entity_id, counter_type, scope)
        self._log(
            actor=self.context.referee_id,
            action="track_usage",
            payload={
                "player_id": player_id,
                "entity_id": entity_id,
                "counter_type": counter_type,
                "scope": scope,
            },
        )
    
    def get_usage_count(self, player_id: str, entity_id: str, counter_type: str, scope: str = "turn") -> int:
        """Get usage count for an ability/attack."""
        return self.state.players[player_id].get_usage_count(entity_id, counter_type, scope)

    # ------------------------------------------------------------------
    # Lost Zone operations
    # ------------------------------------------------------------------
    def send_to_lost_zone(self, player_id: str, card_id: str) -> None:
        """Send a card to the Lost Zone.
        
        Args:
            player_id: Owner of the card
            card_id: UID of the card to send to Lost Zone
        """
        # Find card in any zone (except Lost Zone)
        card = None
        source_zone = None
        
        for zone_type in [Zone.HAND, Zone.DECK, Zone.ACTIVE, Zone.BENCH, Zone.DISCARD, Zone.PRIZE]:
            zone_state = self.state.players[player_id].zone(zone_type)
            for c in zone_state.cards:
                if c.uid == card_id:
                    card = c
                    source_zone = zone_type
                    break
            if card:
                break
        
        if card is None:
            raise ValueError(f"Card {card_id} not found")
        
        # Move to Lost Zone
        source_zone_state = self.state.players[player_id].zone(source_zone)
        lost_zone = self.state.players[player_id].zone(Zone.LOST_ZONE)
        
        source_zone_state.cards.remove(card)
        lost_zone.cards.append(card)
        
        self._log(
            actor=self.context.referee_id,
            action="send_to_lost_zone",
            payload={
                "player_id": player_id,
                "card_id": card_id,
                "source_zone": source_zone.value,
            },
        )

    # ------------------------------------------------------------------
    # Prize operations
    # ------------------------------------------------------------------
    def reveal_prize(self, player_id: str, count: int) -> List[CardInstance]:
        """Reveal prize cards without taking them.
        
        Args:
            player_id: Owner of the prize cards
            count: Number of prize cards to reveal
            
        Returns:
            List of revealed cards
        """
        prize_zone = self.state.players[player_id].zone(Zone.PRIZE)
        revealed = prize_zone.cards[:count]
        
        self._log(
            actor=self.context.referee_id,
            action="reveal_prize",
            payload={
                "player_id": player_id,
                "count": count,
                "cards": [c.uid for c in revealed],
            },
        )
        
        return revealed

    def modify_prize_delta(self, player_id: str, delta: int) -> int:
        """Modify prize count by delta (for effects like Iron Hands ex).
        
        Args:
            player_id: Owner of the prizes
            delta: Change in prize count (can be negative)
            
        Returns:
            New prize count
        """
        old_count = self.state.players[player_id].prizes_remaining
        new_count = max(0, old_count + delta)
        self.state.players[player_id].prizes_remaining = new_count
        
        self._log(
            actor=self.context.referee_id,
            action="modify_prize_delta",
            payload={
                "player_id": player_id,
                "delta": delta,
                "old_count": old_count,
                "new_count": new_count,
            },
        )
        
        return new_count

    # ------------------------------------------------------------------
    # Special conditions
    # ------------------------------------------------------------------
    def set_special_condition(self, pokemon_id: str, condition: str) -> None:
        """Set a special condition on a Pokémon (Asleep, Burned, Confused, Paralyzed, Poisoned).
        
        Args:
            pokemon_id: UID of the Pokémon
            condition: Condition name
        """
        valid_conditions = ["Asleep", "Burned", "Confused", "Paralyzed", "Poisoned"]
        if condition not in valid_conditions:
            raise ValueError(f"Invalid condition: {condition}. Must be one of {valid_conditions}")
        
        # Find Pokémon
        pokemon = None
        for player_id, player_state in self.state.players.items():
            for card in player_state.zone(Zone.ACTIVE).cards:
                if card.uid == pokemon_id:
                    pokemon = card
                    break
            if pokemon is None:
                for card in player_state.zone(Zone.BENCH).cards:
                    if card.uid == pokemon_id:
                        pokemon = card
                        break
            if pokemon:
                break
        
        if pokemon is None:
            raise ValueError(f"Pokémon {pokemon_id} not found")
        
        # Add condition (remove existing if same type)
        if condition in pokemon.special_conditions:
            # Already has this condition
            return
        
        pokemon.special_conditions.append(condition)
        
        self._log(
            actor=self.context.referee_id,
            action="set_special_condition",
            payload={
                "pokemon_id": pokemon_id,
                "condition": condition,
            },
        )

    def remove_special_condition(self, pokemon_id: str, condition: str) -> None:
        """Remove a special condition from a Pokémon.
        
        Args:
            pokemon_id: UID of the Pokémon
            condition: Condition name to remove
        """
        # Find Pokémon
        pokemon = None
        for player_id, player_state in self.state.players.items():
            for card in player_state.zone(Zone.ACTIVE).cards:
                if card.uid == pokemon_id:
                    pokemon = card
                    break
            if pokemon is None:
                for card in player_state.zone(Zone.BENCH).cards:
                    if card.uid == pokemon_id:
                        pokemon = card
                        break
            if pokemon:
                break
        
        if pokemon is None:
            raise ValueError(f"Pokémon {pokemon_id} not found")
        
        if condition in pokemon.special_conditions:
            pokemon.special_conditions.remove(condition)
        
        self._log(
            actor=self.context.referee_id,
            action="remove_special_condition",
            payload={
                "pokemon_id": pokemon_id,
                "condition": condition,
            },
        )

    # ------------------------------------------------------------------
    # Enhanced energy attachment with source tracking
    # ------------------------------------------------------------------
    def attach_energy_from_reveal(
        self,
        player_id: str,
        revealed_cards: List[CardInstance],
        target_pokemon_id: str,
        energy_filter: Optional[Callable[[CardInstance], bool]] = None,
    ) -> Optional[CardInstance]:
        """Attach energy from revealed cards (e.g., Electric Generator).
        
        Args:
            player_id: Owner of the cards
            revealed_cards: List of revealed cards to choose from
            target_pokemon_id: UID of target Pokémon
            energy_filter: Optional filter function for energy cards
            
        Returns:
            Attached energy card or None
        """
        # Filter energy cards
        energy_cards = [
            card for card in revealed_cards
            if card.definition.card_type == "Energy"
            and (energy_filter is None or energy_filter(card))
        ]
        
        if not energy_cards:
            return None
        
        # Attach first matching energy
        energy_card = energy_cards[0]
        
        # Remove from deck and attach
        deck = self.state.players[player_id].zone(Zone.DECK)
        if energy_card in deck.cards:
            deck.cards.remove(energy_card)
        
        # Find target Pokémon
        target_pokemon = None
        for p_id, player_state in self.state.players.items():
            for card in player_state.zone(Zone.ACTIVE).cards:
                if card.uid == target_pokemon_id:
                    target_pokemon = card
                    break
            if target_pokemon is None:
                for card in player_state.zone(Zone.BENCH).cards:
                    if card.uid == target_pokemon_id:
                        target_pokemon = card
                        break
            if target_pokemon:
                break
        
        if target_pokemon is None:
            raise ValueError(f"Target Pokémon {target_pokemon_id} not found")
        
        target_pokemon.attached_energy.append(energy_card.uid)
        
        self._log(
            actor=self.context.referee_id,
            action="attach_energy_from_reveal",
            payload={
                "player_id": player_id,
                "energy_card": energy_card.uid,
                "target_pokemon": target_pokemon_id,
            },
        )
        
        return energy_card

    def query_zone_meta(self, player_id: str, zone: Zone) -> Dict[str, object]:
        """Query zone metadata (counts, types, etc.).
        
        Args:
            player_id: Owner of the zone
            zone: Zone to query
            
        Returns:
            Dictionary with zone metadata
        """
        zone_state = self.state.players[player_id].zone(zone)
        
        card_types = {}
        for card in zone_state.cards:
            card_type = card.definition.card_type
            card_types[card_type] = card_types.get(card_type, 0) + 1
        
        return {
            "card_count": len(zone_state.cards),
            "card_types": card_types,
            "zone": zone.value,
        }
    
    def query_opponent_bench(self, player_id: str) -> List[CardInstance]:
        """Query opponent's bench Pokémon.
        
        Args:
            player_id: The player requesting the query (opponent will be the other player)
            
        Returns:
            List of Pokémon cards on opponent's bench
        """
        opponent_id = [p for p in self.state.players.keys() if p != player_id][0]
        bench_zone = self.state.players[opponent_id].zone(Zone.BENCH)
        return list(bench_zone.cards)
    
    def query_opponent_prize_count(self, player_id: str) -> int:
        """Query opponent's remaining prize card count.
        
        Args:
            player_id: The player requesting the query (opponent will be the other player)
            
        Returns:
            Opponent's remaining prize count
        """
        opponent_id = [p for p in self.state.players.keys() if p != player_id][0]
        return self.state.players[opponent_id].prizes_remaining
    
    def check_stadium_in_play(self, player_id: Optional[str] = None) -> Optional[CardInstance]:
        """Check if a Stadium card is in play.
        
        Args:
            player_id: Optional player ID. If provided, checks that player's Stadium zone.
                      If None, checks both players' Stadium zones (only one should have a Stadium).
            
        Returns:
            Stadium card instance if found, None otherwise
        """
        if player_id:
            stadium_zone = self.state.players[player_id].zone(Zone.STADIUM)
            if stadium_zone.cards:
                return stadium_zone.cards[0]
        else:
            # Check both players
            for p_id in self.state.players.keys():
                stadium_zone = self.state.players[p_id].zone(Zone.STADIUM)
                if stadium_zone.cards:
                    return stadium_zone.cards[0]
        return None
    
    def check_bench_full(self, player_id: str) -> bool:
        """Check if player's bench is full (5 Pokémon).
        
        Args:
            player_id: Owner of the bench
            
        Returns:
            True if bench is full (5 Pokémon), False otherwise
        """
        bench_zone = self.state.players[player_id].zone(Zone.BENCH)
        return len(bench_zone.cards) >= 5
    
    def discard_stadium(self, player_id: str) -> None:
        """Discard the Stadium card in play (if any).
        
        Args:
            player_id: Owner of the Stadium card to discard
        """
        stadium_zone = self.state.players[player_id].zone(Zone.STADIUM)
        discard_zone = self.state.players[player_id].zone(Zone.DISCARD)
        
        if stadium_zone.cards:
            stadium_card = stadium_zone.cards[0]
            stadium_zone.cards.remove(stadium_card)
            discard_zone.cards.append(stadium_card)
            
            self._log(
                actor=self.context.referee_id,
                action="discard_stadium",
                payload={
                    "player_id": player_id,
                    "stadium_card": stadium_card.uid,
                },
            )

    # ------------------------------------------------------------------
    # logging helpers
    # ------------------------------------------------------------------
    def _record_zone(self, player_id: str, zone: Zone) -> None:
        state = self.state.players[player_id].zone(zone)
        self.context.db.record_zone(self.state.match_id, player_id, zone, state.cards)

    def _log(self, actor: str, action: str, payload: dict, random_seed: Optional[str] = None) -> None:
        entry = GameLogEntry(
            match_id=self.state.match_id,
            actor=actor,
            action=action,
            payload=payload,
            random_seed=random_seed,
        )
        self.context.db.append_log(entry)


__all__ = ["GameTools", "ToolCallContext"]
