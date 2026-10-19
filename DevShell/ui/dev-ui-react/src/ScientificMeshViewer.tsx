import { useEffect, useMemo, useRef, useState } from 'react'
import type { ScientificArtifactPreview, ScientificMeshPreview } from './useScientificRuntime'
import './ScientificArtifacts.css'

export type Camera = { yaw: number; pitch: number; zoom: number; wire: boolean }
export const initialCamera: Camera = { yaw: 0.6, pitch: 0.35, zoom: 0.85, wire: false }
type Layer = { id: string; name: string; mesh: ScientificMeshPreview; color: [number, number, number] }
type Display = { visible: Record<string, boolean>; opacity: Record<string, number>; clip: boolean; axis: number; fraction: number; reverse: boolean }
const solidDisplay: Display = { visible: {}, opacity: {}, clip: false, axis: 0, fraction: 0.5, reverse: false }
const colors: Record<string, [number, number, number]> = { a: [0.96, 0.59, 0.23], b: [0.67, 0.46, 0.96], result: [0.2, 0.83, 0.9] }
const vertexShader = `
attribute vec3 position; attribute vec3 normal;
uniform vec3 center; uniform float scale; uniform vec2 angle; uniform float zoom; uniform float aspect;
varying vec3 lightingNormal; varying vec3 worldPosition;
vec3 rotate(vec3 p) {
  float cy=cos(angle.x), sy=sin(angle.x), cx=cos(angle.y), sx=sin(angle.y);
  vec3 q=vec3(cy*p.x+sy*p.z,p.y,-sy*p.x+cy*p.z);
  return vec3(q.x,cx*q.y-sx*q.z,sx*q.y+cx*q.z);
}
void main() { vec3 p=rotate((position-center)*scale); lightingNormal=rotate(normal); worldPosition=position;
  float fit=min(1.0,aspect);
  gl_Position=vec4(p.x*zoom*fit/aspect,p.y*zoom*fit,-p.z*0.2,1.0); }
`
const fragmentShader = `
precision mediump float; uniform vec3 color; uniform float opacity;
uniform float clipEnabled; uniform vec3 clipNormal; uniform float clipPosition; uniform float clipDirection;
varying vec3 lightingNormal; varying vec3 worldPosition;
void main() {
  if (clipEnabled > 0.5 && (dot(worldPosition,clipNormal)-clipPosition)*clipDirection > 0.0) discard;
  float light=0.3+0.7*abs(dot(normalize(lightingNormal),normalize(vec3(0.4,0.7,1.0))));
  gl_FragColor=vec4(color*light,opacity);
}
`

function MeshViewport({ layers, display, camera, setCamera, bounds, title }: {
  layers: Layer[]; display: Display; camera: Camera; setCamera: React.Dispatch<React.SetStateAction<Camera>>; bounds: number[]; title: string
}) {
  const canvas = useRef<HTMLCanvasElement>(null)
  const live = useRef({ display, camera }); live.current = { display, camera }
  const draw = useRef<(() => void) | null>(null)
  const pointer = useRef<{ x: number; y: number } | null>(null)
  const [error, setError] = useState('')
  useEffect(() => {
    const element = canvas.current
    if (!element) return
    setError('')
    if (layers.some(layer => !Array.isArray(layer.mesh.positions) || layer.mesh.positions.length > 108000 || layer.mesh.positions.length % 9 !== 0 || layer.mesh.positions.some(value => !Number.isFinite(value)))) {
      setError('Invalid or oversized preview data.'); return
    }
    const gl = element.getContext('webgl', { antialias: true })
    if (!gl) { setError('WebGL is unavailable. Statistics and saved artifacts remain accessible.'); return }
    const shaders: WebGLShader[] = [], buffers: WebGLBuffer[] = []
    let program: WebGLProgram | null = null
    let observer: ResizeObserver | null = null
    const release = () => { draw.current = null; observer?.disconnect(); buffers.forEach(buffer => gl.deleteBuffer(buffer)); shaders.forEach(shader => gl.deleteShader(shader)); if (program) gl.deleteProgram(program) }
    try {
      const compile = (type: number, source: string) => {
        const shader = gl.createShader(type)
        if (!shader) throw new Error('Cannot allocate preview shader.')
        shaders.push(shader); gl.shaderSource(shader, source); gl.compileShader(shader)
        if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) throw new Error('Cannot compile preview shader.')
        return shader
      }
      program = gl.createProgram()
      if (!program) throw new Error('Cannot allocate preview program.')
      gl.attachShader(program, compile(gl.VERTEX_SHADER, vertexShader)); gl.attachShader(program, compile(gl.FRAGMENT_SHADER, fragmentShader)); gl.linkProgram(program)
      if (!gl.getProgramParameter(program, gl.LINK_STATUS)) throw new Error('Cannot link preview shader.')
      const upload = (data: Float32Array) => {
        const buffer = gl.createBuffer()
        if (!buffer) throw new Error('Cannot allocate preview buffer.')
        buffers.push(buffer); gl.bindBuffer(gl.ARRAY_BUFFER, buffer); gl.bufferData(gl.ARRAY_BUFFER, data, gl.STATIC_DRAW); return buffer
      }
      const geometry = layers.map(layer => {
        const positions = new Float32Array(layer.mesh.positions), normals = new Float32Array(positions.length)
        const edges = new Float32Array(positions.length * 2), edgeNormals = new Float32Array(edges.length)
        for (let i = 0; i < positions.length; i += 9) {
          const ax = positions[i + 3] - positions[i], ay = positions[i + 4] - positions[i + 1], az = positions[i + 5] - positions[i + 2]
          const bx = positions[i + 6] - positions[i], by = positions[i + 7] - positions[i + 1], bz = positions[i + 8] - positions[i + 2]
          const nx = ay * bz - az * by, ny = az * bx - ax * bz, nz = ax * by - ay * bx, length = Math.hypot(nx, ny, nz) || 1
          for (let corner = 0; corner < 3; corner++) normals.set([nx / length, ny / length, nz / length], i + corner * 3)
          for (let edge = 0; edge < 3; edge++) {
            const offset = i * 2 + edge * 6
            edges.set(positions.subarray(i + edge * 3, i + edge * 3 + 3), offset)
            edges.set(positions.subarray(i + ((edge + 1) % 3) * 3, i + ((edge + 1) % 3) * 3 + 3), offset + 3)
            edgeNormals.set([nx / length, ny / length, nz / length, nx / length, ny / length, nz / length], offset)
          }
        }
        return { ...layer, solid: [upload(positions), upload(normals)], wire: [upload(edges), upload(edgeNormals)], count: positions.length / 3 }
      })
      const bind = (name: string, buffer: WebGLBuffer) => { const location = gl.getAttribLocation(program!, name); gl.bindBuffer(gl.ARRAY_BUFFER, buffer); gl.enableVertexAttribArray(location); gl.vertexAttribPointer(location, 3, gl.FLOAT, false, 0, 0) }
      const uniform = (name: string) => gl.getUniformLocation(program!, name)
      const midpoint = [0, 1, 2].map(axis => (bounds[axis * 2] + bounds[axis * 2 + 1]) / 2)
      const extent = Math.hypot(bounds[1] - bounds[0], bounds[3] - bounds[2], bounds[5] - bounds[4]) || 1
      const render = () => {
        const { camera: view, display: style } = live.current
        const ratio = Math.min(window.devicePixelRatio || 1, 2), width = Math.max(1, Math.round(element.clientWidth * ratio)), height = Math.max(1, Math.round(element.clientHeight * ratio))
        if (element.width !== width || element.height !== height) { element.width = width; element.height = height }
        gl.viewport(0, 0, width, height); gl.depthMask(true); gl.clearColor(0.045, 0.065, 0.08, 1); gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT)
        gl.enable(gl.DEPTH_TEST); gl.depthFunc(gl.LEQUAL); gl.disable(gl.CULL_FACE); gl.useProgram(program)
        gl.uniform3fv(uniform('center'), midpoint); gl.uniform1f(uniform('scale'), 1.7 / extent); gl.uniform2f(uniform('angle'), view.yaw, view.pitch)
        gl.uniform1f(uniform('zoom'), view.zoom); gl.uniform1f(uniform('aspect'), width / height)
        gl.uniform1f(uniform('clipEnabled'), style.clip ? 1 : 0)
        gl.uniform3fv(uniform('clipNormal'), [0, 1, 2].map(axis => axis === style.axis ? 1 : 0))
        gl.uniform1f(uniform('clipPosition'), bounds[style.axis * 2] + style.fraction * (bounds[style.axis * 2 + 1] - bounds[style.axis * 2]))
        gl.uniform1f(uniform('clipDirection'), style.reverse ? -1 : 1)
        const visible = geometry.filter(layer => style.visible[layer.id] !== false && (style.opacity[layer.id] ?? 1) > 0 && layer.count > 0)
        const paint = (layer: typeof geometry[number]) => {
          gl.uniform3fv(uniform('color'), layer.color); gl.uniform1f(uniform('opacity'), style.opacity[layer.id] ?? 1)
          const pair = view.wire ? layer.wire : layer.solid; bind('position', pair[0]); bind('normal', pair[1])
          gl.drawArrays(view.wire ? gl.LINES : gl.TRIANGLES, 0, layer.count * (view.wire ? 2 : 1))
        }
        gl.disable(gl.BLEND)
        visible.filter(layer => (style.opacity[layer.id] ?? 1) >= 0.999).forEach(paint)
        gl.enable(gl.BLEND); gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA); gl.depthMask(false)
        visible.filter(layer => (style.opacity[layer.id] ?? 1) < 0.999).forEach(paint)
        gl.depthMask(true); gl.disable(gl.BLEND)
      }
      draw.current = render; observer = new ResizeObserver(render); observer.observe(element); render()
    } catch (failure) { setError(failure instanceof Error ? failure.message : 'Mesh preview failed.'); release() }
    return release
  }, [layers, bounds])
  useEffect(() => { draw.current?.() }, [display, camera])
  return <figure className="scientific-mesh-viewport"><figcaption><strong>{title}</strong></figcaption>
    <canvas ref={canvas} tabIndex={0} aria-label={`${title}; drag to orbit, arrow keys to rotate`}
      onPointerDown={event => { pointer.current = { x: event.clientX, y: event.clientY }; event.currentTarget.setPointerCapture(event.pointerId) }}
      onPointerMove={event => { if (!pointer.current) return; const dx = event.clientX - pointer.current.x, dy = event.clientY - pointer.current.y; pointer.current = { x: event.clientX, y: event.clientY }; setCamera(value => ({ ...value, yaw: value.yaw + dx * 0.008, pitch: Math.max(-1.5, Math.min(1.5, value.pitch + dy * 0.008)) })) }}
      onPointerUp={() => { pointer.current = null }} onPointerCancel={() => { pointer.current = null }}
      onKeyDown={event => { if (['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(event.key)) { event.preventDefault(); setCamera(value => ({ ...value, yaw: value.yaw + (event.key === 'ArrowRight' ? 0.1 : event.key === 'ArrowLeft' ? -0.1 : 0), pitch: Math.max(-1.5, Math.min(1.5, value.pitch + (event.key === 'ArrowDown' ? 0.1 : event.key === 'ArrowUp' ? -0.1 : 0))) })) } }} />
    {error && <p role="alert">{error}</p>}
    {!layers.some(layer => display.visible[layer.id] !== false && (display.opacity[layer.id] ?? 1) > 0 && layer.mesh.triangles > 0) && <p role="status">No visible surface geometry.</p>}
  </figure>
}

export function MeshCanvas({ mesh, camera, setCamera, bounds, after, label }: {
  mesh: ScientificMeshPreview; camera: Camera; setCamera: React.Dispatch<React.SetStateAction<Camera>>; bounds: number[]; after: boolean; label?: string
}) {
  const layers = useMemo<Layer[]>(() => [{ id: 'single', name: mesh.name, mesh, color: after ? colors.result : colors.a }], [mesh, after])
  return <div><MeshViewport layers={layers} display={solidDisplay} camera={camera} setCamera={setCamera} bounds={bounds} title={label ?? (after ? 'AFTER / output' : 'BEFORE / input')} />
    <p>{mesh.name} / {mesh.points.toLocaleString()} points / {mesh.triangles.toLocaleString()} triangles</p><small>{mesh.triangles ? mesh.note : 'Empty result: no surface geometry.'}</small>
  </div>
}

export function ScientificMeshInspection({ geometry }: { geometry: ScientificArtifactPreview['geometry'] }) {
  const [camera, setCamera] = useState(initialCamera)
  const [display, setDisplay] = useState<Display>({ ...solidDisplay, opacity: { a: 0.2, b: 0.2, result: 1 } })
  const [separate, setSeparate] = useState(false)
  const layers = useMemo<Layer[]>(() => [
    ...(geometry.before ? [{ id: 'a', name: geometry.beforeSecond ? 'Mesh A' : 'Input', mesh: geometry.before, color: colors.a }] : []),
    ...(geometry.beforeSecond ? [{ id: 'b', name: 'Mesh B', mesh: geometry.beforeSecond, color: colors.b }] : []),
    { id: 'result', name: 'Result', mesh: geometry.after, color: colors.result },
  ], [geometry])
  const bounds = useMemo(() => {
    const nonempty = layers.filter(layer => layer.mesh.triangles > 0)
    return nonempty.length ? [0, 1, 2].flatMap(axis => [Math.min(...nonempty.map(layer => layer.mesh.bounds[axis * 2])), Math.max(...nonempty.map(layer => layer.mesh.bounds[axis * 2 + 1]))]) : [-1, 1, -1, 1, -1, 1]
  }, [layers])
  return <section aria-label="Geometry inspection" className="scientific-geometry-inspector">
    <h4>Geometry inspection</h4>
    <div className="scientific-artifact-toolbar"><button onClick={() => { setCamera(initialCamera); setDisplay({ ...solidDisplay, opacity: { a: 0.2, b: 0.2, result: 1 } }) }}>Reset view</button>
      <label>View<select aria-label="Geometry view mode" value={separate ? 'separate' : 'combined'} onChange={event => setSeparate(event.target.value === 'separate')}><option value="combined">A / B / result together</option><option value="separate">Separate views</option></select></label>
      <label>Zoom<input aria-label="Geometry zoom" type="range" min="0.3" max="4" step="0.05" value={camera.zoom} onChange={event => setCamera(previous => ({ ...previous, zoom: Number(event.target.value) }))} /></label>
      <label><input aria-label="Geometry wireframe" type="checkbox" checked={camera.wire} onChange={event => setCamera(previous => ({ ...previous, wire: event.target.checked }))} />Wireframe</label>
    </div>
    <div className="scientific-layer-controls">{layers.map(layer => <fieldset key={layer.id}><legend><span className="scientific-layer-swatch" style={{ background: `rgb(${layer.color.map(value => Math.round(value * 255)).join(',')})` }} />{layer.name}</legend>
      <label><input aria-label={`Show ${layer.name}`} type="checkbox" checked={display.visible[layer.id] !== false} onChange={event => setDisplay(previous => ({ ...previous, visible: { ...previous.visible, [layer.id]: event.target.checked } }))} />Visible</label>
      <label>Opacity<input aria-label={`${layer.name} opacity`} type="range" min="0" max="1" step="0.05" value={display.opacity[layer.id] ?? 1} onChange={event => setDisplay(previous => ({ ...previous, opacity: { ...previous.opacity, [layer.id]: Number(event.target.value) } }))} /><output>{Math.round((display.opacity[layer.id] ?? 1) * 100)}%</output></label>
      <small>{layer.mesh.points.toLocaleString()} points / {layer.mesh.triangles.toLocaleString()} triangles{layer.id === 'result' && !layer.mesh.triangles ? ' / empty result' : ''}</small>
    </fieldset>)}</div>
    <div className="scientific-artifact-toolbar"><label><input aria-label="Enable clipping plane" type="checkbox" checked={display.clip} onChange={event => setDisplay(previous => ({ ...previous, clip: event.target.checked }))} />Clipping plane</label>
      <label>Axis<select aria-label="Clipping axis" disabled={!display.clip} value={display.axis} onChange={event => setDisplay(previous => ({ ...previous, axis: Number(event.target.value) }))}>{['X', 'Y', 'Z'].map((axis, index) => <option key={axis} value={index}>{axis}</option>)}</select></label>
      <label>Position<input aria-label="Clipping position" disabled={!display.clip} type="range" min="0" max="1" step="0.01" value={display.fraction} onChange={event => setDisplay(previous => ({ ...previous, fraction: Number(event.target.value) }))} /><output>{Math.round(display.fraction * 100)}%</output></label>
      <label><input aria-label="Reverse clipping side" disabled={!display.clip} type="checkbox" checked={display.reverse} onChange={event => setDisplay(previous => ({ ...previous, reverse: event.target.checked }))} />Reverse side</label>
    </div>
    {geometry.after.triangles === 0 && <p role="status">Result is empty: no surface geometry. Input meshes remain available for inspection.</p>}
    {separate ? <div className={`scientific-mesh-comparison${layers.length === 3 ? ' scientific-mesh-comparison--three' : ''}`}>{layers.map(layer => <SeparateLayer key={layer.id} layer={layer} display={display} camera={camera} setCamera={setCamera} bounds={bounds} />)}</div>
      : <MeshViewport layers={layers} display={display} camera={camera} setCamera={setCamera} bounds={bounds} title="Combined mesh inspection" />}
    <p className="scientific-runtime-note">Drag to orbit; arrow keys rotate. Visibility, transparency, wireframe, and clipping change the preview only. Clipped surfaces are uncapped; saved meshes retain their full geometry.</p>
    {layers.some(layer => layer.mesh.sampled) && <p className="scientific-runtime-note">Large meshes use sampled triangles for display; statistics and outputs describe the full mesh.</p>}
  </section>
}

function SeparateLayer({ layer, ...props }: { layer: Layer; display: Display; camera: Camera; setCamera: React.Dispatch<React.SetStateAction<Camera>>; bounds: number[] }) {
  const layers = useMemo(() => [layer], [layer])
  return <MeshViewport {...props} layers={layers} title={layer.name} />
}
