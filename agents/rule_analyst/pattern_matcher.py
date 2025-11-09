"""Pattern matcher for PTCG rule text parsing."""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple, Any


class RulePatternMatcher:
    """Pattern matcher for parsing PTCG rule text into structured components."""
    
    # Condition patterns
    CONDITION_ONLY_IF = re.compile(
        r"(?:you can (?:play|use) this card only if|only if you)\s+(.+?)(?:\.|$)",
        re.IGNORECASE
    )
    CONDITION_ONLY_DURING = re.compile(
        r"you can play this card only during (.+?)(?:\.|$)",
        re.IGNORECASE
    )
    CONDITION_IF_YOU_DO = re.compile(
        r"if you do,?\s*(.+?)(?:\.|$)",
        re.IGNORECASE
    )
    
    # Action sequence patterns
    DISCARD_AND = re.compile(
        r"discard (\d+) (?:cards? )?from your hand,?\s*(?:and\s*)?(.+?)(?:\.|$)",
        re.IGNORECASE
    )
    THEN_PATTERN = re.compile(
        r"then,?\s*(.+?)(?:\.|$)",
        re.IGNORECASE
    )
    SHUFFLE_INTO = re.compile(
        r"shuffle (.+?) into (.+?)(?:\.|$)",
        re.IGNORECASE
    )
    
    # Target location patterns
    ONTO_BENCH = re.compile(
        r"put (?:them|it) onto your bench",
        re.IGNORECASE
    )
    INTO_HAND = re.compile(
        r"put (?:them|it) into your hand",
        re.IGNORECASE
    )
    ATTACH_TO_POKEMON = re.compile(
        r"attach (?:them|it) to your pokémon",
        re.IGNORECASE
    )
    
    # Optional action patterns
    YOU_MAY = re.compile(
        r"you may (.+?)(?:\.|$)",
        re.IGNORECASE
    )
    
    # Multi-player patterns
    EACH_PLAYER = re.compile(
        r"each player (.+?)(?:\.|$)",
        re.IGNORECASE
    )
    
    # Search patterns
    SEARCH_DECK = re.compile(
        r"search your deck for (.+?)(?:\.|$)",
        re.IGNORECASE
    )
    SEARCH_DISCARD = re.compile(
        r"search your discard pile for (.+?)(?:\.|$)",
        re.IGNORECASE
    )
    
    # Draw patterns
    DRAW_COUNT = re.compile(
        r"draw (\d+) cards?",
        re.IGNORECASE
    )
    DRAW_FOR_EACH = re.compile(
        r"draw (?:a card|cards?) for each of (.+?)(?:\.|$)",
        re.IGNORECASE
    )
    
    # Switch patterns
    SWITCH_OPPONENT = re.compile(
        r"switch in (\d+) of your opponent's (.+?) to the active spot",
        re.IGNORECASE
    )
    SWITCH_YOUR = re.compile(
        r"switch your active pokémon with (\d+) of your benched pokémon",
        re.IGNORECASE
    )
    
    # Lost Zone patterns
    PUT_INTO_LOST_ZONE = re.compile(
        r"put (.+?) (?:in|into) (?:the )?lost zone",
        re.IGNORECASE
    )
    PUT_IN_LOST_ZONE = re.compile(
        r"put (.+?) in the lost zone",
        re.IGNORECASE
    )
    
    # Reveal patterns
    REVEAL = re.compile(
        r"reveal (?:them|it|.+?)(?:\.|,|$)",
        re.IGNORECASE
    )
    REVEAL_AND = re.compile(
        r"reveal (.+?),?\s*(?:and\s*)?(.+?)(?:\.|$)",
        re.IGNORECASE
    )
    
    # Look at patterns
    LOOK_AT_TOP = re.compile(
        r"look at the top (\d+) cards? (?:of your deck|of your opponent's deck)",
        re.IGNORECASE
    )
    LOOK_AT = re.compile(
        r"look at (.+?)(?:\.|$)",
        re.IGNORECASE
    )
    
    # Damage counter patterns
    PUT_DAMAGE_COUNTERS = re.compile(
        r"put (\d+) damage counters? (?:on|onto) (.+?)(?:\.|$)",
        re.IGNORECASE
    )
    
    # Stadium discard patterns
    DISCARD_STADIUM = re.compile(
        r"(?:you may )?discard (?:a |an )?stadium (?:in play|card)(?:\.|$)",
        re.IGNORECASE
    )
    
    # Put back patterns
    PUT_BACK = re.compile(
        r"put (?:them|it|.+?) back (?:on top of your deck|into your deck|onto your deck)",
        re.IGNORECASE
    )
    SHUFFLE_OTHER = re.compile(
        r"shuffle the other cards?",
        re.IGNORECASE
    )
    
    # Damage calculation patterns
    DAMAGE_MORE_FOR_EACH = re.compile(
        r"does (\d+) more damage (?:for each|times the number of) (.+?)(?:\.|$)",
        re.IGNORECASE
    )
    DAMAGE_MORE = re.compile(
        r"does (\d+) more damage",
        re.IGNORECASE
    )
    DAMAGE_TO_MULTIPLE = re.compile(
        r"does (\d+) damage (?:\(each\) )?to (\d+) of your opponent'?s pokémon",
        re.IGNORECASE
    )
    DAMAGE_TO_SELF = re.compile(
        r"this pokémon does (\d+) damage to itself",
        re.IGNORECASE
    )
    ATTACK_DOES_NOTHING = re.compile(
        r"(?:this attack|that attack) does nothing",
        re.IGNORECASE
    )
    
    # Heal patterns (C-06)
    HEAL_DAMAGE = re.compile(
        r"heal (?:all |(\d+) )?damage (?:from|on) (.+?)(?:\.|$)",
        re.IGNORECASE
    )
    
    # Move damage counters patterns (C-08)
    MOVE_DAMAGE_COUNTERS = re.compile(
        r"move (?:all|(\d+)) damage counters? from (.+?) to (.+?)(?:\.|$)",
        re.IGNORECASE
    )
    
    # Move Energy patterns (C-10)
    MOVE_ENERGY = re.compile(
        r"move (?:an|a|(\d+)) (?:amount of )?(.+? )?energy (?:from|attached to) (.+?) to (.+?)(?:\.|$)",
        re.IGNORECASE
    )
    
    # Devolve patterns (C-13)
    DEVOLVE = re.compile(
        r"devolve (.+?) by (?:removing|putting) (.+?)(?:\.|$)",
        re.IGNORECASE
    )
    
    # Before doing damage pattern (E-09)
    BEFORE_DOING_DAMAGE = re.compile(
        r"before doing damage,?\s*(.+?)(?:\.|$)",
        re.IGNORECASE
    )
    
    # All pattern (D-03)
    ALL_PATTERN = re.compile(
        r"(?:discard|shuffle|move|attach) all (.+?)(?:\.|$)",
        re.IGNORECASE
    )
    
    # Extended discard patterns (改进)
    DISCARD_FROM = re.compile(
        r"discard (?:all|(\d+)|any amount of) (.+?) (?:from|attached to) (.+?)(?:\.|$)",
        re.IGNORECASE
    )
    
    # Extended energy attachment patterns (改进)
    ATTACH_ENERGY_FROM = re.compile(
        r"attach (?:up to )?(\d+)? (.+? )?energy cards? (?:from (.+?))? to (.+?)(?:\.|$)",
        re.IGNORECASE
    )
    
    # Extended switch patterns (改进)
    SWITCH_OPPONENT_ACTIVE = re.compile(
        r"your opponent switches? (?:their )?active pokémon with (\d+) of (?:their )?benched pokémon",
        re.IGNORECASE
    )
    
    @classmethod
    def parse_condition_clauses(cls, rules_text: str) -> List[Dict[str, Any]]:
        """Parse condition clauses from rules text.
        
        Returns:
            List of condition dictionaries with 'type' and 'condition' fields
        """
        conditions = []
        text_lower = rules_text.lower()
        
        # "You can play this card only if..."
        match = cls.CONDITION_ONLY_IF.search(rules_text)
        if match:
            condition_text = match.group(1).strip()
            conditions.append({
                "type": "play_condition",
                "condition": condition_text,
                "description": f"使用条件: {condition_text}"
            })
            
            # Parse specific conditions
            if "more prize cards remaining" in condition_text.lower():
                conditions.append({
                    "type": "prize_comparison",
                    "description": "对手已获得的奖赏卡数量必须大于我方已获得的奖赏卡数量",
                    "params": {},
                    "error_message": "只有在对手已获得的奖赏卡数量大于我方时才能使用"
                })
            # Parse pre-discard requirement (e.g., 'discard 2 other cards from your hand')
            cond_lower = condition_text.lower()
            m_pre_dis = re.search(r"discard\s+(\d+)\s+(?:other\s+)?cards?(?:\s+from\s+your\s+hand)?", cond_lower)
            if m_pre_dis:
                conditions.append({
                    "type": "pre_discard",
                    "count": int(m_pre_dis.group(1)),
                    "source": "hand",
                    "description": f"在使用前需丢弃{m_pre_dis.group(1)}张手牌"
                })
        
        # "You can play this card only during..."
        match = cls.CONDITION_ONLY_DURING.search(rules_text)
        if match:
            time_condition = match.group(1).strip()
            conditions.append({
                "type": "play_condition",
                "condition": time_condition,
                "description": f"使用时间限制: {time_condition}"
            })
            
            if "first turn" in time_condition.lower():
                conditions.append({
                    "type": "turn_limit",
                    "value": 1,
                    "condition": "first_turn",
                    "description": "只能在我方第一回合使用"
                })
        
        return conditions
    
    @classmethod
    def parse_action_sequence(cls, rules_text: str) -> List[Dict[str, Any]]:
        """Parse action sequence from rules text.
        
        Returns:
            List of action dictionaries in order
        """
        actions = []
        
        # Handle "Before doing damage" (E-09) - must be processed first
        before_damage_match = cls.BEFORE_DOING_DAMAGE.search(rules_text)
        if before_damage_match:
            # Extract the action before damage
            before_text = before_damage_match.group(1).strip()
            # Split the text at "before doing damage" to get the rest
            parts = re.split(r'before doing damage,?\s+', rules_text, flags=re.IGNORECASE)
            after_text = parts[1].strip() if len(parts) > 1 else ""
            
            if before_text:
                before_action = cls._parse_single_action(before_text)
                if before_action:
                    before_action["before_damage"] = True
                    actions.append(before_action)
            
            # Continue parsing the rest (damage calculation happens after)
            if after_text:
                rules_text = after_text
            else:
                # If no text after "before doing damage", the rest is just damage
                rules_text = ""
        
        # Handle parentheses: extract content in parentheses and process separately
        # Example: "Put 1 of your Pokémon in play into your hand. (Discard all cards attached to that Pokémon.)"
        # The content in parentheses is usually a clarification or additional effect
        paren_match = re.search(r'\((.+?)\)', rules_text)
        paren_text = None
        if paren_match:
            paren_text = paren_match.group(1).strip()
            # Remove parentheses content from main text for now (will be processed separately)
            rules_text = re.sub(r'\(.+?\)', '', rules_text).strip()
        
        # Handle "If you do" conditional chains
        # Split by "If you do" to separate optional conditional actions
        if_you_do_match = cls.CONDITION_IF_YOU_DO.search(rules_text)
        if if_you_do_match:
            # Split the text at "if you do"
            parts = re.split(r'\s+if you do,?\s+', rules_text, flags=re.IGNORECASE)
            main_text = parts[0].strip()
            conditional_text = parts[1].strip() if len(parts) > 1 else None
        else:
            main_text = rules_text
            conditional_text = None
        
        # Split by sentence boundaries, but preserve "Then" connections
        # First, handle "Then" specially
        if "then" in main_text.lower():
            parts = re.split(r'\s+then,?\s+', main_text, flags=re.IGNORECASE)
            main_text = parts[0]
            then_text = parts[1] if len(parts) > 1 else None
        else:
            then_text = None
        
        # Parse main action (may contain "Discard X, and...")
        match = cls.DISCARD_AND.search(main_text)
        if match:
            count = int(match.group(1))
            next_action = match.group(2).strip()
            actions.append({
                "type": "discard",
                "count": count,
                "source": "hand",
                "description": f"从手牌丢弃{count}张卡牌"
            })
            # Continue parsing the next action
            main_text = next_action
        
        # Parse main action
        action = cls._parse_single_action(main_text)
        if action:
            actions.append(action)
        
        # Parse "Then" action
        if then_text:
            action = cls._parse_single_action(then_text)
            if action:
                actions.append(action)
        
        # Parse "If you do" conditional action
        if conditional_text:
            conditional_action = cls._parse_single_action(conditional_text)
            if conditional_action:
                conditional_action["conditional"] = True
                conditional_action["condition_type"] = "if_you_do"
                actions.append(conditional_action)
        
        # Parse parentheses content (usually clarifications or additional effects)
        # For "Discard all cards attached to that Pokémon", this is part of move_to_hand
        # So we don't need to add it as a separate action
        if paren_text:
            # Check if it's a clarification (like "Discard all cards attached to that Pokémon")
            # These are usually handled as part of the main action
            if "discard" in paren_text.lower() and "attached" in paren_text.lower():
                # This is a clarification, not a separate action
                # It's already handled by move_to_hand's discard_attached flag
                pass
            else:
                # Parse as a separate action
                paren_action = cls._parse_single_action(paren_text)
                if paren_action:
                    actions.append(paren_action)
        
        return actions
    
    @classmethod
    def _parse_single_action(cls, sentence: str) -> Optional[Dict[str, Any]]:
        """Parse a single action from a sentence."""
        sentence_lower = sentence.lower()
        
        # Search deck
        if "search your deck" in sentence_lower:
            match = cls.SEARCH_DECK.search(sentence)
            if match:
                criteria_text = match.group(1).strip()
                # Check if reveal is part of the search sequence
                requires_reveal = "reveal" in sentence_lower
                search_action = {
                    "type": "search",
                    "source": "deck",
                    "criteria": cls._parse_search_criteria(criteria_text),
                    "description": f"搜索牌库: {criteria_text}",
                    "requires_reveal": requires_reveal
                }
                return search_action
        
        # Search discard
        if "from your discard pile" in sentence_lower:
            # "Shuffle up to X from your discard pile into your deck" (Super Rod)
            # Extract criteria from the sentence
            criteria_text = sentence
            return {
                "type": "search",
                "source": "discard",
                "criteria": cls._parse_search_criteria(criteria_text),
                "description": f"搜索弃牌区"
            }
        elif "search your discard pile" in sentence_lower:
            match = cls.SEARCH_DISCARD.search(sentence)
            if match:
                criteria_text = match.group(1).strip()
                return {
                    "type": "search",
                    "source": "discard",
                    "criteria": cls._parse_search_criteria(criteria_text),
                    "description": f"搜索弃牌区: {criteria_text}"
                }
        
        # Draw cards
        match = cls.DRAW_COUNT.search(sentence)
        if match:
            count = int(match.group(1))
            return {
                "type": "draw",
                "count": count,
                "description": f"抽{count}张牌"
            }
        
        # Draw for each
        match = cls.DRAW_FOR_EACH.search(sentence)
        if match:
            condition = match.group(1).strip()
            return {
                "type": "draw",
                "for_each": condition,
                "both_players": "each player" in sentence_lower,
                "description": f"根据{condition}抽牌"
            }
        
        # Lost Zone operations
        if "lost zone" in sentence_lower:
            match = cls.PUT_INTO_LOST_ZONE.search(sentence) or cls.PUT_IN_LOST_ZONE.search(sentence)
            if match:
                source_text = match.group(1).strip()
                # Determine source from context
                if "discard pile" in source_text.lower() or "from your discard pile" in sentence_lower:
                    source = "discard"
                elif "hand" in source_text.lower() or "from your hand" in sentence_lower:
                    source = "hand"
                else:
                    source = None  # Will be determined by context
                return {
                    "type": "move",
                    "target": "lost_zone",
                    "source": source,
                    "description": "将卡牌放入Lost Zone"
                }
        
        # Look at operations (check before "put" to avoid conflicts)
        match = cls.LOOK_AT_TOP.search(sentence)
        if match:
            count = int(match.group(1))
            return {
                "type": "look_at",
                "count": count,
                "source": "deck",
                "description": f"查看牌库上方的{count}张牌"
            }
        
        match = cls.LOOK_AT.search(sentence)
        if match and "look at" in sentence_lower:
            target = match.group(1).strip()
            return {
                "type": "look_at",
                "target": target,
                "description": f"查看{target}"
            }
        
        # Reveal operations (check after search to avoid conflicts)
        if "reveal" in sentence_lower and "search" not in sentence_lower:
            # Check if it's part of a search sequence (e.g., "reveal them, and put them into your hand")
            if "and put" in sentence_lower or "then put" in sentence_lower:
                # This is part of a search sequence, don't create separate reveal action
                pass
            else:
                return {
                    "type": "reveal",
                    "description": "揭示卡牌"
                }
        
        # Heal damage operations (C-06)
        match = cls.HEAL_DAMAGE.search(sentence)
        if match:
            amount = match.group(1)
            target = match.group(2).strip()
            if amount:
                amount = int(amount)
            else:
                amount = "all"  # "heal all damage"
            return {
                "type": "heal",
                "amount": amount,
                "target": target,
                "description": f"治疗{target}的{amount if isinstance(amount, int) else '全部'}点伤害"
            }
        
        # Move damage counters operations (C-08)
        match = cls.MOVE_DAMAGE_COUNTERS.search(sentence)
        if match:
            count = match.group(1)
            source = match.group(2).strip()
            target = match.group(3).strip()
            if count:
                count = int(count)
            else:
                count = "all"  # "move all damage counters"
            return {
                "type": "move_damage_counters",
                "count": count,
                "source": source,
                "target": target,
                "description": f"从{source}移动{count if isinstance(count, int) else '全部'}个伤害计数器到{target}"
            }
        
        # Move Energy operations (C-10)
        match = cls.MOVE_ENERGY.search(sentence)
        if match:
            count = match.group(1)
            energy_type = match.group(2)
            source = match.group(3).strip()
            target = match.group(4).strip()
            if count:
                count = int(count)
            elif count is None:
                count = 1  # "move an Energy" or "move a Energy"
            return {
                "type": "move_energy",
                "count": count,
                "energy_type": energy_type.strip() if energy_type else None,
                "source": source,
                "target": target,
                "description": f"从{source}移动{count}个{energy_type if energy_type else ''}能量到{target}"
            }
        
        # Devolve operations (C-13)
        match = cls.DEVOLVE.search(sentence)
        if match:
            target = match.group(1).strip()
            method = match.group(2).strip()
            return {
                "type": "devolve",
                "target": target,
                "method": method,
                "description": f"退化{target}，通过{method}"
            }
        
        # Damage counter operations
        match = cls.PUT_DAMAGE_COUNTERS.search(sentence)
        if match:
            count = int(match.group(1))
            target = match.group(2).strip()
            return {
                "type": "put_damage_counters",
                "count": count,
                "target": target,
                "description": f"在{target}上放置{count}个伤害计数器"
            }
        
        # "All" pattern (D-03) - check before specific discard patterns
        # 但排除"Discard all cards attached"这种情况（这是move_to_hand的一部分）
        if "attached" not in sentence_lower or "in play" not in sentence_lower:
            match = cls.ALL_PATTERN.search(sentence)
            if match:
                target = match.group(1).strip()
                action_type = None
                if "discard" in sentence_lower:
                    action_type = "discard"
                elif "shuffle" in sentence_lower:
                    action_type = "shuffle"
                elif "move" in sentence_lower and "energy" in sentence_lower:
                    action_type = "move_energy"
                elif "move" in sentence_lower:
                    action_type = "move"
                elif "attach" in sentence_lower:
                    action_type = "attach"
                
                if action_type:
                    return {
                        "type": action_type,
                        "count": "all",
                        "target": target,
                        "description": f"{action_type}所有{target}"
                    }
        
        # Extended discard operations (改进 - 支持从不同来源丢弃)
        # Check this after "All" pattern but before basic discard
        match = cls.DISCARD_FROM.search(sentence)
        if match and "discard" in sentence_lower:
            count = match.group(1)
            card_type = match.group(2).strip()
            source = match.group(3).strip()
            
            if count:
                count = int(count)
            elif "all" in sentence_lower:
                count = "all"
            elif "any amount" in sentence_lower:
                count = "any"
            else:
                count = 1
            
            return {
                "type": "discard",
                "count": count,
                "card_type": card_type,
                "source": source,
                "description": f"从{source}丢弃{count if isinstance(count, int) else count}张{card_type}"
            }
        
        # Stadium discard operations
        match = cls.DISCARD_STADIUM.search(sentence)
        if match:
            return {
                "type": "discard_stadium",
                "optional": "you may" in sentence_lower,
                "description": "丢弃场上的竞技场卡"
            }
        
        # Put back operations
        match = cls.PUT_BACK.search(sentence)
        if match:
            return {
                "type": "put_back",
                "target": "deck",
                "description": "将卡牌放回牌库"
            }
        
        match = cls.SHUFFLE_OTHER.search(sentence)
        if match:
            return {
                "type": "shuffle",
                "target": "deck",
                "description": "将其他卡牌洗回牌库"
            }
        
        # "Put X in play into your hand" (like Professor Turo's Scenario)
        # 需要先检查这个更具体的模式，避免被下面的通用模式匹配
        if "put" in sentence_lower and "in play" in sentence_lower and "into your hand" in sentence_lower:
            # 检查是否是"Put 1 of your Pokémon in play into your hand"或类似模式
            if ("1 of your pokémon" in sentence_lower or "1 of your pokemon" in sentence_lower or 
                "one of your pokémon" in sentence_lower or "one of your pokemon" in sentence_lower or
                "pokémon in play" in sentence_lower or "pokemon in play" in sentence_lower):
                return {
                    "type": "move_to_hand",
                    "source": "in_play",
                    "discard_attached": True,
                    "description": "将场上的宝可梦放回手牌"
                }
        
        # "Put X into hand" or "Put X onto bench" (通用模式，放在更具体的检查之后)
        if "put" in sentence_lower:
            if "into your hand" in sentence_lower or "into their hand" in sentence_lower:
                return {
                    "type": "move",
                    "target": "hand",
                    "description": "将卡牌加入手牌"
                }
            elif "onto your bench" in sentence_lower or "onto the bench" in sentence_lower:
                return {
                    "type": "move",
                    "target": "bench",
                    "description": "将卡牌放到备战区"
            }
        
        # "Choose X in play" (like Rare Candy)
        if "choose" in sentence_lower and "in play" in sentence_lower:
            return {
                "type": "select_in_play",
                "description": "选择场上的宝可梦"
            }
        
        # Shuffle
        if "shuffle" in sentence_lower:
            # "shuffle... into deck" (like Iono: "shuffle their hand into their deck")
            if "into" in sentence_lower and "deck" in sentence_lower:
                # Check if it's "shuffle X into deck"
                shuffle_match = re.search(r"shuffle (.+?) into (?:their|your) deck", sentence_lower)
                if shuffle_match:
                    source = shuffle_match.group(1).strip()
                    if "hand" in source:
                        return {
                            "type": "shuffle_into",
                            "source": "hand",
                            "target": "deck",
                            "both_players": "each player" in sentence_lower or "both players" in sentence_lower,
                            "description": f"将{source}洗入牌库"
                        }
            # Regular shuffle
            elif "then" not in sentence_lower:  # Avoid matching "Then, shuffle"
                return {
                    "type": "shuffle",
                    "target": "deck",
                    "description": "洗牌"
                }
        
        # Switch operations (改进 - 支持更多变体)
        match = cls.SWITCH_OPPONENT_ACTIVE.search(sentence)
        if match:
            return {
                "type": "switch",
                "target": "opponent_active",
                "description": "对手切换战斗区宝可梦"
            }
        
        match = cls.SWITCH_OPPONENT.search(sentence)
        if match:
            return {
                "type": "switch",
                "target": "opponent_bench",
                "description": "切换对手备战区宝可梦"
            }
        
        match = cls.SWITCH_YOUR.search(sentence)
        if match:
            return {
                "type": "switch",
                "target": "your_bench",
                "description": "切换自己的宝可梦"
            }
        
        # Extended energy attachment (改进 - 识别能量来源)
        # Check this before basic attach patterns
        match = cls.ATTACH_ENERGY_FROM.search(sentence)
        if match and "attach" in sentence_lower:
            count = match.group(1)
            energy_type = match.group(2)
            source = match.group(3)
            target = match.group(4).strip() if match.group(4) else None
            
            if count:
                count = int(count)
            else:
                count = 1
            
            return {
                "type": "attach",
                "count": count,
                "energy_type": energy_type.strip() if energy_type else None,
                "source": source if source else "hand",
                "target": target,
                "allow_multiple_targets": "in any way you like" in sentence_lower,
                "description": f"从{source if source else '手牌'}附着{count}个{energy_type if energy_type else ''}能量到{target if target else '宝可梦'}"
            }
        
        # Basic attach pattern (fallback)
        if "attach" in sentence_lower and ("energy" in sentence_lower or "to your pokémon" in sentence_lower):
            allow_multiple = "in any way you like" in sentence_lower or "in any way" in sentence_lower
            source = None
            if "from your discard pile" in sentence_lower:
                source = "discard"
            elif "from your hand" in sentence_lower:
                source = "hand"
            elif "from your deck" in sentence_lower:
                source = "deck"
            
            return {
                "type": "attach",
                "source": source if source else "hand",
                "allow_multiple_targets": allow_multiple,
                "description": "附着能量到宝可梦"
            }
        
        return None
    
    @classmethod
    def _parse_search_criteria(cls, criteria_text: str) -> Dict[str, Any]:
        """Parse search criteria from text."""
        criteria = {}
        text_lower = criteria_text.lower()
        
        # Check for combinations first (e.g., "Pokémon Tool cards and Basic Energy cards")
        if "in any combination" in text_lower or ("and" in text_lower and ("tool" in text_lower or "energy" in text_lower)):
            criteria["allow_combination"] = True
            card_types = []
            if "pokémon tool" in text_lower or "pokemon tool" in text_lower or "tool" in text_lower:
                card_types.append({"card_type": "Trainer", "subtype": "Tool"})
            if "basic energy" in text_lower:
                card_types.append({"card_type": "Energy", "energy_type": "Basic Energy"})
            if "pokémon" in text_lower or "pokemon" in text_lower:
                card_types.append({"card_type": "Pokemon"})
            if card_types:
                criteria["card_types"] = card_types
        
        # Single card type
        elif "pokémon tool" in text_lower or "pokemon tool" in text_lower:
            criteria["card_type"] = "Trainer"
            criteria["subtype"] = "Tool"
        elif "basic pokémon" in text_lower or "basic pokemon" in text_lower:
            criteria["card_type"] = "Pokemon"
            criteria["stage"] = "Basic"
        elif "pokémon" in text_lower or "pokemon" in text_lower:
            criteria["card_type"] = "Pokemon"
        elif "basic energy" in text_lower:
            criteria["card_type"] = "Energy"
            criteria["energy_type"] = "Basic Energy"
        elif "energy" in text_lower:
            criteria["card_type"] = "Energy"
        elif "item" in text_lower:
            criteria["card_type"] = "Trainer"
            criteria["subtype"] = "Item"
        elif "tool" in text_lower:
            criteria["card_type"] = "Trainer"
            criteria["subtype"] = "Tool"
        
        # HP limit
        hp_match = re.search(r"(\d+)\s+hp\s+or\s+less", text_lower)
        if hp_match:
            criteria["max_hp"] = int(hp_match.group(1))
        
        # Energy color
        energy_colors = {
            "[r]": "Fire", "[g]": "Grass", "[w]": "Water",
            "[l]": "Lightning", "[p]": "Psychic", "[f]": "Fighting",
            "[d]": "Darkness", "[m]": "Metal"
        }
        for symbol, color in energy_colors.items():
            if symbol in text_lower:
                criteria["energy_color"] = color
                break
        
        # Count - support "up to", "any amount", "any number", "as many as you like"
        up_to_match = re.search(r"up to (\d+)", text_lower)
        if up_to_match:
            criteria["max_count"] = int(up_to_match.group(1))
            criteria["min_count"] = 0  # "up to" allows 0
        elif "any amount" in text_lower or "any number" in text_lower:
            criteria["count_type"] = "any"
            criteria["min_count"] = 0
        elif "as many as you like" in text_lower:
            criteria["count_type"] = "any"
            criteria["min_count"] = 0
        
        return criteria
    
    @classmethod
    def parse_target_location(cls, rules_text: str) -> Optional[str]:
        """Parse target location from rules text.
        
        Returns:
            Target location: "bench", "hand", "pokemon", or None
        """
        if cls.ONTO_BENCH.search(rules_text):
            return "bench"
        elif cls.INTO_HAND.search(rules_text):
            return "hand"
        elif cls.ATTACH_TO_POKEMON.search(rules_text):
            return "pokemon"
        return None
    
    @classmethod
    def parse_optional_actions(cls, rules_text: str) -> List[Dict[str, Any]]:
        """Parse optional actions from rules text.
        
        Returns:
            List of optional action dictionaries
        """
        optional_actions = []
        
        match = cls.YOU_MAY.search(rules_text)
        if match:
            action_text = match.group(1).strip()
            optional_actions.append({
                "type": "optional",
                "action": action_text,
                "description": f"可选操作: {action_text}"
            })
        
        return optional_actions
    
    @classmethod
    def is_multi_player(cls, rules_text: str) -> bool:
        """Check if the rule affects multiple players."""
        return bool(cls.EACH_PLAYER.search(rules_text))
    
    @classmethod
    def parse_attach_action(cls, rules_text: str) -> Optional[Dict[str, Any]]:
        """Parse energy attachment action.
        
        Returns:
            Attachment action dict or None
        """
        text_lower = rules_text.lower()
        if "attach" in text_lower and ("energy" in text_lower or "to your pokémon" in text_lower):
            # Try extended pattern first
            match = cls.ATTACH_ENERGY_FROM.search(rules_text)
            if match:
                count = match.group(1)
                energy_type = match.group(2)
                source = match.group(3)
                target = match.group(4).strip() if match.group(4) else None
                
                if count:
                    count = int(count)
                else:
                    count = 1
                
                return {
                    "type": "attach",
                    "count": count,
                    "energy_type": energy_type.strip() if energy_type else None,
                    "source": source if source else "hand",
                    "target": target,
                    "allow_multiple_targets": "in any way you like" in text_lower or "in any way" in text_lower,
                    "description": f"从{source if source else '手牌'}附着{count}个{energy_type if energy_type else ''}能量到{target if target else '宝可梦'}"
                }
            
            # Fallback to basic pattern
            allow_multiple = "in any way you like" in text_lower or "in any way" in text_lower
            
            # Try to detect source
            source = None
            if "from your discard pile" in text_lower:
                source = "discard"
            elif "from your hand" in text_lower:
                source = "hand"
            elif "from your deck" in text_lower:
                source = "deck"
            
            return {
                "type": "attach",
                "source": source if source else "hand",
                "allow_multiple_targets": allow_multiple,
                "description": "附着能量到宝可梦"
            }
        return None
    
    @classmethod
    def parse_damage_calculation(cls, attack_text: str) -> Optional[Dict[str, Any]]:
        """Parse damage calculation patterns from attack text.
        
        Returns:
            Damage calculation dict or None
        """
        text_lower = attack_text.lower()
        
        # "The attack does nothing" (D-01)
        match = cls.ATTACK_DOES_NOTHING.search(attack_text)
        if match:
            return {
                "type": "attack_does_nothing",
                "description": "攻击无效"
            }
        
        # "This Pokémon does N damage to itself" (B-09)
        match = cls.DAMAGE_TO_SELF.search(attack_text)
        if match:
            damage = int(match.group(1))
            return {
                "type": "damage_to_self",
                "damage": damage,
                "description": f"对自己造成{damage}点伤害"
            }
        
        # "This attack does N damage (each) to X of your opponent's Pokémon" (B-08)
        match = cls.DAMAGE_TO_MULTIPLE.search(attack_text)
        if match:
            damage = int(match.group(1))
            count = int(match.group(2))
            return {
                "type": "damage_to_multiple",
                "damage": damage,
                "count": count,
                "description": f"对{count}个对手的宝可梦各造成{damage}点伤害"
            }
        
        # "does N more damage for each X"
        match = cls.DAMAGE_MORE_FOR_EACH.search(attack_text)
        if match:
            bonus = int(match.group(1))
            condition = match.group(2).strip()
            return {
                "type": "damage_bonus_per",
                "bonus": bonus,
                "condition": condition,
                "description": f"每{condition}增加{bonus}点伤害"
            }
        
        # "does N more damage"
        match = cls.DAMAGE_MORE.search(attack_text)
        if match:
            bonus = int(match.group(1))
            return {
                "type": "damage_bonus",
                "bonus": bonus,
                "description": f"增加{bonus}点伤害"
            }
        
        return None

