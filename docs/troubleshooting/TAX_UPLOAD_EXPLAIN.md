# 税务报告上传流程说明

## 上传和显示逻辑

### 工作流和进度条的显示时机

**重要提示**：工作流和进度条**不是一开始就显示**的，它们只在以下情况才会出现：

#### 1. 进度条显示条件
```vue
<el-progress
  v-if="uploadLoading"
  :percentage="Math.round(uploadProgress)"
  class="mt-4 upload-progress intelligent-processing"
>
```
- **显示时机**：用户点击"开始上传"按钮后，`uploadLoading` 变为 `true`
- **消失时机**：上传完成（无论成功或失败）后，`uploadLoading` 变为 `false`
- **视觉效果**：蓝色到绿色的渐变进度条 + 发光脉冲动画

#### 2. 工作流显示条件
```typescript
const startWorkflowSimulation = () => {
  showWorkflowProgress.value = true  // 这里才显示工作流
  workflowStatus.value = 'running'
  // ...
}
```
- **显示时机**：上传**成功**后，自动调用 `startWorkflowSimulation()`
- **消失时机**：工作流完成所有步骤后，会显示完成状态
- **视觉效果**：
  - AI分析进度卡片（顶部有扫描线动画）
  - 5个步骤的状态指示器（文档解析 → AI分析 → 风险评估 → 报告生成 → 完成）
  - 处理日志区域

## 上传慢的原因分析

### 从浏览器日志看到的
```
tax-report.ts:104 📤 [TaxUpload] 准备上传文件: 80发票.pdf 56324 application/pdf
tax-report.ts:105 📤 [TaxUpload] 请求URL: http://127.0.0.1:8000/api/v1/tax-reports/upload?tax_type=vat
```
- 文件大小：56KB（很小）
- 然后就**没有后续日志**了

### 可能的原因

#### 1. 后端处理慢
从后端日志看到：
```
[2026-04-11 07:21:26] [ERROR] ❌ 获取合同审核历史失败: relation "contract_review_reports" does not exist
```
- 数据库表不存在
- 但这是合同审核服务的问题，不是税务服务

#### 2. 后端税务服务可能：
- 文件上传超时设置太短
- 文件处理逻辑复杂
- 数据库连接慢
- 后端服务器资源不足

#### 3. 网络问题
- 前端和后端之间的网络延迟
- Docker容器间的网络配置

### 建议的解决方案

#### 前端优化（已完成）
1. ✅ 将上传超时从30秒增加到120秒
2. ✅ 减少API请求数量（从5个减少到1个）
3. ✅ 添加超时错误处理

#### 后端优化（需要修改后端代码）

**文件位置**：`rag_backend/app/api/v1/tax_report.py`

**优化点1：增加上传超时**
```python
@router.post("/upload", response_model=TaxReportUploadResponse)
async def upload_tax_report(
    file: UploadFile = File(...),
    # ... 其他参数
):
    # 添加超时控制
    try:
        result = await asyncio.wait_for(
            process_upload(file),
            timeout=120.0  # 120秒超时
        )
        return result
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="处理超时")
```

**优化点2：优化文件处理**
```python
async def process_upload(file: UploadFile):
    # 1. 先保存文件（不等待AI处理）
    file_path = await save_file(file)
    
    # 2. 立即返回成功响应
    # 3. 后台异步处理AI分析
    asyncio.create_task(analyze_tax_report_background(file_path))
    
    return {"status": "processing", "report_id": report_id}
```

**优化点3：添加进度推送**
```python
async def process_upload(file: UploadFile):
    # 使用WebSocket或SSE推送进度
    await websocket.send_json({"status": "uploading", "progress": 50})
    await websocket.send_json({"status": "processing", "progress": 75})
    await websocket.send_json({"status": "completed", "progress": 100})
```

### 如何测试工作流和进度条

1. **准备一个小文件**（比如1-2KB的文本文件）
2. **上传文件**
3. **观察**：
   - 上传按钮变成"上传中..."
   - 进度条出现并显示百分比
   - 上传成功后，工作流卡片出现
   - 工作流步骤依次执行（带动画效果）

### 动画效果说明

#### 进度条动画
- **渐变色**：蓝色 → 绿色
- **发光脉冲**：正在上传时有发光效果
- **智能处理**：体现了"AI正在分析"的感觉

#### 工作流动画
- **扫描线**：卡片顶部有光线从上到下扫描
- **脉冲光环**：当前执行步骤的数字周围有呼吸式光环
- **流动渐变**：连接线有渐变色流动效果
- **智能卡片**：卡片整体有轻微脉动

### 当前状态

**上传很慢的原因**：后端处理逻辑可能包含：
1. 文件上传到服务器
2. 文件保存到磁盘
3. 文件读取和解析
4. AI模型推理
5. 结果保存到数据库

这些步骤都是**同步阻塞**的，导致上传API响应慢。

### 快速修复建议

如果需要快速改善用户体验：

```python
# 在 tax_report.py 中
@router.post("/upload")
async def upload_tax_report(file: UploadFile, ...):
    # 1. 保存文件
    file_path = await save_file_fast(file)
    
    # 2. 立即返回（不等待AI处理）
    return {
        "report_id": report_id,
        "status": "pending",
        "message": "文件上传成功，正在排队处理"
    }
    
    # 3. 后台处理（不阻塞响应）
    asyncio.create_task(process_tax_report_async(report_id, file_path))
```

这样上传API会立即返回，前端进度条可以快速完成，然后显示工作流进度。
