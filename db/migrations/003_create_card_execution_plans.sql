-- 卡牌预案表
-- 用于存储Rule Analyst Agent分析的卡牌执行预案

CREATE TABLE IF NOT EXISTS card_execution_plans (
    id SERIAL PRIMARY KEY,
    card_name TEXT NOT NULL,
    set_code TEXT NOT NULL,
    number TEXT NOT NULL,
    card_id TEXT NOT NULL,  -- 唯一标识：格式为 "set_code-number"
    
    -- 效果分析结果
    requires_selection BOOLEAN DEFAULT FALSE,
    selection_source TEXT,  -- deck, discard, hand等
    selection_criteria JSONB,  -- 选择条件：{"card_type": "Pokemon", "stage": "Basic", "max_hp": 90等}
    max_selection_count INTEGER,  -- 最大选择数量
    
    -- 执行流程（JSONB数组）
    execution_steps JSONB NOT NULL DEFAULT '[]'::jsonb,
    -- 示例：[{"action": "query_deck_candidates", "params": {...}}, 
    --       {"action": "wait_for_selection"}, 
    --       {"action": "move_cards", "params": {...}}]
    
    -- 规则限制（JSONB数组）
    restrictions JSONB DEFAULT '[]'::jsonb,
    -- 示例：[{"type": "turn_limit", "value": 1, "condition": "first_player"}]
    
    -- 验证规则（JSONB数组）
    validation_rules JSONB DEFAULT '[]'::jsonb,
    
    -- 状态管理
    status TEXT DEFAULT 'draft',  -- draft, reviewed, approved, deprecated
    reviewed_by TEXT,
    reviewed_at TIMESTAMP,
    version INTEGER DEFAULT 1,
    
    -- 元数据
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    analysis_notes TEXT,  -- 分析备注
    
    UNIQUE(card_id, version)
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_card_execution_plans_card_id ON card_execution_plans(card_id);
CREATE INDEX IF NOT EXISTS idx_card_execution_plans_status ON card_execution_plans(status);
CREATE INDEX IF NOT EXISTS idx_card_execution_plans_card_name ON card_execution_plans(card_name);

-- 添加注释
COMMENT ON TABLE card_execution_plans IS '卡牌执行预案表，存储Rule Analyst Agent分析的卡牌效果处理预案';
COMMENT ON COLUMN card_execution_plans.card_id IS '卡牌唯一标识，格式：set_code-number';
COMMENT ON COLUMN card_execution_plans.requires_selection IS '是否需要玩家选择卡牌';
COMMENT ON COLUMN card_execution_plans.selection_source IS '选择来源：deck（牌库）、discard（弃牌堆）、hand（手牌）等';
COMMENT ON COLUMN card_execution_plans.selection_criteria IS '选择条件JSON对象，如{"card_type": "Pokemon", "stage": "Basic"}';
COMMENT ON COLUMN card_execution_plans.max_selection_count IS '最大选择数量，如Battle VIP Pass为2，Super Rod为3';
COMMENT ON COLUMN card_execution_plans.execution_steps IS '执行步骤JSON数组，描述如何执行卡牌效果';
COMMENT ON COLUMN card_execution_plans.restrictions IS '使用限制JSON数组，如回合限制、玩家限制等';
COMMENT ON COLUMN card_execution_plans.status IS '状态：draft（草稿）、reviewed（已审核）、approved（已批准）、deprecated（已废弃）';

