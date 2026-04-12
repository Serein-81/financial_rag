# -*- coding: utf-8 -*-
import os

def fix_file(filepath):
    """修复单个文件中的所有乱码"""
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()
    
    original = content
    
    fixes = [
        # ChatLogsView.vue
        ('企业用户?', '企业用户数'),
        ('活跃用户?', '活跃用户数'),
        ('总Token消?', '总Token消费'),
        ('加载?..', '加载中...'),
        ('管理员统?', '管理员统计'),
        
        # FinancialDataEntryView.vue
        ('可享受企业所得税优惠政策?', '可享受企业所得税优惠政策）'),
        ('销?${ formData', '销项${formData'),
        
        # MultiAgentChatView.vue
        ('继续输入新的问题，或者等待系统自动恢复?,', '继续输入新的问题，或者等待系统自动恢复）'),
        ('请求在?{currentStage', '请求在「{currentStage'),
        ('（无内容?}', '（无内容）}'),
        ('如有需要可以重新发起请求?', '如有需要可以重新发起请求）'),
        ('本次调用?{{ activeSpecialists', '本次调用{{activeSpecialists'),
        
        # TestDataGuideView.vue
        ('应税销售额?<br/>', '应税销售额<br/>'),
        
        # AuditResultView.vue
        ('审查进行?..', '审查进行中...'),
        ('请稍?', '请稍候'),
        ('出错?/h3>', '出错啦</h3>'),
        ('检测冲?', '检测冲突'),
        ('综合风险?', '综合风险'),
        ('风险? {{', '风险值 {{'),
        ('冲突检?({{', '冲突检测（{{'),
        
        # SecurityAuditView.vue
        ('最?天事件趋?', '最近7天事件趋势'),
        
        # HITLApprovalView.vue
        ('待审?,', '待审核，'),
        ('已批?,', '已批准，'),
        ('已拒?,', '已拒绝，'),
        ('已超?,', '已超时，'),
        ('待审?, badge:', '待审核， badge:'),
        ('处理完?', '处理完成'),
        ('状?/th>', '状态</th>'),
        ('申请?/th>', '申请人</th>'),
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
        'ChatLogsView.vue',
        'FinancialDataEntryView.vue',
        'MultiAgentChatView.vue',
        'TestDataGuideView.vue',
        'AuditResultView.vue',
        'SecurityAuditView.vue',
        'HITLApprovalView.vue',
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
