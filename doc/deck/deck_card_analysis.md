## Pidgey PAF 196
- Call for Family
  - rule:Search your deck for up to 2 Basic Pokémon and put them onto your Bench. Then, shuffle your deck.
  - steps:
    1. 合法性校验：备战区是否已满；附着能量是否满足招式需求；是否在战斗区
    2. 结算招式伤害
    3. 查询牌库中的基础宝可梦有哪些（如果没有，则跳到第6步）
    4. 询问玩家的选择
    5. 放置宝可梦到备战区（玩家有可能不选择）
    6. 牌库洗牌
    7. 招式效果结算结束
- Tackle
  - steps:
    1. 合法性校验：附着能量是否满足招式需求；是否在战斗区
    2. 结算招式伤害
   

## Charmander PAF 7
- Blazing Destruction
  - rule:Discard a Stadium in play.
  - steps:
    1. 合法性校验：附着能量是否满足招式需求；是否在战斗区
    2. 结算招式伤害
    3. 是否存在竞技场
    4. 如果有，将竞技场卡放到对应玩家的弃牌堆中
    5. 招式效果结算结束
- Steady Firebreathing
  - steps:
    1. 合法性校验：附着能量是否满足招式需求；是否在战斗区
    2. 结算招式伤害

## Mew CEL 11
- Ability: Mysterious Tail
  - rule:Once during your turn, if this Pokémon is in the Active Spot, you may look at the top 6 cards of your deck, reveal an Item card you find there, and put it into your hand. Shuffle the other cards.
  - steps:
    1. 合法性校验：这个宝可梦的特性是否已使用过；是否在战斗区
    2. 取牌库上方的6张牌的数量（牌库剩余数量不足6张的情况下，就是全部）
    3. 6张牌中是否有Item card
    4. 如果有，则询问玩家的选择；如果没有，跳到第6步
    5. 玩家选择结束，将玩家选择的卡牌加入到玩家的手牌中（玩家有可能不选择）
    6. 将未选择卡牌放回牌库并洗牌
    7. 特性使用结束
- Steady Psyshot
  - steps:
    1. 合法性校验：附着能量是否满足招式需求；是否在战斗区
    2. 结算招式伤害

## Jirachi PAR 126
- Ability: Stellar Veil
  - rule:Prevent all damage counters from being placed on your Benched Pokémon by effects of attacks used by your opponent's Basic Pokémon.
  - 无需使用，自动生效
- Charge Energy
  - rule:Search your deck for up to 2 Basic Energy cards, reveal them, and put them into your hand. Then, shuffle your deck.
  - steps:
    1. 合法性校验：附着能量是否满足招式需求；是否在战斗区
    2. 结算招式伤害
    3. 查询牌库中的基础能量卡有哪些（如果没有，则跳到第6步）
    4. 询问玩家的选择
    5. 将玩家选择的卡牌加入到玩家的手牌中（玩家有可能不选择）
    6. 牌库洗牌
    7. 招式效果结算结束

## Charmeleon PAF 8
- Ability: Flare Veil
  - rule:Prevent all effects of attacks used by your opponent's Pokémon done to this Pokémon. (Damage is not an effect.)
  - 无需使用，自动生效
- Combustion 
  - steps:
    1. 合法性校验：附着能量是否满足招式需求；是否在战斗区
    2. 结算招式伤害

## Rotom V CRZ 45
- Ability: Instant Charge
  - rule:Once during your turn, you may draw 3 cards. If you use this Ability, your turn ends.
  - steps:
    1. 将牌库上方的3张卡牌加入到玩家的手牌中
    2. 回合结束
- Scrap Short 40+
  - Put any number of Pokémon Tool cards from your discard pile in the Lost Zone. This attack does 40 more damage for each card you put in the Lost Zone in this way.
  - steps:
    1. 合法性校验：附着能量是否满足招式需求；是否在战斗区
    2. 查询弃牌区中宝可梦道具卡的数据
    3. 询问玩家的选择
    4. 将玩家选择的宝可梦道具卡从弃牌区放到Lost区（玩家有可能不选择）
    5. 招式伤害计算：40 + 选择的道具卡数量 * 40
    6. 招式伤害结算

## Charmander OBF 26
- Heat Tackle 
  - rule:This Pokémon also does 10 damage to itself.
  - steps:
    1. 合法性校验：附着能量是否满足招式需求；是否在战斗区
    2. 结算招式伤害
    3. 给自己造成10点伤害

## Pidgeot ex OBF 164
- Ability: Quick Search
  - rule:Once during your turn, you may search your deck for a card and put it into your hand. Then, shuffle your deck. You can't use more than 1 Quick Search Ability each turn.
  - steps:
    1. 合法性校验：本回合是否已使用过名为Quick Search的特性；是否在战斗区
    2. 查询牌库数据
    3. 询问玩家的选择
    4. 玩家选择结束，将玩家选择的卡牌加入到玩家的手牌中（玩家有可能不选择）
    5. 牌库洗牌
    6. 特性使用结束
- Blustery Wind 
  - rule:You may discard a Stadium in play.
  - steps:
    1. 合法性校验：附着能量是否满足招式需求；是否在战斗区
    2. 招式伤害结算
    3. 场上是否存在竞技场卡
    4. 如有，询问玩家的选择
    5. 玩家选择结束，如选择是，则将将竞技场卡放到对应玩家的弃牌堆中
    6. 招式效果结算结束

## Manaphy BRS 41
- Ability: Wave Veil
  - rule:Prevent all damage done to your Benched Pokémon by attacks from your opponent's Pokémon.
  - 无需使用，自动生效
- Rain Splash
  - steps:
    1. 合法性校验：附着能量是否满足招式需求；是否在战斗区
    2. 结算招式伤害

## Charizard ex OBF 125
- subtype:Tera
  - rule:As long as this Pokémon is on your Bench, prevent all damage done to this Pokémon by attacks (both yours and your opponent’s).
- Ability: Infernal Reign
  - rule:When you play this Pokémon from your hand to evolve 1 of your Pokémon during your turn, you may search your deck for up to 3 Basic [R] Energy cards and attach them to your Pokémon in any way you like. Then, shuffle your deck.
  - steps:
    1. 合法性校验：是否是从手牌中打出这张卡进行进化的；是否是本回合进化的
    2. 查询牌库中火能量卡的数据
    3. 询问玩家的选择
    4. 将玩家选择的火能量卡附着到玩家选择的宝可梦身上（注意规则中是任意方式，to your Pokémon in any way you like）
    5. 牌库洗牌
- Burning Darkness
  - This attack does 30 more damage for each Prize card your opponent has taken.
  - steps:
    1. 合法性校验：附着能量是否满足招式需求；是否在战斗区
    2. 查询对手已获得的奖赏卡数量
    3. 招式伤害计算：180 + 对手已获得的奖赏卡数量 * 30
    4. 招式伤害结算

## Counter Catcher PAR 160
- rule:
  - You can play this card only if you have more Prize cards remaining than your opponent.
  - Switch in 1 of your opponent's Benched Pokémon to the Active Spot.
- steps:
  - 合法性校验：对手已获得的奖赏卡数量是否大于我方已获得的奖赏卡数量
  - 询问玩家的选择
  - 按照玩家的选择，将另一名玩家被选择的备战区的宝可梦与当前战斗区的宝可梦交换位置
  - 道具卡使用结束

## Vengeful Punch OBF 197
- rule:
  - If the Pokémon this card is attached to is Knocked Out by damage from an attack from your opponent's Pokémon, put 4 damage counters on the Attacking Pokémon.
- steps:
  - 合法性校验：玩家选定的宝可梦身上是否已经存在宝可梦道具
  - 将这张道具卡与选定的宝可梦绑定

## Artazon PAF 76
- subtype: Stadium
- rule:Once during each player's turn, that player may search their deck for a Basic Pokémon, reveal it, and put it into their hand. Then, that player shuffles their deck.
- steps:
  1. 合法性校验：是否本回合已使用过Stadium卡；是否已有同名Stadium在场上
  2. 将Stadium卡从手牌移到Stadium区域（如果已有其他Stadium，将其移到对应玩家的弃牌堆）
  3. Stadium效果生效（持续在场）
  4. 当玩家使用Stadium效果时：
     - 查询该玩家牌库中的基础宝可梦
     - 询问玩家的选择（玩家可能不选择）
     - 将玩家选择的卡牌加入手牌（如果选择了）
     - 牌库洗牌
  5. 训练家卡使用结束（Stadium留在场上）

## Level Ball AOR 76
- subtype: Item
- rule:Search your deck for a Pokémon with 90 HP or less, reveal it, and put it into your hand. Then, shuffle your deck.
- steps:
  1. 合法性校验：卡牌是否在手牌中
  2. 查询牌库中HP≤90的宝可梦有哪些（如果没有，则跳到第5步）
  3. 询问玩家的选择
  4. 将玩家选择的卡牌加入到玩家的手牌中（玩家有可能不选择）
  5. 牌库洗牌
  6. 将训练家卡移到弃牌堆
  7. 训练家卡使用结束

## Forest Seal Stone SIT 156
- subtype: Pokémon Tool
- rule:If the Pokémon this card is attached to is a Pokémon V, it can use the VSTAR Power on this card. (You can't use more than 1 VSTAR Power in a game.)
- steps:
  1. 合法性校验：玩家选定的宝可梦身上是否已经存在宝可梦道具；该宝可梦是否是Pokémon V
  2. 将这张道具卡与选定的宝可梦绑定
  3. 道具卡使用结束（道具卡留在宝可梦身上）
  - VSTAR Power效果（当宝可梦使用VSTAR Power时）：
    1. 合法性校验：本局游戏是否已使用过VSTAR Power
    2. 查询牌库数据
    3. 询问玩家的选择
    4. 玩家选择结束，将玩家选择的卡牌加入到玩家的手牌中（玩家有可能不选择）
    5. 牌库洗牌
    6. VSTAR Power特性使用结束

## Nest Ball SVI 181
- subtype: Item
- rule:Search your deck for a Basic Pokémon, reveal it, and put it into your hand. Then, shuffle your deck.
- steps:
  1. 合法性校验：卡牌是否在手牌中
  2. 查询牌库中的基础宝可梦有哪些（如果没有，则跳到第5步）
  3. 询问玩家的选择
  4. 将玩家选择的卡牌加入到玩家的手牌中（玩家有可能不选择）
  5. 牌库洗牌
  6. 将训练家卡移到弃牌堆
  7. 训练家卡使用结束

## Temple of Sinnoh ASR 155
- subtype: Stadium
- rule:Pokémon in play (both yours and your opponent's) have no Abilities, except Pokémon ex.
- steps:
  1. 合法性校验：是否本回合已使用过Stadium卡；是否已有同名Stadium在场上
  2. 将Stadium卡从手牌移到Stadium区域（如果已有其他Stadium，将其移到对应玩家的弃牌堆）
  3. Stadium效果生效：场上所有非ex宝可梦失去能力（持续在场）
  4. 训练家卡使用结束（Stadium留在场上）

## Arven OBF 186
- subtype: Supporter
- rule:Search your deck for up to 2 in any combination of Pokémon Tool cards and Basic Energy cards, reveal them, and put them into your hand. Then, shuffle your deck.
- steps:
  1. 合法性校验：卡牌是否在手牌中；是否本回合已使用过Supporter卡；先手玩家第一回合不能使用
  2. 查询牌库中的Pokémon Tool卡和基础能量卡有哪些（如果没有，则跳到第5步）
  3. 询问玩家的选择（最多选择2张，任意组合）
  4. 将玩家选择的卡牌加入到玩家的手牌中（玩家有可能不选择）
  5. 牌库洗牌
  6. 将训练家卡移到弃牌堆
  7. 训练家卡使用结束

## Battle VIP Pass FST 225
- subtype: Item
- rule:You can play this card only during your first turn. Search your deck for up to 2 Basic Pokémon, reveal them, and put them into your hand. Then, shuffle your deck.
- steps:
  1. 合法性校验：卡牌是否在手牌中；是否是我方第一回合
  2. 查询牌库中的基础宝可梦有哪些（如果没有，则跳到第5步）
  3. 询问玩家的选择（最多选择2张）
  4. 将玩家选择的卡牌加入到玩家的手牌中（玩家有可能不选择）
  5. 牌库洗牌
  6. 将训练家卡移到弃牌堆
  7. 训练家卡使用结束

## Boss's Orders PAL 172
- subtype: Supporter
- rule:Switch in 1 of your opponent's Benched Pokémon to the Active Spot.
- steps:
  1. 合法性校验：卡牌是否在手牌中；是否本回合已使用过Supporter卡；先手玩家第一回合不能使用
  2. 查询对手备战区的宝可梦有哪些（如果没有，则操作失败）
  3. 询问玩家的选择
  4. 将对手被选择的备战区宝可梦与对手当前战斗区宝可梦交换位置
  5. 将训练家卡移到弃牌堆
  6. 训练家卡使用结束

## Iono PAL 185
- subtype: Supporter
- rule:Each player shuffles their hand into their deck. Then, each player draws a card for each of their remaining Prize cards.
- steps:
  1. 合法性校验：卡牌是否在手牌中；是否本回合已使用过Supporter卡；先手玩家第一回合不能使用
  2. 双方玩家将手牌以随机的顺序放回到牌库的底部
  3. 查询双方剩余的奖赏卡数量
  4. 双方玩家各自从牌库抽等同于剩余奖赏卡数量的卡牌
  5. 将训练家卡移到弃牌堆
  6. 训练家卡使用结束

## Super Rod PAL 188
- subtype: Item
- rule:Shuffle up to 3 in any combination of Pokémon and Basic Energy cards from your discard pile into your deck.
- steps:
  1. 合法性校验：卡牌是否在手牌中
  2. 查询弃牌区中的宝可梦和基础能量卡有哪些（如果没有，则跳到第5步）
  3. 询问玩家的选择（最多选择3张，任意组合）
  4. 将玩家选择的卡牌从弃牌区洗回牌库（玩家有可能不选择）
  5. 牌库洗牌
  6. 将训练家卡移到弃牌堆
  7. 训练家卡使用结束

## Lost Vacuum LOR 162
- subtype: Item
- rule:You may discard a Stadium in play. If you do, put a card from your discard pile in the Lost Zone.
- steps:
  1. 合法性校验：卡牌是否在手牌中；场上是否存在竞技场卡或道具卡（没有则不能使用）
  2. 询问玩家选择一张手牌
  3. 将选择的手牌放到lost zone
  4. 询问玩家选择竞技场卡或道具卡
  5. 将竞技场卡或道具卡移到对应玩家的lost zone
  6. 将训练家卡移到弃牌堆
  7. 训练家卡使用结束

## Collapsed Stadium BRS 137
- subtype: Stadium
- rule:Each player can't have more than 4 Benched Pokémon. If a player has 5 or more Benched Pokémon, they discard Benched Pokémon until they have 4 Pokémon on the Bench. The player who played this card discards first. If more than one effect changes the number of Benched Pokémon allowed, use the smaller number.
- steps:
  1. 合法性校验：是否本回合已使用过Stadium卡；是否已有同名Stadium在场上
  2. 将Stadium卡从手牌移到Stadium区域（如果已有其他Stadium，将其移到对应玩家的弃牌堆）
  3. Stadium效果生效：检查双方备战区宝可梦数量
  4. 如果任何一方的备战区宝可梦达到5只：
     - 询问该玩家选择要丢弃的宝可梦（只剩4只）
     - 将玩家选择的宝可梦以及附着所有的卡牌移到弃牌堆
  5. 训练家卡使用结束（Stadium留在场上）

## Ultra Ball SVI 196
- subtype: Item
- rule:Discard 2 cards from your hand, and search your deck for a Pokémon, reveal it, and put it into your hand. Then, shuffle your deck.
- steps:
  1. 合法性校验：卡牌是否在手牌中；手牌中是否有至少2张其他卡牌
  2. 询问玩家选择要丢弃的2张手牌
  3. 将玩家选择的2张卡牌从手牌移到弃牌堆
  4. 查询牌库中的宝可梦有哪些（如果没有，则跳到第7步）
  5. 询问玩家的选择
  6. 将玩家选择的卡牌加入到玩家的手牌中（玩家有可能不选择）
  7. 牌库洗牌
  8. 将训练家卡移到弃牌堆
  9. 训练家卡使用结束

## Vitality Band SVI 197
- subtype: Pokémon Tool
- rule:The attacks of the Pokémon this card is attached to do 10 more damage to your opponent's Active Pokémon.
- steps:
  1. 合法性校验：玩家选定的宝可梦身上是否已经存在宝可梦道具
  2. 将这张道具卡与选定的宝可梦绑定
  3. 道具卡使用结束（道具卡留在宝可梦身上，该宝可梦的攻击对对手战斗区宝可梦造成额外10点伤害）

## Switch SVI 194
- subtype: Item
- rule:Switch your Active Pokémon with 1 of your Benched Pokémon.
- steps:
  1. 合法性校验：卡牌是否在手牌中；备战区是否有宝可梦
  2. 查询玩家备战区的宝可梦有哪些
  3. 询问玩家的选择
  4. 将玩家选择的备战区宝可梦与当前战斗区宝可梦交换位置
  5. 将训练家卡移到弃牌堆
  6. 训练家卡使用结束

## Professor Turo's Scenario PRE 121
- subtype: Supporter
- rule:Put 1 of your Pokémon in play into your hand. (Discard all cards attached to that Pokémon.)
- steps:
  1. 合法性校验：卡牌是否在手牌中；是否本回合已使用过Supporter卡；先手玩家第一回合不能使用
  2. 查询玩家备战区的宝可梦有哪些（如果没有，则操作失败）
  3. 询问玩家的选择
  4. 将玩家选择的备战区宝可梦移到手牌
  5. 将其他附着的卡牌（能量、道具等）移到弃牌区
  6. 将训练家卡移到弃牌堆
  7. 训练家卡使用结束

## Rare Candy SVI 191
- subtype: Item
- rule:Choose 1 of your Basic Pokémon in play. If you have a Stage 2 card in your hand that evolves from that Pokémon, put that card onto the Basic Pokémon to evolve it, skipping the Stage 1. You can't use this card during your first turn or on a Basic Pokémon that was put into play this turn.","You may play any number of Item cards during your turn.
- steps:
  1. 合法性校验：卡牌是否在手牌中；目标宝可梦是否是Basic Pokémon；该宝可梦是否是上一回合放置在场上的（如果是，则可以使用Rare Candy跳过Stage 1）；手牌中是否有目标宝可梦的stage 2宝可梦卡
  2. 将玩家选择的Stage 2宝可梦从牌库移到场上，替换Basic Pokémon（保留所有附着的卡牌和伤害， 原本的Basic Pokémon卡作为附着卡存在）
  3. 将训练家卡移到弃牌堆
  4. 训练家卡使用结束

## Fire Energy SVE 2
- subtype: Basic Energy
- rule:Basic Energy card provides [R] Energy.
- steps:
  1. 合法性校验：卡牌是否在手牌中；是否本回合已从手牌附能过（每回合只能附能一次，注意是从手牌进行附能）
  2. 询问玩家选择要附能的宝可梦（战斗区或备战区）
  3. 将能量卡附着到玩家选择的宝可梦上
  4. 能量卡使用结束（能量卡留在宝可梦身上）

