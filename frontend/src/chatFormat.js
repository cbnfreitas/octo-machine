/**
 * Escape HTML, then apply a tiny subset: **bold** and newlines -> <br>.
 * Safe for v-html when the source is untrusted (e.g. LLM output).
 */
export function formatChatHtml(text) {
  if (text == null || text === '') return ''
  let s = String(text)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
  s = s.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
  s = s.replace(/\n/g, '<br />')
  return s
}
