"""
输出格式化工具

用于清理和格式化 Agent 的输出，移除调试信息和内部标记
"""

import re


class OutputFormatter:
    """输出格式化器"""
    
    DEBUG_PATTERNS = [
        r'\[工具调用多次失败\]',
        r'\[检测到重复思考.*?\]\n?',
        r'\[达到最大迭代次数.*?\]\n?',
        r'\[处理出错.*?\]\n?',
        r'\[执行超时.*?\]\n?',
        r'\n\n根据检索到的资料：\n\n.*?知识库中未找到相关内容.*?',
    ]
    
    # 内部标记模式（这些不应该暴露给用户）
    INTERNAL_MARKER_PATTERNS = [
        # 知识库和记忆上下文标记
        r'【知识库文档】\s*【提示】以下内容来自知识库文档\s*',
        r'【提示】以下内容来自知识库文档\s*',
        r'【提示】以下内容来自个人对话记忆\s*',
        r'【提示】以下内容包含知识库文档和个人对话记忆.*?\s*',
        r'【知识库文档】\s*',
        r'【记忆上下文】\s*',
        r'【系统指令】.*?(?=\n\n|\n用户|$)',
        # 旧版 XML 格式的内部标记
        r'<Context[^>]*>以下内容.*?</Context>',
        r'<Context[^>]*>.*?</Context>',
        r'<ContextSource[^>]*>.*?</ContextSource>',
        r'<KnowledgeBase>.*?</KnowledgeBase>',
        r'</Context>',
        r'</ContextSource>',
        r'</KnowledgeBase>',
        # 新版 XML 格式的内部标记（InternalContext 结构）
        r'<InternalContext>.*?</InternalContext>',
        r'</InternalContext>',
        r'<KnowledgeBase>.*?</KnowledgeBase>',
        r'</KnowledgeBase>',
        r'<MemoryContext>.*?</MemoryContext>',
        r'</MemoryContext>',
        r'<SystemInstructions>.*?</SystemInstructions>',
        r'</SystemInstructions>',
        # ReAct 思考格式
        r'##\s*Thought\s*\n.*?(?=##\s*Action|##\s*Final\s*Answer|##\s*Observation)',
        r'^Thought:.*$',
        r'^##\s*Thought\s*$',
        r'##\s*Observation\s*\n.*?(?=##\s*Thought|##\s*Action|##\s*Final\s*Answer)',
        r'^Observation:.*$',
        r'##\s*Action\s*\n.*?(?=##\s*Thought|##\s*Observation)',
        r'^Action:.*$',
        # Final Answer 标记（必须放在最后，清理所有残留的 Final Answer 标记）
        r'^Final Answer\s*:\s*',
        r'^##\s*Final Answer\s*:\s*',
        r'^##\s*Final Answer\s*$',
        # 工具调用过程
        r'##\s*Action\s*\n.*?```\n.*?```',
        r'调用工具:.*?\n',
        r'工具结果:.*?\n',
        # 调试标记
        r'\[START\].*?\n',
        r'\[OK\].*?\n',
        r'\[STREAM\].*?\n',
        r'\[ERROR\].*?\n',
        r'\[WARNING\].*?\n',
        r'🌊.*?\n',
        r'🤖.*?\n',
        r'📤.*?\n',
        r'✅.*?\n',
        r'🔍.*?\n',
        r'📚.*?\n',
        r'🧠.*?\n',
        r'💾.*?\n',
        r'🔧.*?\n',
        r'⏰.*?\n',
        r'❌.*?\n',
    ]
    
    # 流式输出时需要实时清理的简单模式（避免误清理正常内容）
    STREAM_CLEAN_PATTERNS = [
        # 中文内部标记
        r'【知识库文档】',
        r'【提示】以下内容来自知识库文档',
        r'【提示】以下内容来自个人对话记忆',
        r'【提示】以下内容包含知识库文档和个人对话记忆',
        r'【记忆上下文】',
        r'【系统指令】',
        # 旧版 XML 格式的内部标记
        r'<Context[^>]*>以下内容.*?</Context>',
        r'<Context[^>]*>.*?</Context>',
        r'<KnowledgeBase>.*?</KnowledgeBase>',
        r'</Context>',
        r'</KnowledgeBase>',
        # 新版 XML 格式的内部标记（InternalContext 结构）
        r'<InternalContext>.*?</InternalContext>',
        r'</InternalContext>',
        r'<KnowledgeBase>.*?</KnowledgeBase>',
        r'</KnowledgeBase>',
        r'<MemoryContext>.*?</MemoryContext>',
        r'</MemoryContext>',
        r'<SystemInstructions>.*?</SystemInstructions>',
        r'</SystemInstructions>',
        # ReAct 格式标题
        r'##\s*Thought\s*\n',
        r'##\s*Observation\s*\n',
        r'##\s*Action\s*\n',
        r'^Thought:\s*',
        r'^Observation:\s*',
        r'^Action:\s*',
        r'^##\s*Thought\s*$',
        r'^##\s*Observation\s*$',
        r'^##\s*Action\s*$',
        # Final Answer 标记（必须放在最后）
        r'^Final Answer\s*:\s*',
        r'^##\s*Final Answer\s*:\s*',
        r'^##\s*Final Answer\s*$',
        r'\n{3,}',  # 连续空行
    ]
    
    PRIVATE_INFO_PATTERNS = [
        r'报销暗号[：:].*',
        r'启动密码[：:].*',
        r'秘[密钥][：:].*',
        r'password[：:].*',
        r'secret[：:].*',
    ]
    
    @classmethod
    def clean_output(cls, text: str) -> str:
        """
        清理输出文本
        
        Args:
            text: 原始输出文本
            
        Returns:
            清理后的文本
        """
        if not text:
            return text
        
        cleaned = text
        
        # 先清理内部标记
        for pattern in cls.INTERNAL_MARKER_PATTERNS:
            cleaned = re.sub(pattern, '', cleaned, flags=re.DOTALL | re.MULTILINE)
        
        # 再清理调试模式
        for pattern in cls.DEBUG_PATTERNS:
            cleaned = re.sub(pattern, '', cleaned, flags=re.DOTALL)
        
        # 清理敏感信息
        for pattern in cls.PRIVATE_INFO_PATTERNS:
            cleaned = re.sub(pattern, '[已隐藏敏感信息]', cleaned, flags=re.IGNORECASE)
        
        # 清理多余的空行（连续的空行压缩为单个空行）
        cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
        
        # 清理行首行尾的空白（但保留段落缩进）
        lines = cleaned.split('\n')
        cleaned_lines = []
        for line in lines:
            # 如果不是段落的一部分（不是以空格开头），则去除首尾空白
            if not line.startswith('    ') and not line.startswith('\t'):
                line = line.strip()
            # 跳过只包含空白字符的行
            if line.strip():
                cleaned_lines.append(line)
        
        cleaned = '\n'.join(cleaned_lines)
        cleaned = cleaned.strip()
        
        return cleaned
    
    @classmethod
    def extract_final_answer(cls, text: str) -> str:
        """
        从输出中提取最终答案（如果包含 ReAct 格式）
        
        Args:
            text: 原始输出文本
            
        Returns:
            最终答案部分
        """
        if not text:
            return text
        
        # 如果已经清理过了，直接返回
        if not cls._contains_react_format(text):
            return text
        
        # 提取 Final Answer 部分
        patterns = [
            r'##\s*Final\s*Answer\s*\n(.*?)$',
            r'Final\s*Answer:\s*(.*?)$',
            r'##\s*Answer\s*\n(.*?)$',
            r'答案[：:]\s*(.*?)$',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.DOTALL | re.IGNORECASE | re.MULTILINE)
            if match:
                answer = match.group(1).strip()
                # 清理提取出的答案中的残留标记
                answer = cls.clean_output(answer)
                return answer
        
        # 如果没有找到 Final Answer，返回原始文本的清理版本
        return cls.clean_output(text)
    
    @classmethod
    def _contains_react_format(cls, text: str) -> bool:
        """
        检查文本是否包含 ReAct 格式标记
        
        Args:
            text: 文本
            
        Returns:
            是否包含 ReAct 格式
        """
        react_markers = [
            r'##\s*Thought',
            r'##\s*Action',
            r'##\s*Observation',
            r'##\s*Final\s*Answer',
            r'Thought:\s*',
            r'Action:\s*',
            r'Observation:\s*',
            r'Final\s*Answer:\s*',
        ]
        
        for marker in react_markers:
            if re.search(marker, text, re.IGNORECASE):
                return True
        
        return False
    
    @classmethod
    def clean_stream_chunk(cls, chunk: str) -> str:
        """
        清理流式输出的单个 chunk（实时清理）
        
        这个方法专门用于流式输出场景，会实时清理明显的内部标记，
        但不会过度清理正常内容。
        
        Args:
            chunk: 单个流式输出块
            
        Returns:
            清理后的块
        """
        if not chunk:
            return chunk
        
        cleaned = chunk
        
        # 应用流式清理模式
        for pattern in cls.STREAM_CLEAN_PATTERNS:
            cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)
        
        # 清理连续空白
        cleaned = re.sub(r'\s{2,}', ' ', cleaned)
        
        return cleaned

    @classmethod
    def clean_stream_content(cls, text: str) -> str:
        """
        Clean a completed streaming response before persistence.

        Streaming chunks are cleaned incrementally while they are emitted, but
        the accumulated buffer can still contain partial ReAct markers or XML
        context wrappers. Keep this method as the full-response counterpart used
        by the chat streaming service.
        """
        if not text:
            return text

        cleaned = cls.strip_react_markers_from_buffer(text)
        cleaned = cls.extract_final_answer(cleaned)
        cleaned = cls.clean_output(cleaned)
        return cleaned
    
    @classmethod
    def strip_react_markers_from_buffer(cls, buffer: str) -> str:
        """
        从流式缓冲区中剥离 ReAct 内部标记段（## Action / ## Thought / ## Observation）

        用于流式输出过程中实时清理已积累的缓冲区，
        防止 ## Action、## Thought 等内部过程标记泄露到前端。

        清理规则：
        - ## Action section_name\n...  → 移除整段
        - ## Thought\n...  → 移除整段
        - ## Observation\n...  → 移除整段
        - ## Final Answer → 移除标题行，保留内容

        Args:
            buffer: 当前累积的流式缓冲区

        Returns:
            清理后的缓冲区
        """
        if not buffer:
            return buffer

        cleaned = buffer

        # 1. 剥离完整的 ## Action\n 段（含内联函数调用的下一行）
        cleaned = re.sub(
            r'##\s*Action\s*\n\s*\w+\s*\([^)]*\)',
            '',
            cleaned,
            flags=re.IGNORECASE
        )
        # 2. 剥离独立的 ## Action 标题行
        cleaned = re.sub(
            r'##\s*Action\s*\n?',
            '',
            cleaned,
            flags=re.IGNORECASE
        )
        # 3. 剥离完整的 ## Thought\n... 段（到下一个 ## 标题行或末尾）
        cleaned = re.sub(
            r'##\s*Thought\s*\n.*?(?=\n##|$)',
            '',
            cleaned,
            flags=re.IGNORECASE | re.DOTALL
        )
        # 4. 剥离完整的 ## Observation\n... 段
        cleaned = re.sub(
            r'##\s*Observation\s*\n.*?(?=\n##|$)',
            '',
            cleaned,
            flags=re.IGNORECASE | re.DOTALL
        )
        # 5. 剥离独立标题行残留
        cleaned = re.sub(
            r'^##\s*(Thought|Action|Observation|Final Answer)\s*$',
            '',
            cleaned,
            flags=re.IGNORECASE | re.MULTILINE
        )
        # 6. 剥离 "Final Answer" 标记标题（保留后面的答案内容）
        cleaned = re.sub(
            r'##\s*Final Answer\s*:\s*',
            '',
            cleaned,
            flags=re.IGNORECASE
        )
        # 7. 清理多余空行
        cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)

        return cleaned.strip()
    
    @classmethod
    def format_no_result_answer(cls, question_type: str = "问题") -> str:
        """
        格式化"未找到结果"的回答
        
        Args:
            question_type: 问题类型
            
        Returns:
            格式化后的回答
        """
        return "抱歉，我暂时没有找到相关的信息。能否请您提供更多细节或换个方式描述您的问题？"
    
    @classmethod
    def format_error_answer(cls, error_msg: str = None) -> str:
        """
        格式化错误回答
        
        Args:
            error_msg: 错误信息
            
        Returns:
            格式化后的回答
        """
        return "抱歉，处理您的请求时遇到了一些问题，请稍后重试。"
    
    @classmethod
    def is_meaningful_response(cls, text: str, min_length: int = 10) -> bool:
        """
        检查响应是否有意义
        
        Args:
            text: 响应文本
            min_length: 最小长度
            
        Returns:
            是否有意义
        """
        if not text:
            return False
        
        cleaned = cls.clean_output(text)
        
        if len(cleaned.strip()) < min_length:
            return False
        
        empty_patterns = [
            r'^[\s\n\r]*$',
            r'^[\[\]（）()。，，、\.\,\!\！\?\？]+$',
        ]
        
        for pattern in empty_patterns:
            if re.match(pattern, cleaned):
                return False
        
        return True


output_formatter = OutputFormatter()
