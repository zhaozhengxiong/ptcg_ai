"""规则文档查询模块，用于从 advanced-manual-split 查询相关规则文档。"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = None
try:
    import logging
    logger = logging.getLogger(__name__)
except:
    pass


class RulebookQuery:
    """规则文档查询器，用于从 advanced-manual-split 文件夹查询相关规则。"""
    
    # 规则模式到文档文件的映射
    RULE_PATTERN_MAP: Dict[str, List[str]] = {
        # Damage calculation (B系列)
        "damage_to_self": ["part_II_B_B-09.md"],
        "damage_to_multiple": ["part_II_B_B-08.md"],
        "attack_does_nothing": ["part_II_D_D-01.md"],
        "damage_bonus_per": ["part_II_B_B-02.md"],
        "damage_bonus": ["part_II_B_B-04.md"],
        "damage_less": ["part_II_B_B-03.md", "part_II_B_B-05.md"],
        
        # Effects (C系列)
        "discard": ["part_II_C_C-01.md"],
        "put_back": ["part_II_C_C-02.md"],
        "switch": ["part_II_C_C-03.md", "part_II_C_C-04.md", "part_II_C_C-05.md"],
        "heal": ["part_II_C_C-06.md"],
        "put_damage_counters": ["part_II_C_C-07.md"],
        "move_damage_counters": ["part_II_C_C-08.md"],
        "attach_energy": ["part_II_C_C-09.md"],
        "move_energy": ["part_II_C_C-10.md"],
        "put_pokemon_bench": ["part_II_C_C-11.md"],
        "evolve": ["part_II_C_C-12.md"],
        "devolve": ["part_II_C_C-13.md"],
        "cant_retreat": ["part_II_C_C-14.md"],
        "cant_attack": ["part_II_C_C-15.md"],
        "prevent_damage": ["part_II_C_C-16.md"],
        "prevent_effects": ["part_II_C_C-17.md"],
        "use_as_attack": ["part_II_C_C-18.md"],
        "cant_play": ["part_II_C_C-19.md"],
        "look_at": ["part_II_C_C-20.md"],
        
        # Glossary (D系列)
        "all": ["part_II_D_D-03.md"],
        "choose": ["part_II_D_D-04.md"],
        "up_to": ["part_II_D_D-05.md"],
        "as_many_as_you_like": ["part_II_D_D-02.md"],
        
        # Other text (E系列)
        "before_doing_damage": ["part_II_E_E-09.md"],
        "you_may": ["part_II_E_E-10.md"],
        "if_you_do": ["part_II_E_E-19.md"],
        "once_during_turn": ["part_II_E_E-17.md"],
        "then_shuffle": ["part_II_E_E-18.md"],
        
        # Attacks and Abilities (I系列)
        "attacks": ["part_I_A_A-01.md"],
        "abilities": ["part_I_A_A-02.md"],
        "retreat": ["part_I_A_A-03.md"],
        "put_pokemon_bench": ["part_I_A_A-04.md"],
        "evolve": ["part_I_A_A-05.md"],
        
        # Trainers (I系列)
        "items": ["part_I_B_B-01.md"],
        "supporters": ["part_I_B_B-02.md"],
        "stadiums": ["part_I_B_B-03.md"],
    }
    
    def __init__(self, rulebook_dir: Optional[Path] = None):
        """初始化规则文档查询器。
        
        Args:
            rulebook_dir: 规则文档目录路径，默认为项目根目录下的 doc/advanced-manual-split
        """
        if rulebook_dir is None:
            # 默认路径：项目根目录/doc/advanced-manual-split
            current_file = Path(__file__)
            project_root = current_file.parent.parent.parent
            rulebook_dir = project_root / "doc" / "advanced-manual-split"
        
        self.rulebook_dir = rulebook_dir
        self._cache: Dict[str, str] = {}  # 缓存已读取的文件内容
        self._full_manual_cache: Optional[str] = None  # 缓存完整手册内容
        
    def _load_file(self, filename: str) -> Optional[str]:
        """加载规则文档文件。
        
        Args:
            filename: 文件名（如 part_II_C_C-06.md）
            
        Returns:
            文件内容，如果文件不存在则返回None
        """
        if filename in self._cache:
            return self._cache[filename]
        
        file_path = self.rulebook_dir / filename
        if not file_path.exists():
            if logger:
                logger.warning(f"规则文档文件不存在: {file_path}")
            return None
        
        try:
            content = file_path.read_text(encoding='utf-8')
            self._cache[filename] = content
            return content
        except Exception as e:
            if logger:
                logger.error(f"读取规则文档文件失败 {file_path}: {e}")
            return None
    
    def _load_full_manual(self) -> Optional[str]:
        """加载完整的规则手册（advanced-manual_extracted.md）。
        
        Returns:
            完整手册内容
        """
        if self._full_manual_cache is not None:
            return self._full_manual_cache
        
        # 尝试从父目录加载完整手册
        full_manual_path = self.rulebook_dir.parent / "advanced-manual_extracted.md"
        if not full_manual_path.exists():
            if logger:
                logger.warning(f"完整规则手册不存在: {full_manual_path}")
            return None
        
        try:
            content = full_manual_path.read_text(encoding='utf-8')
            self._full_manual_cache = content
            return content
        except Exception as e:
            if logger:
                logger.error(f"读取完整规则手册失败 {full_manual_path}: {e}")
            return None
    
    def _extract_rule_section(self, content: str, rule_id: str) -> Optional[str]:
        """从完整手册中提取特定规则章节。
        
        Args:
            content: 完整手册内容
            rule_id: 规则ID（如 "C-06", "B-08"）
            
        Returns:
            规则章节内容，如果未找到则返回None
        """
        # 匹配规则章节标题，支持多种格式
        patterns = [
            rf"####\s+{re.escape(rule_id)}\s+(.+?)(?=####|\Z)",
            rf"####\s+{re.escape(rule_id.replace('-', '-\s*'))}\s+(.+?)(?=####|\Z)",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
            if match:
                return match.group(0).strip()
        
        return None
    
    def query_by_pattern(self, pattern_type: str) -> List[Dict[str, str]]:
        """根据模式类型查询相关规则文档。
        
        Args:
            pattern_type: 模式类型（如 "heal", "damage_to_self"）
            
        Returns:
            规则文档列表，每个元素包含 filename 和 content
        """
        filenames = self.RULE_PATTERN_MAP.get(pattern_type, [])
        results = []
        
        for filename in filenames:
            content = self._load_file(filename)
            if content:
                results.append({
                    "filename": filename,
                    "content": content,
                    "rule_id": self._extract_rule_id_from_filename(filename)
                })
        
        # 如果split文件只有标题，尝试从完整手册中提取
        if not results or all(len(r["content"].strip()) < 100 for r in results):
            full_manual = self._load_full_manual()
            if full_manual:
                rule_id = self._pattern_to_rule_id(pattern_type)
                if rule_id:
                    section_content = self._extract_rule_section(full_manual, rule_id)
                    if section_content:
                        results.append({
                            "filename": f"extracted_{rule_id}",
                            "content": section_content,
                            "rule_id": rule_id
                        })
        
        return results
    
    def _extract_rule_id_from_filename(self, filename: str) -> Optional[str]:
        """从文件名提取规则ID。
        
        Args:
            filename: 文件名（如 part_II_C_C-06.md）
            
        Returns:
            规则ID（如 C-06）
        """
        # 匹配格式：part_II_C_C-06.md -> C-06
        match = re.search(r'([A-Z])-([A-Z])-([A-Z])-(\d+)', filename)
        if match:
            return f"{match.group(3)}-{match.group(4).zfill(2)}"
        
        # 匹配格式：part_II_B_B-08.md -> B-08
        match = re.search(r'([A-Z])-([A-Z])-(\d+)', filename)
        if match:
            return f"{match.group(2)}-{match.group(3).zfill(2)}"
        
        return None
    
    def _pattern_to_rule_id(self, pattern_type: str) -> Optional[str]:
        """将模式类型转换为规则ID。
        
        Args:
            pattern_type: 模式类型
            
        Returns:
            规则ID（如 "C-06"）
        """
        # 从RULE_PATTERN_MAP中查找对应的规则ID
        filenames = self.RULE_PATTERN_MAP.get(pattern_type, [])
        if filenames:
            rule_id = self._extract_rule_id_from_filename(filenames[0])
            return rule_id
        return None
    
    def query_by_text(self, rules_text: str) -> List[Dict[str, str]]:
        """根据规则文本查询相关规则文档。
        
        Args:
            rules_text: 规则文本（如 "Heal 30 damage from 1 of your Pokémon"）
            
        Returns:
            规则文档列表
        """
        rules_text_lower = rules_text.lower()
        matched_patterns = []
        
        # 根据关键词匹配模式
        if "heal" in rules_text_lower and "damage" in rules_text_lower:
            matched_patterns.append("heal")
        if "move" in rules_text_lower and "damage counter" in rules_text_lower:
            matched_patterns.append("move_damage_counters")
        if "move" in rules_text_lower and "energy" in rules_text_lower:
            matched_patterns.append("move_energy")
        if "devolve" in rules_text_lower:
            matched_patterns.append("devolve")
        if "before doing damage" in rules_text_lower:
            matched_patterns.append("before_doing_damage")
        if "does" in rules_text_lower and "damage to itself" in rules_text_lower:
            matched_patterns.append("damage_to_self")
        if "does" in rules_text_lower and "damage" in rules_text_lower and "each" in rules_text_lower and "opponent" in rules_text_lower:
            matched_patterns.append("damage_to_multiple")
        if "does nothing" in rules_text_lower:
            matched_patterns.append("attack_does_nothing")
        if "discard" in rules_text_lower:
            matched_patterns.append("discard")
        if "search" in rules_text_lower and "deck" in rules_text_lower:
            matched_patterns.append("search")
        if "attach" in rules_text_lower and "energy" in rules_text_lower:
            matched_patterns.append("attach_energy")
        if "switch" in rules_text_lower:
            matched_patterns.append("switch")
        if "look at" in rules_text_lower:
            matched_patterns.append("look_at")
        if "you may" in rules_text_lower:
            matched_patterns.append("you_may")
        if "if you do" in rules_text_lower:
            matched_patterns.append("if_you_do")
        if "once during" in rules_text_lower:
            matched_patterns.append("once_during_turn")
        if "then" in rules_text_lower and "shuffle" in rules_text_lower:
            matched_patterns.append("then_shuffle")
        
        # 查询所有匹配的模式
        all_results = []
        seen_rule_ids = set()
        
        for pattern in matched_patterns:
            results = self.query_by_pattern(pattern)
            for result in results:
                rule_id = result.get("rule_id")
                if rule_id and rule_id not in seen_rule_ids:
                    seen_rule_ids.add(rule_id)
                    all_results.append(result)
        
        return all_results
    
    def get_rule_summary(self, rule_id: str) -> Optional[str]:
        """获取规则摘要（前200个字符）。
        
        Args:
            rule_id: 规则ID（如 "C-06"）
            
        Returns:
            规则摘要
        """
        # 先尝试从完整手册中提取
        full_manual = self._load_full_manual()
        if full_manual:
            section = self._extract_rule_section(full_manual, rule_id)
            if section:
                # 提取摘要（去除标题，取前200字符）
                lines = section.split('\n')
                content_lines = [line for line in lines if not line.strip().startswith('#') and line.strip()]
                summary = ' '.join(content_lines[:5])  # 取前5行
                if len(summary) > 200:
                    summary = summary[:200] + "..."
                return summary
        
        return None


def create_rulebook_query(rulebook_dir: Optional[Path] = None) -> RulebookQuery:
    """创建规则文档查询器实例。
    
    Args:
        rulebook_dir: 规则文档目录路径
        
    Returns:
        RulebookQuery实例
    """
    return RulebookQuery(rulebook_dir=rulebook_dir)

