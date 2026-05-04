# Enterprise Profile Dimensions for Policy Matching

This reference explains how enterprise characteristics map to tax policy matching criteria.

## Dimension 1: Industry (行业)

| Industry | Applicable Policies |
|----------|-------------------|
| 信息技术 / 软件 | 高新技术企业15%税率, 软件企业两免三减半, 研发费用加计扣除 |
| 生物医药 / 医疗 | 高新技术企业15%税率, 研发费用加计扣除 |
| 先进制造 | 高新技术企业15%税率, 研发费用加计扣除, 固定资产加速折旧 |
| 集成电路 / 半导体 | 集成电路企业十年免税, 高新技术企业15%税率 |
| 新能源 / 节能环保 | 高新技术企业15%税率, 环境保护节能节水项目所得减免 |
| 金融 | 无特殊行业优惠（一般企业25%税率） |
| 教育 / 医疗 / 养老 | 非营利组织免税资格, 符合条件的收入免征企业所得税 |
| 农业 | 农产品初加工免征企业所得税, 农业生产资料免征增值税 |

## Dimension 2: Region (地区)

| Region | Applicable Policies |
|--------|-------------------|
| 海南 | 海南自贸港15%税率, 新增境外直接投资所得免征 |
| 西部省份(重庆/四川/贵州/云南/陕西/甘肃/青海/宁夏/新疆/西藏/内蒙/广西) | 西部大开发15%税率 |
| 上海临港 | 临港新片区15%税率(特定产业) |
| 粤港澳大湾区(广州/深圳/珠海/东莞等) | 大湾区个人所得税优惠(境外高端人才), 横琴粤澳深度合作区15%税率 |
| 北京/上海/广州/深圳 | 无特殊地区优惠(按国家标准) |
| 其他地区 | 一般适用国家统一政策 |

## Dimension 3: Enterprise Scale (规模)

| Scale Criteria | Classification | Applicable Policies |
|---------------|---------------|-------------------|
| 营收<300万 或 人数<20人 | 微型 | 小微企业优惠, 增值税小规模减免 |
| 营收300-2000万 或 人数20-100人 | 小型 | 小微企业优惠, 增值税小规模减免 |
| 营收2000万-4亿 或 人数100-500人 | 中型 | 一般纳税人(标准税率) |
| 营收>4亿 或 人数>500人 | 大型 | 一般纳税人(标准税率), 可能适用特定产业优惠 |

## Dimension 4: Tax Types (税种)

| Tax Type | Key Policies |
|----------|-------------|
| 增值税 | 一般纳税人13%/9%/6%税率, 小规模1%征收率, 留抵退税, 出口退税 |
| 企业所得税 | 25%标准税率, 高新技术15%, 小型微利优惠, 研发费用加计扣除 |
| 个人所得税 | 3%-45%累进税率, 专项附加扣除, 年终奖单独计税 |
| 消费税 | 特定消费品(烟/酒/化妆品等)从价/从量征收 |
| 房产税 | 自用1.2%, 出租12% |

## Dimension 5: Special Qualifications (特殊资质)

| Qualification | Policy Benefit |
|--------------|---------------|
| 高新技术企业 | 企业所得税15%税率（资格有效期3年，需复审） |
| 软件企业 | 两免三减半（自获利年度起） |
| 集成电路企业 | 十年/五年/两免三减半（按线宽和经营期） |
| 技术先进型服务企业 | 企业所得税15%税率 |
| 小型微利企业 | 应纳税所得额分段减免 |
| 增值税小规模纳税人 | 3%→1%征收率优惠 |
| 非营利组织 | 符合条件的收入免征企业所得税 |

## Dimension 6: Keywords & Business Scope (关键词与经营范围)

| Keyword/Scope | Potential Policy Match |
|--------------|----------------------|
| 研发 / 技术开发 / 创新 | 研发费用加计扣除(100%) |
| 出口 / 外贸 | 出口退税, 跨境应税行为零税率 |
| 软件 / 软件开发 | 软件产品增值税即征即退 |
| 技术转让 | 技术转让所得减免(500万以内免税) |
| 节能环保 / 新能源 | 环境保护节能节水项目所得减免 |
| 基础设施 / 港口/机场 | 基础设施项目所得减免 |
| 创投 / 投资 | 创业投资企业按投资额70%抵扣应纳税所得额 |

## Matching Logic

The policy matching engine uses a weighted scoring system:

1. Industry match: +3 points (highest weight)
2. Region match: +3 points
3. Keyword match: +3 points
4. Qualification match: +4 points (highest single weight)
5. Tax type match: +2 points
6. Scale match: +2 points

- Score >= 4: Highly likely to qualify (✅)
- Score 2-3: Potentially applicable (⚠️ check conditions)
- Score < 2: Unlikely to apply
