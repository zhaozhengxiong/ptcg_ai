-- 添加 effect_name 字段并修改唯一约束
-- 支持同一张卡牌的多个效果（ability 和 attack）

-- 1. 添加 effect_name 字段
ALTER TABLE card_execution_plans 
ADD COLUMN IF NOT EXISTS effect_name TEXT;

-- 2. 从 analysis_notes 中提取 effect_name 并填充到新字段
-- 更新现有记录，从 [EFFECT_INFO] 标签中提取 effect_name
-- 使用正则表达式提取 JSON 字符串，然后转换为 JSONB 并提取 effect_name
UPDATE card_execution_plans
SET effect_name = (
    SELECT (jsonb_extract_path_text(
        (regexp_replace(
            regexp_replace(analysis_notes, '.*\[EFFECT_INFO\]', ''),
            '\[/EFFECT_INFO\].*', ''
        ))::jsonb,
        'effect_name'
    ))
)
WHERE effect_name IS NULL 
  AND analysis_notes IS NOT NULL 
  AND analysis_notes LIKE '%[EFFECT_INFO]%';

-- 3. 删除旧的唯一约束
ALTER TABLE card_execution_plans 
DROP CONSTRAINT IF EXISTS card_execution_plans_card_id_version_key;

-- 4. 添加新的唯一约束，包含 effect_name
ALTER TABLE card_execution_plans 
ADD CONSTRAINT card_execution_plans_card_id_version_effect_name_key 
UNIQUE (card_id, version, effect_name);

-- 5. 添加索引以提高查询性能
CREATE INDEX IF NOT EXISTS idx_card_execution_plans_effect_name 
ON card_execution_plans(effect_name);

-- 6. 添加注释
COMMENT ON COLUMN card_execution_plans.effect_name IS '效果名称，用于区分同一张卡牌的不同效果（如能力名称、攻击名称）';

