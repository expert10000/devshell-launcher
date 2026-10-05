import { useMemo, useState } from 'react'
import { CodeFilePreview } from './DataFilePreview'
import { buildStaticHtmlPreview } from './htmlPreview'

export function HtmlFilePreview({ text, filename }: { text: string; filename: string }) {
  const [rendered, setRendered] = useState(false)
  const preview = useMemo(() => rendered ? buildStaticHtmlPreview(text) : undefined, [text, rendered])
  return <div className="html-preview">
    <div className="html-preview-toolbar" aria-label="HTML view mode"><button aria-pressed={!rendered} onClick={() => setRendered(false)}>HTML source</button><button aria-pressed={rendered} onClick={() => setRendered(true)}>Preview HTML</button><span>Static, offline preview</span></div>
    {preview ? <><iframe className="html-preview-frame" title={`Static HTML preview: ${filename}`} sandbox="" src="about:blank" srcDoc={preview.srcDoc} referrerPolicy="no-referrer" allow="camera 'none'; microphone 'none'; geolocation 'none'; fullscreen 'none'; clipboard-read 'none'; clipboard-write 'none'" /><p className="workspace-view-caption">Static markup and inline CSS only. Scripts, links, forms, embedded frames, and external resources are removed or blocked.{preview.omitted > 0 ? ` ${preview.omitted} elements or attributes omitted.` : ''}</p>{preview.limited && <p>Static preview limited to 4000 nodes and depth 32. Use HTML source for the bounded file contents.</p>}</> : <CodeFilePreview text={text} filename={filename} />}
  </div>
}
