import { Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType, Table, TableRow, TableCell, WidthType, BorderStyle } from 'docx'
import { format } from 'date-fns'

export interface PolicyData {
  title?: string
  policy_title?: string
  summary?: string
  source?: string
  policy_source?: string
  department?: string
  publish_date?: string
  effective_date?: string
  tags?: string[]
  match_score?: number
  conditions?: string[]
  benefits?: string[]
}

export interface ExportData {
  policies: PolicyData[]
  exportTime?: string
  totalCount?: number
  query?: string
  enterpriseId?: string
}

export function useWordGenerator() {

  function formatDate(dateStr?: string): string {
    if (!dateStr) return '未知'
    try {
      const date = new Date(dateStr)
      return format(date, 'yyyy-MM-dd')
    } catch {
      return dateStr
    }
  }

  function createTitle(title: string): Paragraph {
    return new Paragraph({
      text: title,
      heading: HeadingLevel.TITLE,
      alignment: AlignmentType.CENTER,
      spacing: {
        after: 400
      }
    })
  }

  function createHeading(text: string, level: HeadingLevel = HeadingLevel.HEADING_1): Paragraph {
    return new Paragraph({
      text: text,
      heading: level,
      spacing: {
        before: 400,
        after: 200
      }
    })
  }

  function createParagraph(text: string, bold: boolean = false): Paragraph {
    return new Paragraph({
      children: [
        new TextRun({
          text: text,
          bold: bold,
          size: 24
        })
      ],
      spacing: {
        after: 200
      }
    })
  }

  function createBulletPoint(text: string): Paragraph {
    return new Paragraph({
      children: [
        new TextRun({
          text: `• ${text}`,
          size: 22
        })
      ],
      spacing: {
        after: 100
      }
    })
  }

  function createInfoTable(data: { label: string; value: string }[]): Table {
    const rows = data.map(item =>
      new TableRow({
        children: [
          new TableCell({
            children: [new Paragraph({
              children: [new TextRun({ text: item.label, bold: true, size: 22 })],
              spacing: { before: 100, after: 100 }
            })],
            width: { size: 25, type: WidthType.PERCENTAGE },
            shading: { fill: 'E8F5E9' }
          }),
          new TableCell({
            children: [new Paragraph({
              children: [new TextRun({ text: item.value, size: 22 })],
              spacing: { before: 100, after: 100 }
            })],
            width: { size: 75, type: WidthType.PERCENTAGE }
          })
        ]
      })
    )

    return new Table({
      rows: rows,
      width: { size: 100, type: WidthType.PERCENTAGE }
    })
  }

  function createPolicyCard(policy: PolicyData, index: number): Paragraph[] {
    const paragraphs: Paragraph[] = []

    paragraphs.push(createHeading(`${index + 1}. ${policy.policy_title || policy.title || '未知政策'}`, HeadingLevel.HEADING_2))

    const details: { label: string; value: string }[] = []
    if (policy.policy_source || policy.source) {
      details.push({ label: '来源', value: policy.policy_source || policy.source || '' })
    }
    if (policy.department) {
      details.push({ label: '发布部门', value: policy.department })
    }
    if (policy.publish_date) {
      details.push({ label: '发布日期', value: formatDate(policy.publish_date) })
    }
    if (policy.effective_date) {
      details.push({ label: '生效日期', value: formatDate(policy.effective_date) })
    }

    if (details.length > 0) {
      paragraphs.push(createInfoTable(details))
    }

    if (policy.summary) {
      paragraphs.push(createParagraph('摘要：', true))
      paragraphs.push(createParagraph(policy.summary))
    }

    if (policy.tags && policy.tags.length > 0) {
      paragraphs.push(createParagraph('标签：', true))
      const tagText = policy.tags.slice(0, 5).join('、 ')
      paragraphs.push(createParagraph(tagText))
    }

    if (policy.match_score !== undefined) {
      paragraphs.push(createParagraph(`匹配度：${(policy.match_score * 100).toFixed(1)}%`))
    }

    if (policy.conditions && policy.conditions.length > 0) {
      paragraphs.push(createParagraph('适用条件：', true))
      policy.conditions.slice(0, 3).forEach(condition => {
        paragraphs.push(createBulletPoint(condition))
      })
    }

    if (policy.benefits && policy.benefits.length > 0) {
      paragraphs.push(createParagraph('政策优惠：', true))
      policy.benefits.slice(0, 3).forEach(benefit => {
        paragraphs.push(createBulletPoint(benefit))
      })
    }

    paragraphs.push(new Paragraph({ text: '' }))

    return paragraphs
  }

  async function generatePolicyReport(data: ExportData): Promise<Blob> {
    const children: Paragraph[] = []

    children.push(createTitle('政策报告'))

    children.push(createParagraph(`生成时间：${formatDate(data.exportTime || new Date().toISOString())}`))
    children.push(createParagraph(`政策总数：${data.totalCount || data.policies.length}`))
    if (data.query) {
      children.push(createParagraph(`查询条件：${data.query}`))
    }

    children.push(new Paragraph({ text: '' }))

    children.push(createHeading('政策列表', HeadingLevel.HEADING_1))

    data.policies.forEach((policy, index) => {
      const policyParagraphs = createPolicyCard(policy, index)
      children.push(...policyParagraphs)
    })

    children.push(new Paragraph({ text: '' }))
    children.push(createParagraph('— 报告结束 —', false))

    const doc = new Document({
      sections: [{
        properties: {},
        children: children
      }]
    })

    return await Packer.toBlob(doc)
  }

  return {
    generatePolicyReport,
    formatDate
  }
}
