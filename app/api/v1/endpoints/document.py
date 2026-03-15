"""
⚠️ 废弃文件警告 ⚠️

本文件中的上传接口已被废弃，请使用 knowledge.py 中的接口：
- 新接口：POST /api/v1/knowledge/bases/{kb_id}/upload
- 旧接口：POST /api/v1/documents/upload (已废弃)

废弃原因：
1. 硬编码知识库ID，不支持多知识库隔离
2. 使用本地磁盘存储，已迁移到MinIO对象存储
3. 缺少完善的错误处理和状态管理

保留此文件仅用于向后兼容，建议尽快迁移到新接口。
如需删除此文件，请同时更新 main.py 中的路由注册。
"""

from fastapi import APIRouter

# 创建空路由器，保持API结构完整性
router = APIRouter()

# 所有上传相关的接口已迁移到 knowledge.py
# 如果需要文档管理功能，请使用：
# - GET /api/v1/knowledge/bases/{kb_id}/documents - 获取文档列表
# - POST /api/v1/knowledge/bases/{kb_id}/upload - 上传文档
# - DELETE /api/v1/knowledge/bases/{kb_id}/documents/{doc_id} - 删除文档（待实现）