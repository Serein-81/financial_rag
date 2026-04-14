# 多Agent通信协议标准

## 一、XML通信标签定义

### 1.1 任务调用标签（编排者 → 执行者）

当需要调用其他Agent时，严格使用以下XML格式：

```xml
<Call_Agent>
  <Name>Agent名称</Name>
  <Instruction>给予该Agent的具体指令</Instruction>
  <Input_Data>
    [User Request]: 用户原始需求
    [Retrieved Context]: RAG检索到的相关文档
    [Previous Steps]: 已完成的工作结果
  </Input_Data>
</Call_Agent>
```

**示例**：
```xml
<Call_Agent>
  <Name>finance_specialist</Name>
  <Instruction>分析我们公司2024年度的财务状况，重点关注营收增长率和成本控制</Instruction>
  <Input_Data>
    [User Request]: 我们公司2024年财务状况如何？
    [Retrieved Context]: 检索到年度财务报告.pdf，包含收入、成本、利润等数据
    [Previous Steps]: 无
  </Input_Data>
</Call_Agent>
```

### 1.2 结果返回标签（执行者 → 编排者）

执行者完成任务后，必须使用以下格式返回结果：

```xml
<Task_Result>
  <Agent>Agent名称</Agent>
  <Status>SUCCESS/FAILED/PARTIAL</Status>
  <Content>
    任务执行结果的具体内容
  </Content>
  <Metadata>
    <Execution_Time>执行时间</Execution_Time>
    <Confidence>置信度(0-1)</Confidence>
    <Data_Sources>使用的数据源</Data_Sources>
  </Metadata>
</Task_Result>
```

**示例**：
```xml
<Task_Result>
  <Agent>finance_specialist</Agent>
  <Status>SUCCESS</Status>
  <Content>
    ## 2024年度财务分析报告

    ### 一、总体财务状况
    - 营业收入：5.2亿元，同比增长18.5%
    - 净利润：8900万元，同比增长12.3%
    - 毛利率：17.1%

    ### 二、关键发现
    1. 核心业务稳健增长
    2. 成本控制效果显著
    3. 现金流状况良好
  </Content>
  <Metadata>
    <Execution_Time>3.2秒</Execution_Time>
    <Confidence>0.95</Confidence>
    <Data_Sources>财务报表、ERP系统</Data_Sources>
  </Metadata>
</Task_Result>
```

### 1.3 终止与最终结果标签

当所有任务完成时，输出最终结果：

```xml
<Final_Result>
  <Summary>简要总结（100字以内）</Summary>
  <Details>详细回答</Details>
  <Next_Actions>
    - 建议的后续操作（如有）
  </Next_Actions>
</Final_Result>
```

**示例**：
```xml
<Final_Result>
  <Summary>我们公司2024年财务状况良好，营收和利润均实现两位数增长。</Summary>
  <Details>
    ## 综合财务分析报告

    [详细报告内容...]
  </Details>
  <Next_Actions>
    - 建议进行季度财务复盘
    - 关注成本优化空间
  </Next_Actions>
</Final_Result>
```

### 1.4 错误处理标签

```xml
<Error>
  <Code>错误代码</Code>
  <Message>错误描述</Message>
  <Suggestion>修复建议</Suggestion>
</Error>
```

## 二、输入数据规范

### 2.1 标准输入字段

每个执行者Agent接收的输入必须包含以下标准字段：

```markdown
## 输入数据

### [User Request]
用户的原始需求或问题

### [Retrieved Context]
从RAG系统检索到的相关文档和数据

### [Previous Steps]
其他Agent已完成的工作结果

### [Session Context]
会话上下文信息（用户身份、历史记录等）
```

### 2.2 数据质量要求

- **[User Request]**: 必须完整，不截断
- **[Retrieved Context]**: 如果为空，明确标注"未检索到相关上下文"
- **[Previous Steps]**: 按时间顺序列出已完成的任务
- **数据校验**: 执行者必须验证输入数据的完整性和合理性

## 三、输出质量标准

### 3.1 必需字段

所有Agent的输出必须包含：

1. **Status字段**: SUCCESS/FAILED/PARTIAL
2. **Content字段**: 主要输出内容
3. **Metadata字段**: 执行元信息

### 3.2 内容质量要求

- **完整性**: 必须完整表达，不截断
- **准确性**: 基于提供的[Retrieved Context]回答
- **可执行性**: 建议和结论必须具体可操作
- **一致性**: 输出格式必须严格遵循XML规范

### 3.3 边界控制

- **禁止编造**: 上下文中没有的信息不得编造
- **明确标注**: 无法回答时明确标注"Context insufficient"
- **置信度评估**: 对答案的确定性给出评估

## 四、执行流程规范

### 4.1 编排者执行流程

```markdown
1. **理解需求**
   - 解析用户请求
   - 识别关键信息需求

2. **制定计划**
   - 输出 <Plan> 标签
   - 拆解任务步骤

3. **调用执行者**
   - 使用 <Call_Agent> 标签
   - 等待执行结果

4. **整合结果**
   - 汇总各Agent返回
   - 处理异常情况

5. **输出最终结果**
   - 使用 <Final_Result> 标签
```

### 4.2 执行者执行流程

```markdown
1. **验证输入**
   - 检查必填字段
   - 验证数据质量

2. **执行任务**
   - 调用必要工具
   - 处理业务逻辑

3. **质量检查**
   - 验证输出完整性
   - 确保格式正确

4. **返回结果**
   - 使用 <Task_Result> 标签
   - 包含完整元数据
```

## 五、错误处理机制

### 5.1 执行失败处理

```xml
<Task_Result>
  <Agent>finance_specialist</Agent>
  <Status>FAILED</Status>
  <Content>
    <Error>
      <Code>DATA_NOT_FOUND</Code>
      <Message>未找到2024年度财务报表</Message>
      <Suggestion>请提供2024年度的财务数据或上传相关文档</Suggestion>
    </Error>
  </Content>
  <Metadata>
    <Execution_Time>1.5秒</Execution_Time>
    <Confidence>0</Confidence>
    <Data_Sources>企业数据库</Data_Sources>
  </Metadata>
</Task_Result>
```

### 5.2 部分成功处理

```xml
<Task_Result>
  <Agent>finance_specialist</Agent>
  <Status>PARTIAL</Status>
  <Content>
    ## 部分财务分析

    ### ✅ 已完成
    - 营收分析
    - 成本结构分析

    ### ⚠️ 部分缺失
    - 现金流分析（数据不完整）
    - 同比对比（缺少去年同期数据）

    ### 📋 建议
    请补充完整数据后重新分析
  </Content>
  <Metadata>
    <Execution_Time>2.8秒</Execution_Time>
    <Confidence>0.7</Confidence>
    <Data_Sources>财务报表（部分）</Data_Sources>
  </Metadata>
</Task_Result>
```

## 六、示例对话流程

### 场景：用户询问公司财务状况

**1. 用户输入**:
```
我们公司2024年的财务状况如何？
```

**2. 编排者（Smart Router）**:
```xml
<Plan>
  1. 调用 finance_specialist 获取2024年度财务数据
  2. 调用 tax_specialist 获取税务合规情况
  3. 调用 output_agent 整合分析结果
</Plan>

<Call_Agent>
  <Name>finance_specialist</Name>
  <Instruction>分析我们公司2024年度的财务状况，提供完整的财务分析报告</Instruction>
  <Input_Data>
    [User Request]: 我们公司2024年的财务状况如何？
    [Retrieved Context]: 年度财务报表.pdf
    [Previous Steps]: 无
  </Input_Data>
</Call_Agent>
```

**3. 执行者（Finance Specialist）**:
```xml
<Task_Result>
  <Agent>finance_specialist</Agent>
  <Status>SUCCESS</Status>
  <Content>
    ## 2024年度财务分析

    ### 一、核心财务指标
    - 营业收入：5.2亿元（同比增长18.5%）
    - 净利润：8900万元（同比增长12.3%）
    - 毛利率：17.1%

    ### 二、财务健康度评估
    - 资产负债率：45%（良好）
    - 流动比率：2.1（优秀）
    - 应收账款周转：5.2次

    ### 三、关键发现
    1. 营收增长强劲，主要得益于XXX业务
    2. 成本控制有效，毛利率保持稳定
    3. 现金流充裕，财务风险低
  </Content>
  <Metadata>
    <Execution_Time>3.2秒</Execution_Time>
    <Confidence>0.95</Confidence>
    <Data_Sources>ERP系统、财务报表</Data_Sources>
  </Metadata>
</Task_Result>
```

**4. 编排者整合后**:
```xml
<Final_Result>
  <Summary>我们公司2024年财务状况优秀，营收和利润均实现两位数增长，财务风险低。</Summary>
  <Details>
    ## 综合财务分析报告

    [整合后的完整报告...]
  </Details>
  <Next_Actions>
    - 建议召开季度财务复盘会议
    - 关注XXX业务的成本优化空间
  </Next_Actions>
</Final_Result>
```

## 七、使用规范

### 7.1 标签使用规则

1. **严格性**: 必须严格遵循XML格式，不得随意更改
2. **完整性**: 必须包含所有必需字段
3. **顺序性**: 标签必须按定义顺序排列
4. **转义性**: XML特殊字符必须转义

### 7.2 内容规范

1. **语言一致性**: 中文输出
2. **专业性**: 使用专业术语，但保持可读性
3. **客观性**: 基于数据说话，避免主观臆断
4. **建设性**: 提供可操作的建议

### 7.3 性能要求

- **响应时间**: 单个Agent执行不超过10秒
- **重试机制**: 失败时自动重试一次
- **超时处理**: 超时后返回部分结果或错误信息

---

**版本**: 1.0
**最后更新**: 2025-01-10
**适用范围**: 所有多Agent协作场景
