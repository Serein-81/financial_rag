# 财务数据Excel上传接口使用指南

## 📋 概述

本接口允许用户通过上传Excel文件批量录入财务数据，支持数据验证、错误提示和重复数据处理。

## 🔗 API接口

### 1. 下载Excel模板
**接口**: `GET /api/v1/financial-data/download-template`

**说明**: 下载标准财务数据Excel模板文件

**响应**: 返回.xlsx格式的Excel文件

**示例**:
```bash
curl -X GET "http://localhost:8000/api/v1/financial-data/download-template" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  --output financial_data_template.xlsx
```

---

### 2. 上传财务数据Excel
**接口**: `POST /api/v1/financial-data/upload-excel`

**Content-Type**: `multipart/form-data`

**参数**:

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| file | File | ✅ | Excel文件(.xlsx/.xls) |
| fiscal_year | int | ✅ | 财务年度(2000-2100) |
| period_type | string | ❌ | 周期类型(yearly/quarterly/monthly)，默认yearly |
| period_start | string | ✅ | 周期开始日期(YYYY-MM-DD) |
| period_end | string | ✅ | 周期结束日期(YYYY-MM-DD) |
| overwrite_existing | bool | ❌ | 是否覆盖已存在的数据，默认false |

**成功响应示例**:
```json
{
  "success": true,
  "message": "成功导入3条财务数据记录",
  "file_id": "550e8400-e29b-41d4-a716-446655440000",
  "preview_data": {
    "fiscal_year": 2024,
    "total_revenue": 1250000.0,
    "taxable_sales": 1125000.0
  },
  "validation_errors": []
}
```

**验证失败响应示例**:
```json
{
  "success": false,
  "message": "Excel数据验证失败，发现2个错误",
  "file_id": null,
  "preview_data": null,
  "validation_errors": [
    "第2行: 财务年度必须在2000-2100之间",
    "第3行: 总收入不能为负数"
  ]
}
```

**错误响应示例**:
```json
{
  "detail": "只支持.xlsx或.xls格式的Excel文件"
}
```

---

## 📊 Excel文件格式要求

### 必需列（21列）

| 列名 | 数据类型 | 说明 | 示例 |
|------|----------|------|------|
| fiscal_year | int | 财务年度 | 2024 |
| period_type | string | 周期类型 | yearly/quarterly/monthly |
| period_start | string | 周期开始日期 | 2024-01-01 |
| period_end | string | 周期结束日期 | 2024-12-31 |
| total_revenue | float | 总收入 | 1250000.00 |
| taxable_sales | float | 应税销售额 | 1125000.00 |
| tax_free_sales | float | 免税销售额 | 125000.00 |
| total_expenses | float | 总支出 | 750000.00 |
| deductible_expenses | float | 可抵扣支出 | 600000.00 |
| non_deductible_expenses | float | 不可抵扣支出 | 150000.00 |
| input_tax | float | 进项税额 | 97500.00 |
| output_tax | float | 销项税额 | 146250.00 |
| vat_rate | float | 增值税率(0-1) | 0.13 |
| taxable_income | float | 应纳税所得额 | 375000.00 |
| corporate_tax_rate | float | 企业所得税率(0-1) | 0.25 |
| is_small_enterprise | bool | 是否小微企业 | false |
| total_payroll | float | 工资薪金总额 | 500000.00 |
| special_deductions | float | 专项附加扣除 | 50000.00 |
| total_invoices | int | 发票总数 | 120 |
| input_invoice_count | int | 进项发票数 | 80 |
| output_invoice_count | int | 销项发票数 | 40 |

---

## ✅ 数据验证规则

### 必填字段验证
- `fiscal_year`: 必须在2000-2100之间
- `period_type`: 必须是yearly/quarterly/monthly之一
- `period_start` 和 `period_end`: 必须是有效的日期格式(YYYY-MM-DD)
- `period_start` 必须早于 `period_end`

### 数值范围验证
- `total_revenue` (总收入): ≥ 0
- `taxable_sales` (应税销售额): ≥ 0
- `tax_free_sales` (免税销售额): ≥ 0
- `vat_rate` (增值税率): 0 ≤ value ≤ 1
- `corporate_tax_rate` (企业所得税率): 0 ≤ value ≤ 1
- `input_tax` (进项税额): ≥ 0
- `output_tax` (销项税额): ≥ 0

### 业务逻辑验证
- `total_revenue` ≥ `taxable_sales` + `tax_free_sales`
- `total_expenses` ≥ `deductible_expenses` + `non_deductible_expenses`

### 数据类型验证
- 数值字段不能为空（会使用默认值0）
- 日期字段必须是可解析的日期格式
- 布尔字段必须是true/false或0/1

---

## 💡 使用示例

### Python requests示例
```python
import requests

# 1. 下载模板
response = requests.get(
    "http://localhost:8000/api/v1/financial-data/download-template",
    headers={"Authorization": "Bearer YOUR_TOKEN"}
)
with open("template.xlsx", "wb") as f:
    f.write(response.content)

# 2. 上传填好的Excel文件
url = "http://localhost:8000/api/v1/financial-data/upload-excel"
files = {"file": open("your_financial_data.xlsx", "rb")}
data = {
    "fiscal_year": 2024,
    "period_type": "yearly",
    "period_start": "2024-01-01",
    "period_end": "2024-12-31",
    "overwrite_existing": "false"
}
headers = {"Authorization": "Bearer YOUR_TOKEN"}

response = requests.post(url, files=files, data=data, headers=headers)
print(response.json())
```

### JavaScript fetch示例
```javascript
// 上传Excel文件
const formData = new FormData();
formData.append('file', fileInput.files[0]);
formData.append('fiscal_year', '2024');
formData.append('period_type', 'yearly');
formData.append('period_start', '2024-01-01');
formData.append('period_end', '2024-12-31');
formData.append('overwrite_existing', 'false');

const response = await fetch('/api/v1/financial-data/upload-excel', {
    method: 'POST',
    headers: {
        'Authorization': 'Bearer YOUR_TOKEN'
    },
    body: formData
});

const result = await response.json();
console.log(result);
```

---

## ⚠️ 常见错误及解决方案

### 1. 文件格式错误
**错误**: `只支持.xlsx或.xls格式的Excel文件`
**解决**: 确保上传的是Excel文件，不是CSV或其他格式

### 2. Excel解析失败
**错误**: `Excel文件格式错误，无法解析`
**解决**: 
- 检查Excel文件是否损坏
- 尝试用Excel重新保存文件
- 确保使用.xlsx格式（.xls可能不支持）

### 3. 缺少必需列
**错误**: `Excel文件缺少必需列: 总收入, 应税销售额`
**解决**: 确保Excel包含所有21个必需列

### 4. 数据验证失败
**错误**: 返回的validation_errors列表包含错误信息
**解决**: 
- 检查每一行的数据是否符合验证规则
- 查看错误信息中指出的行号和数据问题
- 修正后重新上传

### 5. 数据已存在
**响应**: `跳过2条已存在的数据`
**解决**: 
- 使用 `overwrite_existing=true` 覆盖已存在的数据
- 或修改period_type/year为新的组合

---

## 🔄 批量导入最佳实践

### 1. 准备数据
- 使用下载的模板文件
- 按列正确填写数据
- 确保数据格式正确

### 2. 数据验证
- 先用小批量数据测试接口
- 检查返回的validation_errors
- 修正所有错误后再批量上传

### 3. 数据备份
- 上传前备份现有数据
- 使用 `overwrite_existing=false` 避免意外覆盖

### 4. 监控导入结果
- 检查返回的success字段
- 记录跳过的数据并手动处理
- 验证导入的数据是否正确

---

## 📞 技术支持

如有问题，请检查：
1. API服务是否正常运行
2. 请求参数是否正确
3. Excel文件格式是否符合要求
4. 认证Token是否有效
