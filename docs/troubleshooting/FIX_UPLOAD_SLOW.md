# 修复税务报告上传慢的问题

## 问题现象

从浏览器日志可以看到：
```
📤 [TaxUpload] 准备上传文件: 80发票.pdf 56324 application/pdf
📤 [TaxUpload] 请求URL: http://127.0.0.1:8000/api/v1/tax-reports/upload?tax_type=vat
...
📤 [TaxUpload] 上传超时
```

文件只有56KB，但上传120秒后超时。

## 根本原因

后端 `tax_report.py` 的上传接口在处理文件时包含了太多同步操作：
1. 保存文件到磁盘
2. 读取文件内容
3. AI模型推理（同步阻塞）
4. 保存结果到数据库

这些操作都是**同步阻塞**的，导致API响应时间过长。

## 解决方案

### 方案1：快速返回 + 后台异步处理（推荐）

修改文件：`rag_backend/app/api/v1/tax_report.py`

```python
from fastapi import APIRouter, UploadFile, File, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
import asyncio
import uuid
from datetime import datetime
from pathlib import Path

router = APIRouter()

# 创建上传目录
UPLOAD_DIR = Path("uploads/tax_reports")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

@router.post("/upload")
async def upload_tax_report(
    file: UploadFile = File(...),
    tax_type: str = "vat",
    tax_period_year: int = None,
    tax_period_month: int = None,
    db: AsyncSession = Depends(get_db)
):
    """
    上传税务报告接口
    
    优化：快速保存文件，立即返回，后台异步处理AI分析
    """
    try:
        # 1. 生成报告ID
        report_id = str(uuid.uuid4())
        
        # 2. 保存文件到磁盘（同步快速）
        file_path = UPLOAD_DIR / f"{report_id}_{file.filename}"
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)
        
        # 3. 创建数据库记录
        report = TaxReport(
            id=report_id,
            filename=file.filename,
            file_size=len(content),
            tax_type=tax_type,
            tax_period_year=tax_period_year,
            tax_period_month=tax_period_month,
            status="processing",
            created_at=datetime.utcnow()
        )
        db.add(report)
        await db.commit()
        
        # 4. 立即返回成功响应（不等待AI处理）
        return {
            "report_id": report_id,
            "filename": file.filename,
            "status": "processing",
            "message": "文件上传成功，正在排队处理",
            "created_at": report.created_at.isoformat()
        }
        
        # 5. 后台异步处理AI分析（不阻塞响应）
        asyncio.create_task(
            process_tax_report_background(report_id, str(file_path), db)
        )
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"上传失败: {str(e)}")


async def process_tax_report_background(report_id: str, file_path: str, db: AsyncSession):
    """
    后台异步处理税务报告分析
    
    这个函数在后台运行，不会阻塞API响应
    """
    try:
        # 模拟AI分析处理
        await asyncio.sleep(5)  # 实际这里是AI模型推理
        
        # 读取文件内容
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        
        # 更新数据库状态为已完成
        from sqlalchemy import update
        await db.execute(
            update(TaxReport)
            .where(TaxReport.id == report_id)
            .values(
                status="completed",
                analysis_result={"summary": "分析完成", "content": content[:1000]},
                completed_at=datetime.utcnow()
            )
        )
        await db.commit()
        
        print(f"✅ 报告 {report_id} 处理完成")
        
    except Exception as e:
        print(f"❌ 报告 {report_id} 处理失败: {str(e)}")
        # 更新失败状态
        await db.execute(
            update(TaxReport)
            .where(TaxReport.id == report_id)
            .values(status="failed", error_message=str(e))
        )
        await db.commit()
```

### 方案2：添加进度推送（使用SSE）

如果需要实时推送处理进度，可以使用Server-Sent Events (SSE)：

```python
@router.get("/upload/{report_id}/progress")
async def get_upload_progress(report_id: str, db: AsyncSession = Depends(get_db)):
    """
    获取上传进度（SSE流）
    """
    async def event_generator():
        while True:
            # 查询当前进度
            report = await db.get(TaxReport, report_id)
            
            if not report:
                yield {"event": "error", "data": "报告不存在"}
                break
            
            yield {
                "event": "progress",
                "data": json.dumps({
                    "report_id": report_id,
                    "status": report.status,
                    "progress": get_progress_percentage(report.status)
                })
            }
            
            if report.status in ["completed", "failed"]:
                break
            
            await asyncio.sleep(1)  # 每秒更新一次
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )
```

### 方案3：使用WebSocket推送进度

```python
from fastapi import WebSocket
from typing import Dict

connected_clients: Dict[str, WebSocket] = {}

@router.websocket("/upload/ws/{report_id}")
async def upload_progress_websocket(websocket: WebSocket, report_id: str):
    await websocket.accept()
    connected_clients[report_id] = websocket
    
    try:
        while True:
            # 查询进度
            report = await db.get(TaxReport, report_id)
            
            if report:
                await websocket.send_json({
                    "report_id": report_id,
                    "status": report.status,
                    "progress": get_progress_percentage(report.status)
                })
                
                if report.status in ["completed", "failed"]:
                    break
            
            await asyncio.sleep(1)
    finally:
        del connected_clients[report_id]
```

## 前端修改（支持快速返回）

修改文件：`rag_frontend/src/views/TaxSubmissionView.vue`

```typescript
const handleUpload = async () => {
  if (selectedFiles.value.length === 0) {
    ElMessage.warning('请先选择文件')
    return
  }

  uploadLoading.value = true
  uploadProgress.value = 0
  uploadResult.value = null

  try {
    for (let i = 0; i < selectedFiles.value.length; i++) {
      const file = selectedFiles.value[i]
      
      const result = await taxReportApiClient.upload(file, {
        tax_type: selectedTaxType.value,
        tax_period_year: selectedYear.value,
        tax_period_month: selectedMonth.value,
        onProgress: (progress) => {
          uploadProgress.value = (i / selectedFiles.value.length) * 100 + (progress / selectedFiles.value.length)
        }
      })

      // 即使后端立即返回，前端也可以显示工作流
      if (i === 0) {
        uploadResult.value = {
          success: true,
          message: result.message || '文件上传成功'
        }
      }
    }

    // 清空文件列表
    selectedFiles.value = []
    
    // 显示工作流进度
    startWorkflowSimulation()

  } catch (error: any) {
    uploadResult.value = {
      success: false,
      message: error.message || '上传失败'
    }
  } finally {
    uploadLoading.value = false
  }
}
```

## 性能对比

| 方案 | API响应时间 | 用户体验 | 复杂度 |
|------|------------|----------|--------|
| 当前（同步） | 120秒+ | 卡顿 | 低 |
| 方案1（异步） | <1秒 | 流畅 | 中 |
| 方案2（SSE） | <1秒 | 实时进度 | 高 |
| 方案3（WS） | <1秒 | 实时进度 | 高 |

## 推荐步骤

1. **立即修复**：实施方案1（快速返回 + 后台异步）
   - 修改 `tax_report.py`
   - 前端无需大改

2. **增强体验**：实施方案2或3
   - 添加实时进度推送
   - 需要前端和后端同时修改

3. **测试验证**
   - 测试小文件上传（应该<1秒）
   - 测试大文件上传（应该<1秒返回）
   - 观察工作流动画是否正常显示

## 预期效果

修复后：
- ✅ 上传API响应时间：<1秒
- ✅ 前端进度条：立即显示"上传成功"
- ✅ 工作流动画：立即开始显示AI分析进度
- ✅ 后台处理：异步进行，不影响用户体验
