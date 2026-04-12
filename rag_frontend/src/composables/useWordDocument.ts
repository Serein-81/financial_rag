import { ref } from 'vue'
import mammoth from 'mammoth'
import DOMPurify from 'dompurify'

export function useWordDocument() {
  const isConverting = ref(false)
  const conversionError = ref<string | null>(null)

  async function convertToHtml(blob: Blob): Promise<string> {
    isConverting.value = true
    conversionError.value = null

    try {
      console.log('[WordPreview] Starting conversion...')
      
      const arrayBuffer = await blob.arrayBuffer()
      
      const result = await mammoth.convertToHtml(
        { arrayBuffer },
        {
          styleMap: [
            "p[style-name='Heading 1'] => h1:fresh",
            "p[style-name='Heading 2'] => h2:fresh",
            "p[style-name='Heading 3'] => h3:fresh",
            "p[style-name='Title'] => h1.document-title:fresh",
            "b => strong",
            "i => em",
            "u => u",
          ]
        }
      )

      if (result.messages && result.messages.length > 0) {
        console.log('[WordPreview] Conversion messages:', result.messages)
      }

      const sanitizedHtml = DOMPurify.sanitize(result.value, {
        ADD_TAGS: ['img'],
        ADD_ATTR: ['target', 'class', 'style'],
      })

      console.log('[WordPreview] Conversion successful')
      return sanitizedHtml
      
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Word 文档转换失败'
      console.error('[WordPreview] Conversion error:', error)
      conversionError.value = errorMessage
      throw new Error(errorMessage)
    } finally {
      isConverting.value = false
    }
  }

  async function convertToHtmlWithStyles(blob: Blob): Promise<string> {
    const htmlContent = await convertToHtml(blob)
    
    return `
      <!DOCTYPE html>
      <html>
        <head>
          <meta charset="UTF-8">
          <meta name="viewport" content="width=device-width, initial-scale=1.0">
          <style>
            * {
              margin: 0;
              padding: 0;
              box-sizing: border-box;
            }
            html, body {
              width: 100%;
              height: 100%;
              overflow: auto;
            }
            body {
              font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 
                           'Microsoft YaHei', 'Helvetica Neue', Helvetica, Arial, sans-serif;
              font-size: 15px;
              line-height: 1.8;
              color: #334155;
              background: #fff;
              padding: 30px 40px;
            }
            .document-content {
              max-width: 1000px;
              margin: 0 auto;
              min-height: calc(100vh - 60px);
            }
            h1, h2, h3, h4, h5, h6 {
              margin-top: 32px;
              margin-bottom: 16px;
              font-weight: 600;
              line-height: 1.3;
              color: #1e293b;
            }
            h1 {
              font-size: 2.2em;
              border-bottom: 3px solid #10b981;
              padding-bottom: 0.4em;
              margin-top: 0;
            }
            h2 {
              font-size: 1.6em;
              border-bottom: 2px solid #e2e8f0;
              padding-bottom: 0.3em;
            }
            h3 {
              font-size: 1.3em;
            }
            h4 {
              font-size: 1.1em;
            }
            p {
              margin: 20px 0;
              text-align: justify;
            }
            ul, ol {
              margin: 20px 0;
              padding-left: 2em;
            }
            li {
              margin: 10px 0;
            }
            table {
              border-collapse: collapse;
              margin: 24px 0;
              width: 100%;
              box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
            }
            th, td {
              border: 1px solid #cbd5e1;
              padding: 12px 16px;
              text-align: left;
            }
            th {
              background: linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%);
              font-weight: 600;
              color: #166534;
            }
            tr:nth-child(even) {
              background: #f8fafc;
            }
            tr:hover {
              background: #f1f5f9;
            }
            img {
              max-width: 100%;
              height: auto;
              display: block;
              margin: 20px 0;
              border-radius: 8px;
              box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
            }
            blockquote {
              margin: 24px 0;
              padding: 16px 24px;
              border-left: 5px solid #10b981;
              background: linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%);
              color: #166534;
              border-radius: 0 8px 8px 0;
            }
            code {
              background: #f1f5f9;
              padding: 3px 8px;
              border-radius: 4px;
              font-family: 'Courier New', Consolas, monospace;
              font-size: 0.9em;
              color: #be185d;
            }
            pre {
              background: linear-gradient(135deg, #1e293b 0%, #334155 100%);
              color: #f1f5f9;
              padding: 20px;
              border-radius: 12px;
              overflow-x: auto;
              margin: 24px 0;
              box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
            }
            pre code {
              background: transparent;
              padding: 0;
              color: inherit;
              font-size: 0.95em;
            }
            strong {
              font-weight: 600;
              color: #1e293b;
            }
            em {
              color: #64748b;
              font-style: italic;
            }
            a {
              color: #10b981;
              text-decoration: none;
              border-bottom: 1px solid transparent;
              transition: all 0.2s;
            }
            a:hover {
              color: #059669;
              border-bottom-color: #059669;
            }
            hr {
              border: none;
              height: 2px;
              background: linear-gradient(90deg, transparent, #e2e8f0, transparent);
              margin: 32px 0;
            }
          </style>
        </head>
        <body>
          <div class="document-content">
            ${htmlContent}
          </div>
        </body>
      </html>
    `
  }

  return {
    isConverting,
    conversionError,
    convertToHtml,
    convertToHtmlWithStyles,
  }
}
