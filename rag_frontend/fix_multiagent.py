# -*- coding: utf-8 -*-
import os

filepath = r'D:\Python\Codebase\My_rag\rag_frontend\src\views\MultiAgentChatView.vue'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Find the problematic area and fix
content = content.replace('启用知识检索/span>', '启用知识检索</span>')

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)

print('Fixed MultiAgentChatView.vue')
