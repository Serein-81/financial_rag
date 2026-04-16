"""
A2A Protocol Models

定义 A2A 协议的核心数据模型
基于 A2A Protocol Specification v0.2.5
"""

from enum import Enum
from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field
from datetime import datetime
from uuid import uuid4


class TaskStatus(str, Enum):
    """任务状态枚举"""
    SUBMITTED = "submitted"
    WORKING = "working"
    INPUT_REQUIRED = "input-required"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"


class TaskMode(str, Enum):
    """任务模式"""
    PUSH = "push"
    PULL = "pull"
    SSE = "sse"


class MessagePart(BaseModel):
    """消息部件基类"""
    kind: str


class TextPart(MessagePart):
    """文本消息部件"""
    kind: Literal["text"] = "text"
    text: str


class DataPart(MessagePart):
    """数据消息部件"""
    kind: Literal["data"] = "data"
    data: Dict[str, Any]


class FilePart(MessagePart):
    """文件消息部件"""
    kind: Literal["file"] = "file"
    file: Dict[str, Any]


class Message(BaseModel):
    """A2A 消息"""
    role: Literal["user", "agent"] = "user"
    parts: List[MessagePart] = Field(default_factory=list)
    metadata: Optional[Dict[str, Any]] = None


class Task(BaseModel):
    """A2A 任务"""
    id: str = Field(default_factory=lambda: str(uuid4()))
    sessionId: Optional[str] = None
    status: TaskStatus = TaskStatus.SUBMITTED
    messages: List[Message] = Field(default_factory=list)
    artifacts: List[Dict[str, Any]] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    createdAt: datetime = Field(default_factory=datetime.now)
    updatedAt: datetime = Field(default_factory=datetime.now)
    
    def add_message(self, role: str, content: str, metadata: Dict[str, Any] = None) -> None:
        """添加消息"""
        message = Message(
            role=role,
            parts=[TextPart(text=content)],
            metadata=metadata
        )
        self.messages.append(message)
        self.updatedAt = datetime.now()
    
    def add_artifact(self, artifact: Dict[str, Any]) -> None:
        """添加产物"""
        self.artifacts.append(artifact)
        self.updatedAt = datetime.now()


class TaskSubmitParams(BaseModel):
    """任务提交参数"""
    sessionId: Optional[str] = None
    message: Message
    acceptedOutputModes: List[str] = Field(default_factory=lambda: ["text"])
    pushNotification: Optional[Dict[str, Any]] = None


class TaskStatusUpdateEvent(BaseModel):
    """任务状态更新事件"""
    taskId: str
    status: TaskStatus
    metadata: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.now)


class TaskArtifactUpdateEvent(BaseModel):
    """任务产物更新事件"""
    taskId: str
    artifact: Dict[str, Any]
    metadata: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.now)


class TaskGetParams(BaseModel):
    """任务查询参数"""
    taskId: str
    historyLength: Optional[int] = None


class TaskSendSubscribeParams(BaseModel):
    """任务订阅参数"""
    taskId: str


class A2AError(BaseModel):
    """A2A 错误"""
    code: int
    message: str
    data: Optional[Dict[str, Any]] = None


class AgentCapabilities(BaseModel):
    """Agent 能力"""
    streaming: bool = False
    pushNotifications: bool = False
    stateTransitionReports: bool = False
    artifactUpdates: bool = False


class Security(BaseModel):
    """安全配置"""
    schemes: List[str] = Field(default_factory=lambda: ["bearer"])
    credentials: Optional[str] = None
