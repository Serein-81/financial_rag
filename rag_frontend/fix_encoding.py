# -*- coding: utf-8 -*-
import os
import re

files_to_fix = [
    "d:/Python/Codebase/My_rag/rag_frontend/src/views/AuditResultView.vue",
    "d:/Python/Codebase/My_rag/rag_frontend/src/views/ChatLogsView.vue",
    "d:/Python/Codebase/My_rag/rag_frontend/src/views/ContractReviewView.vue",
    "d:/Python/Codebase/My_rag/rag_frontend/src/views/FinancialDataEntryView.vue",
    "d:/Python/Codebase/My_rag/rag_frontend/src/views/FinancialHealthView.vue",
    "d:/Python/Codebase/My_rag/rag_frontend/src/views/HITLApprovalView.vue",
    "d:/Python/Codebase/My_rag/rag_frontend/src/views/IntentClassifierDebugView.vue",
    "d:/Python/Codebase/My_rag/rag_frontend/src/views/MultiAgentChatView.vue",
    "d:/Python/Codebase/My_rag/rag_frontend/src/views/NotificationCenterView.vue",
    "d:/Python/Codebase/My_rag/rag_frontend/src/views/SecurityAuditView.vue",
    "d:/Python/Codebase/My_rag/rag_frontend/src/views/TaskManagementView.vue",
    "d:/Python/Codebase/My_rag/rag_frontend/src/views/TaxIntelligenceView.vue",
    "d:/Python/Codebase/My_rag/rag_frontend/src/views/TestDataGuideView.vue",
]

def read_file(filepath):
    encodings = ['utf-8', 'gbk', 'latin-1']
    for enc in encodings:
        try:
            with open(filepath, 'r', encoding=enc) as f:
                return f.read(), enc
        except:
            continue
    return None, None

def write_file(filepath, content):
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

replacements = [
    (b'\xe8\x8e\xb7\xe5\x8f\x96\xe4\xbb\xbb\xe5\x8a\xa1\xe7\x8a\xb6\xe6\x80\x81\xe5\xa4\xb1\xe9\x94\x99', b'\xe8\x8e\xb7\xe5\x8f\x96\xe4\xbb\xbb\xe5\x8a\xa1\xe7\x8a\xb6\xe6\x80\x81\xe5\xa4\xb1\xe8\xb4\xa5'),
    (b'\xe5\x8f\x91\xe8\xb5\xb7\xe4\xb8\x80\xe4\xba\x9b\xe5\xaf\xb9\xe9\x97\xae', b'\xe5\x8f\x91\xe8\xb5\xb7\xe4\xb8\x80\xe4\xba\x9b\xe5\xaf\xb9\xe8\xaf\x9d'),
    (b'\xe9\x94\x80\xe5\x94\xae\xe5\x90\x88\xe9\x97\xb4', b'\xe9\x94\x80\xe5\x94\xae\xe5\x90\x88\xe5\x90\x8c'),
    (b'\xe5\xb7\xb2\xe5\x8a\xa0\xe8\xbd\xbd\xe8\xb4\xa2\xe5\x8a\xa1\xe6\x95\xb0\xe6\x8d\xae', b'\xe5\xb7\xb2\xe5\x8a\xa0\xe8\xbd\xbd\xe8\xb4\xa2\xe5\x8a\xa1\xe6\x95\xb0\xe6\x8d\xae'),
    (b'\xe5\xb7\xb2\xe8\xbf\x87\xe6\x9c\x9f', b'\xe5\xb7\xb2\xe8\xbf\x87\xe6\x9c\x9f'),
    (b'\xe5\x85\xb3\xe9\x94\xae\xe8\xaf\x8d', b'\xe5\x85\xb3\xe9\x94\xae\xe8\xaf\x8d'),
    (b'\xe5\x88\x86\xe6\x9e\x90\xe9\x97\xae\xe9\xa2\x98\xe7\xb1\xbb\xe5\x9e\x8b\xe5\x92\x8c\xe6\x84\x8f\xe5\x9b\xbe', b'\xe5\x88\x86\xe6\x9e\x90\xe9\x97\xae\xe9\xa2\x98\xe7\xb1\xbb\xe5\x9e\x8b\xe5\x92\x8c\xe6\x84\x8f\xe5\x9b\xbe'),
    (b'\xe6\x8f\x90\xe7\xa4\xba\xe8\xaf\x8d\xe6\xb3\xa8\xe5\x85\xa5', b'\xe6\x8f\x90\xe7\xa4\xba\xe8\xaf\x8d\xe6\xb3\xa8\xe5\x85\xa5'),
    (b'\xe5\xbc\x82\xe5\xb8\xb8\xe6\xa3\x80\xe6\xb5\x8b', b'\xe5\xbc\x82\xe5\xb8\xb8\xe6\xa3\x80\xe6\xb5\x8b'),
    (b'\xe9\xab\x98\xe6\x96\xb0\xe4\xbc\x81\xe4\xb8\x9a', b'\xe9\xab\x98\xe6\x96\xb0\xe4\xbc\x81\xe4\xb8\x9a'),
    (b'\xe6\x80\xbb\xe6\x94\xb6\xe5\x85\xa5', b'\xe6\x80\xbb\xe6\x94\xb6\xe5\x85\xa5'),
    (b'\xe7\xb4\xa1\xe6\x80\xa5', b'\xe7\xb4\xa1\xe6\x80\xa5'),
    (b'\xe5\x8d\xb0\xe5\xba\xa6\xe5\xbc\x80\xe5\x8f\x91\xe7\x9a\x84\xe5\x95\x86\xe5\x93\x81', b'\xe5\x8d\xb0\xe5\xba\xa6\xe5\xbc\x80\xe5\x8f\x91\xe7\x9a\x84\xe5\x95\x86\xe5\x93\x81'),
]

for filepath in files_to_fix:
    if not os.path.exists(filepath):
        print(f"File not found: {filepath}")
        continue

    content_bytes = None
    for enc in ['gbk', 'latin-1', 'utf-8']:
        try:
            with open(filepath, 'rb') as f:
                content_bytes = f.read()
            break
        except:
            continue

    if content_bytes is None:
        print(f"Cannot read: {filepath}")
        continue

    original = content_bytes
    for old, new in replacements:
        content_bytes = content_bytes.replace(old, new)

    if content_bytes != original:
        with open(filepath, 'wb') as f:
            f.write(content_bytes)
        print(f"Fixed: {os.path.basename(filepath)}")
    else:
        print(f"No changes: {os.path.basename(filepath)}")

print("\nDone!")
