# -*- coding: utf-8 -*-
import os

views_dir = r'D:\Python\Codebase\My_rag\rag_frontend\src\views'
files = os.listdir(views_dir)
for f in sorted(files):
    if f.endswith('.vue'):
        filepath = os.path.join(views_dir, f)
        with open(filepath, 'rb') as file:
            raw = file.read()
        # 检查是否有替换字符
        if b'\xef\xbf\xbd' in raw:
            print(f'Has replacement char: {f}')
            # 统计数量
            count = raw.count(b'\xef\xbf\xbd')
            print(f'  Count: {count}')
