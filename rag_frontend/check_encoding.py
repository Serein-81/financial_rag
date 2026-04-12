# -*- coding: utf-8 -*-
import os

views_dir = r'D:\Python\Codebase\My_rag\rag_frontend\src\views'
files = ['FinancialDataEntryView.vue', 'FinancialHealthView.vue']
for f in files:
    filepath = os.path.join(views_dir, f)
    print(f'=== {f} ===')
    with open(filepath, 'rb') as file:
        content = file.read()
    # 查找替换字符
    pos = content.find(b'\xef\xbf\xbd')
    if pos >= 0:
        print(f'Found replacement char at {pos}')
        print(f'Context: {content[pos-10:pos+20].hex()}')
    else:
        print('No replacement char found')
    print()
