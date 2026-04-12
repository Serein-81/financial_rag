# 政策智能更新系统 - 实施方案文档

> 创建时间: 2026-04-03
> 版本: v1.0
> 状态: 待实施

---

## 一、项目概述

### 1.1 目标
为企业财税系统构建实时政策更新机制，通过AI智能体自动采集、解析、匹配和推送相关税务政策。

### 1.2 核心价值
- 政策覆盖率: 从 30% 提升到 85%+
- 响应时间: 从"数天"缩短到"数小时"
- 个性化服务: 智能匹配企业适用政策
- 合规风险: 降低 60%+

### 1.3 设计原则
1. **合法合规**: 严格遵守robots.txt，使用官方免费数据源
2. **不影响现有系统**: 政策数据独立存储，与用户知识库完全隔离
3. **渐进式实施**: 分6个阶段逐步推进
4. **代码复用**: 充分利用现有Agent架构

---

## 二、数据源规划

### 2.1 免费合法数据源（按优先级排序）

#### 第一优先级 ⭐⭐⭐⭐⭐（权威官方）
```yaml
1. 国家税务总局官网
   网址: https://www.chinatax.gov.cn
   说明: 最权威的税收政策来源
   更新: 实时

2. 国家法律法规数据库
   网址: https://flk.flchina.cn
   说明: 收录所有税收相关法律法规
   更新: 实时

3. 中国政府网
   网址: https://www.gov.cn
   说明: 国务院政策文件
   更新: 实时
```

#### 第二优先级 ⭐⭐⭐⭐（政策解读和实务）
```yaml
4. 12366纳税服务平台
   网址: https://12366.chinatax.gov.cn
   说明: 税务咨询、热点问答

5. 财政部官网
   网址: https://www.mof.gov.cn
   说明: 财政政策、预决算
```

#### 第三优先级 ⭐⭐⭐（补充来源）
```yaml
6. 地方税务局官网（各省市）
7. 中国裁判文书网（税务案例）
```

### 2.2 更新频率策略

| 级别 | 适用场景 | 更新频率 | 触发时间 | 延迟容忍 |
|------|---------|---------|---------|---------|
| A级 | 总局官网公告 | 每日2次 | 09:00, 15:00 | 4小时 |
| B级 | 财政部、地方政策 | 每周1次 | 每周一09:00 | 1周 |
| C级 | 法律法规库 | 每月1次 | 每月1号 | 1个月 |
| D级 | 关键词监控 | 每30分钟 | 持续运行 | 30分钟 |

### 2.3 爬虫合规要求

**🚫 禁止行为:**
- 绕过反爬措施
- 高频请求（DoS攻击认定）
- 爬取robots.txt禁止的内容
- 爬取个人信息或商业机密
- 商业转售采集数据

**✅ 合规要求:**
- 严格遵守robots.txt
- 速率限制: ≤6次/分钟
- User-Agent标注用途
- 明确免责声明
- 优先使用官方API

---

## 三、数据存储架构

### 3.1 数据库隔离设计

```
┌─────────────────────────────────────────────────────────────┐
│                    数据库架构（完全隔离）                      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  【用户数据】            【政策数据】                          │
│  ├── knowledge_bases    ├── policies (独立表)               │
│  ├── documents         ├── policy_relations                │
│  └── document_chunks   └── enterprise_policy_matches       │
│       ↓                       ↓                             │
│   tenant_id 隔离        无租户隔离（公开数据）               │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 数据表设计

#### policies（政策主表）
```python
class Policy(Base):
    __tablename__ = "policies"
    
    id: UUID                    # 主键
    policy_id: String           # 政策编号（唯一）
    title: String(500)          # 政策标题
    content: Text               # 政策全文
    summary: Text               # 摘要
    
    # 来源信息
    source_url: String(500)     # 来源URL
    source_name: String(100)   # 来源名称
    published_date: DateTime    # 发布日期
    effective_date: DateTime    # 生效日期
    
    # 适用范围
    industries: List[String]   # 适用行业
    regions: List[String]       # 适用地区
    scales: List[String]       # 适用企业规模
    tax_types: List[String]    # 相关税种
    
    # 存储
    embedding: List[Float]      # 向量化
    tags: List[String]          # 标签
    status: String              # active/archived
    version: String             # 版本号
    
    created_at: DateTime
    updated_at: DateTime
```

#### policy_relations（政策关系表）
```python
class PolicyRelation(Base):
    __tablename__ = "policy_relations"
    
    id: UUID
    source_policy_id: UUID      # 源政策
    target_policy_id: UUID      # 目标政策
    relation_type: String      # replaces/supplements/related
```

#### enterprise_policy_matches（企业-政策匹配表）
```python
class EnterprisePolicyMatch(Base):
    __tablename__ = "enterprise_policy_matches"
    
    id: UUID
    enterprise_id: String      # 企业ID（tenant_id）
    policy_id: UUID            # 政策ID
    match_score: Float         # 匹配度
    notification_status: String # pending/sent/acknowledged
    created_at: DateTime
    acknowledged_at: DateTime
```

---

## 四、Agent设计方案

### 4.1 新增Agent清单

| Agent | 职责 | 代码行数 | 优先级 |
|-------|------|---------|--------|
| PolicyAgent | 政策采集+解析+理解+影响分析 | ~400行 | 🔴高 |
| NotificationAgent | 企业匹配+个性化推送+追踪确认 | ~300行 | 🔴高 |

### 4.2 PolicyAgent设计

```python
class PolicyAgent(BaseSpecialistAgent):
    """
    政策处理Agent
    
    职责:
    1. 采集: 从官方来源抓取政策
    2. 解析: 结构化政策内容
    3. 理解: 提取适用行业/地区/规模
    4. 影响: 评估对企业的影响
    """
    
    async def process(self, task: PolicyTask) -> ImpactReport:
        raw = await self.collect_from_sources()
        parsed = await self.parse_and_understand(raw)
        impact = await self.analyze_impact(parsed)
        return ImpactReport(parsed=parsed, impact=impact)
```

### 4.3 NotificationAgent设计

```python
class NotificationAgent(BaseAgent):
    """
    通知Agent
    
    职责:
    1. 匹配: 企业画像与政策匹配
    2. 推送: 个性化政策通知
    3. 追踪: 用户确认状态
    """
    
    async def notify(self, policy: Policy, enterprise_id: str):
        match = await self.match_enterprise(policy, enterprise_id)
        if match.score > 0.7:
            await self.send_notification(policy, enterprise_id)
```

---

## 五、Agent协作方式

### 5.1 协作模式

```
┌─────────────────────────────────────────────────────────────┐
│                    协作模式                                  │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  【Pipeline模式】政策处理流程                                 │
│  PolicyCollector → PolicyParser → ImpactAnalyzer            │
│                                                             │
│  【Broadcast模式】通知分发                                    │
│  重要政策 → 同时通知所有匹配企业                              │
│                                                             │
│  【Event-Driven模式】事件驱动                                 │
│  policy.updated → 触发影响分析 → 触发通知                     │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 5.2 协作流程图

```
[定时调度]
    ↓
[PolicyCollector采集] → [PolicyParser解析]
    ↓
[PolicyStore存储] → [ImpactAnalyzer影响分析]
    ↓                         ↓
[EnterpriseMatcher匹配] → [NotificationAgent推送]
    ↓
[用户确认] → [更新状态]
```

---

## 六、实施计划

### 6.1 阶段划分

#### 第一阶段：数据库与模型设计 🔴
- [ ] 1.1 创建Policy数据模型
- [ ] 1.2 创建PolicyRelation数据模型
- [ ] 1.3 创建EnterprisePolicyMatch数据模型
- [ ] 1.4 数据库迁移脚本
- [ ] 1.5 向量索引配置

#### 第二阶段：核心Agent开发 🔴
- [ ] 2.1 PolicyAgent设计与实现
- [ ] 2.2 NotificationAgent设计与实现
- [ ] 2.3 AgentFactory注册新Agent
- [ ] 2.4 AgentOrchestrator集成

#### 第三阶段：政策采集与解析 🔴
- [ ] 3.1 政策采集工具开发
- [ ] 3.2 robots.txt遵守检查
- [ ] 3.3 速率限制器实现
- [ ] 3.4 政策解析与向量化
- [ ] 3.5 定时更新调度器

#### 第四阶段：检索与通知集成 🔴
- [ ] 4.1 HybridRAGRetriever实现
- [ ] 4.2 企业画像匹配逻辑
- [ ] 4.3 通知推送集成
- [ ] 4.4 消息总线事件集成

#### 第五阶段：测试与部署 🟡
- [ ] 5.1 单元测试
- [ ] 5.2 集成测试
- [ ] 5.3 性能测试
- [ ] 5.4 部署文档

#### 第六阶段：持续优化 🟢
- [ ] 6.1 数据质量监控
- [ ] 6.2 效果评估指标
- [ ] 6.3 用户反馈收集
- [ ] 6.4 版本迭代规划

### 6.2 预计工期

| 阶段 | 工期 | 累计 |
|------|------|------|
| 第一阶段 | 1周 | 1周 |
| 第二阶段 | 1.5周 | 2.5周 |
| 第三阶段 | 1.5周 | 4周 |
| 第四阶段 | 1周 | 5周 |
| 第五阶段 | 1周 | 6周 |
| 第六阶段 | 持续 | - |

**总计: 6-8周**

---

## 七、注意事项

### 7.1 代码修改原则
1. **谨慎删除**: 不删除现有代码，采用扩展方式
2. **配置追加**: 配置文件采用追加方式，不覆盖
3. **测试验证**: 每阶段完成后必须测试
4. **回滚准备**: 保留回滚方案

### 7.2 数据库修改原则
1. **新增表**: 政策相关使用独立表
2. **不影响现有表**: 不修改用户相关表结构
3. **迁移安全**: 使用Alembic迁移，支持回滚

### 7.3 风险控制
1. **爬虫风险**: 严格遵守合规要求
2. **性能风险**: 异步处理+限流
3. **数据质量**: 人工复核机制

---

## 八、版本历史

| 版本 | 日期 | 修改内容 | 作者 |
|------|------|---------|------|
| v1.0 | 2026-04-03 | 初始版本 | AI Assistant |

---

## 九、附录

### A. 免责声明模板
```
【数据使用声明】
1. 本系统采集的政府公开政策信息，仅供企业内部参考使用
2. 政策原文以政府官方发布为准，本系统仅提供辅助解读
3. 如需正式法律意见，请咨询专业税务顾问或律师
4. 禁止将采集数据用于商业转售或非法用途
5. 本系统遵守目标网站的robots.txt和使用条款
```

### B. 合规检查清单
- [ ] robots.txt检查
- [ ] 速率限制（≤6次/分钟）
- [ ] User-Agent正确设置
- [ ] 免责声明附带
- [ ] 不采集禁止内容
- [ ] 不绕过反爬措施
