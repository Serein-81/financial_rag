# -*- coding: utf-8 -*-
import os

def fix_file(filepath):
    """修复单个文件中的所有乱码"""
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()
    
    original = content
    
    # 通用修复
    fixes = [
        # TestDataGuideView.vue
        ('应税销售额?<br/>', '应税销售额<br/>'),
        
        # NotificationCenterView.vue
        ('删除选中?${selectedNotifications.value.size} 条通知吗？', '删除选中${selectedNotifications.value.size}条通知吗？'),
        ('清空所?${activeCategory', '清空所有${activeCategory'),
        ('通知和提?', '通知和提醒'),
        ('取消全?', '取消全选'),
        ('全?', '全选'),
        ('最新优?', '最新优先'),
        ('最早优?', '最早优先'),
        ('筛?', '筛选'),
        ('优先?', '优先级'),
        ('状?', '状态'),
        ('清除筛?', '清除筛选'),
        ('条未?', '条未读'),
        
        # MultiAgentChatView.vue
        ('多专家协作处?', '多专家协作处理'),
        ('反思审?', '反思审核'),
        ('质量审核与优?', '质量审核与优化'),
        ('保存状态失?', '保存状态失败'),
        ('会话已超时，清除旧状?', '会话已超时，清除旧状态'),
        ('已生成的部分内容：\\n\\n${state.currentResponse || \'（无内容?`', '已生成的部分内容：\\n\\n${state.currentResponse || \'（无内容）`}'),
        ('加载状态失?', '加载状态失败'),
        ('清除状态失?', '清除状态失败'),
        ('已恢复之前的会话状?', '已恢复之前的会话状态'),
        ('服务器返回错? HTTP', '服务器返回错误 HTTP'),
        ('无法读取响应?', '无法读取响应'),
        ('请求超时?分钟）', '请求超时（10分钟）'),
        ('需要人工审?) || false', '需要人工审核） || false'),
        ('多专家协?· 智能路由 · 质量审核', '多专家协作 · 智能路由 · 质量审核'),
        ('启用反思审?', '启用反思审核'),
        ('启用知识检?', '启用知识检索'),
        ('需要人工审?', '需要人工审核'),
        ('已激?', '已激活'),
        ('可以继续新的对话或刷新页面重试?', '可以继续新的对话或刷新页面重试'),
        ('本次调用?${ activeSpecialists', '本次调用${activeSpecialists'),
        
        # IntentClassifierDebugView.vue
        ('意图分类器调?/h1>', '意图分类器调试</h1>'),
        ('两阶段分类效?', '两阶段分类效果'),
        ('特殊处理流?', '特殊处理流程'),
        ('?置信度= 匹配?× 0.3 + 0.4', '• 置信度= 匹配度× 0.3 + 0.4'),
        
        # FinancialHealthView.vue
        ('异常预?', '异常预警'),
        ('健康状?', '健康状况'),
        ('利润? {{ formatPercent', '利润率 {{ formatPercent'),
        ('净现金?', '净现金流'),
        ('最近异?', '最近异常'),
        ('检测? {{ anomaly', '检测值 {{ anomaly'),
        ('资产回报?', '资产回报率'),
        ('净资产回报?', '净资产回报率'),
        ('期望? {{ anomaly', '期望值 {{ anomaly'),
        ('开始日?', '开始日期'),
        
        # FinancialDataEntryView.vue
        ('导入完成，但?${result', '导入完成，但有${result'),
        ('系统自动识别?${detectedCount} 个财务字段', '系统自动识别了${detectedCount}个财务字段'),
        ('上传完成，但?${uploadErrors', '上传完成，但有${uploadErrors'),
        ('税务智能分?', '税务智能分析'),
        ('年销售额?00万，应纳税所得额?00万', '年销售额<100万，应纳税所得额<100万'),
        ('周期开始日?', '周期开始日期'),
        ('（年销售额?00万', '（年销售额<100万'),
        ('应纳税所得额?00万）', '应纳税所得额<100万）'),
        ('总支?(?', '总支出（元）'),
        ('增值税?', '增值税'),
        ('企业所得税?', '企业所得税'),
        ('保存?..', '保存中...'),
        ('销?${ formData', '销项${formData'),
        ('智能识别</strong>：系统自动识别Excel列名，无需严格按模板格?', '智能识别</strong>：系统自动识别Excel列名，无需严格按模板格式'),
        ('支持中文列名（如：总收入、应税销售额、税额等?', '支持中文列名（如：总收入、应税销售额、税额等）'),
        ('支持 .xlsx ?.xls 格式?Excel', '支持 .xlsx 和 .xls 格式的Excel'),
        ('文件大小建议不超?5MB', '文件大小建议不超过5MB'),
        ('每行数据将作为一条财务记录导?', '每行数据将作为一条财务记录导入'),
        ('拖拽到此?', '拖拽到此区域'),
        ('导入?..', '导入中...'),
        ('开始导?', '开始导入'),
        
        # ContractReviewView.vue
        ('请输入合同文?)', '请输入合同文本）'),
        ('确定要删除这条分析记录吗?', '确定要删除这条分析记录吗？'),
        ('高风险合?', '高风险合同'),
        ('低风险合?', '低风险合同'),
        ('最近审?', '最近审核'),
        ('相对?', '相对风险'),
        ('有效?', '有效期'),
        ('不利条?', '不利条款'),
        ('低风?', '低风险'),
        ('相似? {{', '相似度 {{'),
        ('显著差?', '显著差异'),
        ('标准模板参?', '标准模板参考'),
        ('次使?', '次使用'),
        ('开始对?', '开始对话'),
        ('请输入合同金?', '请输入合同金额'),
        ('请粘贴合同文本内?', '请粘贴合同文本内容'),
        ('开始审?', '开始审核'),
        
        # ChatLogsView.vue
        ('条记?', '条记录'),
        ('选择企业?', '选择企业'),
        ('显示在这?', '显示在这里'),
        ('企业名称?', '企业名称：'),
        ('邀请码?', '邀请码：'),
        ('消息?', '消息数'),
        ('无标?', '无标题'),
        ('上一?', '上一页'),
        ('下一?', '下一页'),
        ('普通用户统?', '普通用户统计'),
        ('Token 消?', 'Token 消费'),
        ('成功?', '成功率'),
    ]
    
    for wrong, correct in fixes:
        content = content.replace(wrong, correct)
    
    if content != original:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    return False

def main():
    views_dir = r'D:\Python\Codebase\My_rag\rag_frontend\src\views'
    
    files = [
        'TestDataGuideView.vue',
        'NotificationCenterView.vue',
        'MultiAgentChatView.vue',
        'IntentClassifierDebugView.vue',
        'FinancialHealthView.vue',
        'FinancialDataEntryView.vue',
        'ContractReviewView.vue',
        'ChatLogsView.vue',
    ]
    
    fixed_count = 0
    for filename in files:
        filepath = os.path.join(views_dir, filename)
        if os.path.exists(filepath):
            if fix_file(filepath):
                print(f'Fixed: {filename}')
                fixed_count += 1
            else:
                print(f'No changes: {filename}')
    
    print(f'\nDone! Fixed {fixed_count} files.')

if __name__ == '__main__':
    main()
