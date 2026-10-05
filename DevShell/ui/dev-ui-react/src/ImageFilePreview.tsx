import { useEffect, useRef, useState } from 'react'

export function ImageFilePreview({ image, paths, onSelect, onError }: {
  image: { path: string; dataUrl: string; mimeType: string; size: number }; paths: string[]; onSelect: (path: string) => void; onError: () => void
}) {
  const viewport = useRef<HTMLDivElement>(null)
  const drag = useRef<{ id: number; x: number; y: number; left: number; top: number } | null>(null)
  const [dimensions, setDimensions] = useState({ width: 0, height: 0 })
  const [bounds, setBounds] = useState({ width: 300, height: 300 })
  const [zoom, setZoom] = useState<number | 'fit'>('fit')
  const [dragging, setDragging] = useState(false)
  useEffect(() => {
    const element = viewport.current; if (!element) return
    const observer = new ResizeObserver(() => setBounds({ width: element.clientWidth, height: element.clientHeight }))
    observer.observe(element); return () => observer.disconnect()
  }, [])
  const fit = dimensions.width && dimensions.height ? Math.max(.01, Math.min(1, Math.max(1, bounds.width - 28) / dimensions.width, Math.max(1, bounds.height - 28) / dimensions.height)) : 1
  const scale = zoom === 'fit' ? fit : zoom
  const index = paths.indexOf(image.path)
  function changeZoom(multiplier: number) { setZoom(Math.min(8, Math.max(.1, scale * multiplier))) }
  function release() { drag.current = null; setDragging(false) }
  return <>
    <div className="image-preview-toolbar" aria-label="Image controls">
      <button disabled={index <= 0} onClick={() => onSelect(paths[index - 1])}>Previous image</button>
      <button disabled={index < 0 || index >= paths.length - 1} onClick={() => onSelect(paths[index + 1])}>Next image</button>
      <button aria-label="Zoom out" disabled={zoom !== 'fit' && zoom <= .1} onClick={() => changeZoom(1 / 1.25)}>-</button>
      <output aria-label="Image zoom">{Math.round(scale * 100)}%</output>
      <button aria-label="Zoom in" disabled={scale >= 8} onClick={() => changeZoom(1.25)}>+</button>
      <button aria-pressed={zoom === 'fit'} onClick={() => { setZoom('fit'); viewport.current?.scrollTo(0, 0) }}>Fit image</button>
      <button aria-pressed={zoom === 1} onClick={() => setZoom(1)}>100%</button>
    </div>
    <div ref={viewport} className={`files-image-preview image-pan-viewport ${dragging ? 'dragging' : ''}`} tabIndex={0} aria-label="Image viewport. Drag to pan, use arrow keys to scroll, plus or minus to zoom, Home to fit."
      onPointerDown={event => {
        if (event.button !== 0) return
        const element = event.currentTarget
        drag.current = { id: event.pointerId, x: event.clientX, y: event.clientY, left: element.scrollLeft, top: element.scrollTop }
        element.setPointerCapture(event.pointerId); setDragging(true); element.focus(); event.preventDefault()
      }}
      onPointerMove={event => { const origin = drag.current; if (!origin || origin.id !== event.pointerId) return; event.currentTarget.scrollLeft = origin.left - (event.clientX - origin.x); event.currentTarget.scrollTop = origin.top - (event.clientY - origin.y) }}
      onPointerUp={event => { if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId); release() }}
      onPointerCancel={release} onLostPointerCapture={release}
      onKeyDown={event => { if (event.key === '+' || event.key === '=') { event.preventDefault(); changeZoom(1.25) } else if (event.key === '-') { event.preventDefault(); changeZoom(1 / 1.25) } else if (event.key === 'Home') { event.preventDefault(); setZoom('fit'); event.currentTarget.scrollTo(0, 0) } }}>
      <div className="image-pan-canvas" style={{ width: dimensions.width ? Math.max(bounds.width - 28, dimensions.width * scale) : undefined, height: dimensions.height ? Math.max(bounds.height - 28, dimensions.height * scale) : undefined }}>
        <img src={image.dataUrl} alt={image.path} draggable={false} style={{ width: dimensions.width ? dimensions.width * scale : undefined, height: dimensions.height ? dimensions.height * scale : undefined }} onLoad={event => setDimensions({ width: event.currentTarget.naturalWidth, height: event.currentTarget.naturalHeight })} onError={onError} />
      </div>
    </div>
    <p className="workspace-view-caption">{image.mimeType} / {(image.size / 1024).toFixed(1)} KB{dimensions.width > 0 && ` / ${dimensions.width} x ${dimensions.height}`} / {index >= 0 ? `${index + 1} of ${paths.length} visible folder images` : 'single image'} / drag to pan; zoom is not saved</p>
  </>
}
