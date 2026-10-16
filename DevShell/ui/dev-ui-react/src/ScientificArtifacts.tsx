import { useEffect, useMemo, useRef, useState } from 'react'
import type { ScientificMeshPreview, useScientificRuntime } from './useScientificRuntime'
import type { RuntimeProfile } from './scientificRuntimeProfiles'
import './ScientificArtifacts.css'

export type Camera = { yaw: number; pitch: number; zoom: number; wire: boolean }
export const initialCamera: Camera = { yaw: 0.6, pitch: 0.35, zoom: 0.85, wire: false }
const vertexShader = `
attribute vec3 position; attribute vec3 normal;
uniform vec3 center; uniform float scale; uniform vec2 angle; uniform float zoom; uniform float aspect;
varying vec3 lightingNormal;
vec3 rotate(vec3 p) {
  float cy=cos(angle.x), sy=sin(angle.x), cx=cos(angle.y), sx=sin(angle.y);
  vec3 q=vec3(cy*p.x+sy*p.z,p.y,-sy*p.x+cy*p.z);
  return vec3(q.x,cx*q.y-sx*q.z,sx*q.y+cx*q.z);
}
void main() { vec3 p=rotate((position-center)*scale); lightingNormal=rotate(normal);
  gl_Position=vec4(p.x*zoom/aspect,p.y*zoom,-p.z*0.2,1.0); }
`
const fragmentShader = `
precision mediump float; uniform vec3 color; varying vec3 lightingNormal;
void main() { float light=0.3+0.7*abs(dot(normalize(lightingNormal),normalize(vec3(0.4,0.7,1.0))));
  gl_FragColor=vec4(color*light,1.0); }
`

export function MeshCanvas({ mesh, camera, setCamera, bounds, after, label }: {
  mesh: ScientificMeshPreview; camera: Camera; setCamera: React.Dispatch<React.SetStateAction<Camera>>; bounds: number[]; after: boolean; label?: string
}) {
  const canvas = useRef<HTMLCanvasElement>(null)
  const currentCamera = useRef(camera); currentCamera.current = camera
  const draw = useRef<(() => void) | null>(null)
  const pointer = useRef<{ x: number; y: number } | null>(null)
  const [error, setError] = useState('')
  useEffect(() => {
    const element = canvas.current
    if (!element) return
    setError('')
    if (!Array.isArray(mesh.positions) || mesh.positions.length > 108000 || mesh.positions.length % 9 !== 0 || mesh.positions.some(value => !Number.isFinite(value))) {
      setError('Invalid or oversized preview data.'); return
    }
    const gl = element.getContext('webgl', { antialias: true, preserveDrawingBuffer: false })
    if (!gl) { setError('WebGL is unavailable. Mesh statistics and artifacts remain accessible.'); return }
    const shaders: WebGLShader[] = []
    const buffers: WebGLBuffer[] = []
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
      const positions = new Float32Array(mesh.positions)
      const normals = new Float32Array(positions.length)
      const edges = new Float32Array(positions.length * 2)
      const edgeNormals = new Float32Array(normals.length * 2)
      for (let index = 0; index < positions.length; index += 9) {
        const ax = positions[index + 3] - positions[index], ay = positions[index + 4] - positions[index + 1], az = positions[index + 5] - positions[index + 2]
        const bx = positions[index + 6] - positions[index], by = positions[index + 7] - positions[index + 1], bz = positions[index + 8] - positions[index + 2]
        const nx = ay * bz - az * by, ny = az * bx - ax * bz, nz = ax * by - ay * bx
        const length = Math.hypot(nx, ny, nz) || 1
        for (let corner = 0; corner < 3; corner++) normals.set([nx / length, ny / length, nz / length], index + corner * 3)
        for (let edge = 0; edge < 3; edge++) {
          const offset = index * 2 + edge * 6
          edges.set(positions.subarray(index + edge * 3, index + edge * 3 + 3), offset)
          edges.set(positions.subarray(index + ((edge + 1) % 3) * 3, index + ((edge + 1) % 3) * 3 + 3), offset + 3)
          edgeNormals.set([nx / length, ny / length, nz / length, nx / length, ny / length, nz / length], offset)
        }
      }
      const upload = (values: Float32Array) => { const buffer = gl.createBuffer(); if (!buffer) throw new Error('Cannot allocate preview buffer.'); buffers.push(buffer); gl.bindBuffer(gl.ARRAY_BUFFER, buffer); gl.bufferData(gl.ARRAY_BUFFER, values, gl.STATIC_DRAW); return buffer }
      const solid = [upload(positions), upload(normals)], wire = [upload(edges), upload(edgeNormals)]
      const bind = (name: string, buffer: WebGLBuffer) => { const location = gl.getAttribLocation(program!, name); gl.bindBuffer(gl.ARRAY_BUFFER, buffer); gl.enableVertexAttribArray(location); gl.vertexAttribPointer(location, 3, gl.FLOAT, false, 0, 0) }
      const midpoint = [0, 1, 2].map(axis => (bounds[axis * 2] + bounds[axis * 2 + 1]) / 2)
      const extent = Math.max(bounds[1] - bounds[0], bounds[3] - bounds[2], bounds[5] - bounds[4]) || 1
      const render = () => {
        const view = currentCamera.current
        const ratio = Math.min(window.devicePixelRatio || 1, 2)
        const width = Math.max(1, Math.round(element.clientWidth * ratio)), height = Math.max(1, Math.round(element.clientHeight * ratio))
        if (element.width !== width || element.height !== height) { element.width = width; element.height = height }
        gl.viewport(0, 0, width, height); gl.clearColor(0.035, 0.065, 0.085, 1); gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT); gl.enable(gl.DEPTH_TEST); gl.useProgram(program)
        gl.uniform3fv(gl.getUniformLocation(program!, 'center'), midpoint); gl.uniform1f(gl.getUniformLocation(program!, 'scale'), 1.7 / extent)
        gl.uniform2f(gl.getUniformLocation(program!, 'angle'), view.yaw, view.pitch); gl.uniform1f(gl.getUniformLocation(program!, 'zoom'), view.zoom); gl.uniform1f(gl.getUniformLocation(program!, 'aspect'), width / height)
        gl.uniform3fv(gl.getUniformLocation(program!, 'color'), after ? [0.25, 0.82, 0.88] : [0.94, 0.65, 0.36])
        const pair = view.wire ? wire : solid; bind('position', pair[0]); bind('normal', pair[1])
        gl.drawArrays(view.wire ? gl.LINES : gl.TRIANGLES, 0, (view.wire ? edges.length : positions.length) / 3)
      }
      draw.current = render; observer = new ResizeObserver(render); observer.observe(element); render()
    } catch (failure) { setError(failure instanceof Error ? failure.message : 'Mesh preview failed.'); release() }
    return release
  }, [mesh, bounds, after])
  useEffect(() => { draw.current?.() }, [camera])
  return <figure className="scientific-mesh-viewport"><figcaption><strong>{label ?? (after ? 'AFTER / output' : 'BEFORE / input')}</strong><span>{mesh.name}</span></figcaption>
    <canvas ref={canvas} tabIndex={0} aria-label={`${label ?? (after ? 'Output' : 'Input')} mesh; drag to orbit, arrow keys to rotate`}
      onPointerDown={event => { pointer.current = { x: event.clientX, y: event.clientY }; event.currentTarget.setPointerCapture(event.pointerId) }}
      onPointerMove={event => { if (!pointer.current) return; const dx = event.clientX - pointer.current.x, dy = event.clientY - pointer.current.y; pointer.current = { x: event.clientX, y: event.clientY }; setCamera(value => ({ ...value, yaw: value.yaw + dx * 0.008, pitch: Math.max(-1.5, Math.min(1.5, value.pitch + dy * 0.008)) })) }}
      onPointerUp={() => { pointer.current = null }} onPointerCancel={() => { pointer.current = null }}
      onKeyDown={event => { if (['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(event.key)) { event.preventDefault(); setCamera(value => ({ ...value, yaw: value.yaw + (event.key === 'ArrowRight' ? 0.1 : event.key === 'ArrowLeft' ? -0.1 : 0), pitch: Math.max(-1.5, Math.min(1.5, value.pitch + (event.key === 'ArrowDown' ? 0.1 : event.key === 'ArrowUp' ? -0.1 : 0))) })) } }} />
    {error && <p role="alert">{error}</p>}
    <p>{mesh.points.toLocaleString()} points / {mesh.triangles.toLocaleString()} triangles</p><small>{mesh.note} {mesh.sampled && `${mesh.previewTriangles.toLocaleString()} triangles displayed.`}</small>
  </figure>
}

export function ScientificArtifacts({ runtime, native }: { runtime: RuntimeProfile; native: ReturnType<typeof useScientificRuntime> }) {
  const job = native.jobs[runtime.id]
  const [selected, setSelected] = useState('')
  const [camera, setCamera] = useState<Camera>(initialCamera)
  useEffect(() => { setSelected(''); setCamera(initialCamera) }, [runtime.id, job?.jobId])
  const artifacts = (job?.result?.artifacts ?? []).filter(item => /\.(obj|stl|ply|vtp|m3dm)$/i.test(item.path))
  const path = artifacts.some(item => item.path === selected) ? selected : artifacts[0]?.path ?? ''
  const cached = native.previews[runtime.id]
  const preview = cached?.jobId === job?.jobId && cached?.artifactPath === path ? cached : null
  const bounds = useMemo(() => {
    if (!preview) return [0, 1, 0, 1, 0, 1]
    const meshes = [preview.geometry.before, preview.geometry.after].filter((item): item is ScientificMeshPreview => !!item)
    return [0, 1, 2].flatMap(axis => [Math.min(...meshes.map(item => item.bounds[axis * 2])), Math.max(...meshes.map(item => item.bounds[axis * 2 + 1]))])
  }, [preview])
  const result = job?.result
  return <section className="scientific-artifacts" aria-label="Scientific mesh artifacts">
    <h3>Mesh comparison / run artifacts</h3>
    {!job ? <p>No managed run in this session. Use Commands to run a mesh recipe; opening this page does not execute anything.</p> : <>
      <p><strong>{job.recipeId} / {job.state}</strong> / {job.durationMs} ms / <code>{job.jobId}</code></p>
      <div className="scientific-artifact-toolbar"><label>Output artifact<select aria-label="Scientific output artifact" value={path} onChange={event => { setSelected(event.target.value); setCamera(initialCamera) }}><option value="">Select geometry...</option>{artifacts.map(item => <option key={item.path} value={item.path}>{item.path}</option>)}</select></label>
        <button disabled={!path || job.state !== 'succeeded' || native.pending} onClick={() => native.send(runtime.id, 'artifacts', { jobId: job.jobId, artifactPath: path })}>{native.pending ? 'Loading...' : 'Load comparison'}</button>
        <button onClick={() => native.send(runtime.id, 'open-output', { jobId: job.jobId })}>Open output folder</button><button onClick={() => native.send(runtime.id, 'open-log', { jobId: job.jobId })}>Open full log</button>
      </div>
      {!artifacts.length && <p>No previewable geometry in this run. Failed, cancelled, and timed-out runs do not advertise successful output artifacts.</p>}
      {preview && <><div className="scientific-artifact-toolbar"><button onClick={() => setCamera(initialCamera)}>Fit / reset camera</button><label>Zoom<input aria-label="Mesh zoom" type="range" min="0.3" max="4" step="0.05" value={camera.zoom} onChange={event => setCamera(value => ({ ...value, zoom: Number(event.target.value) }))} /></label><label><input type="checkbox" checked={camera.wire} onChange={event => setCamera(value => ({ ...value, wire: event.target.checked }))} /> Wireframe</label><span>Drag either view to orbit both.</span></div>
        <div className="scientific-mesh-comparison">{preview.geometry.before ? <MeshCanvas mesh={preview.geometry.before} camera={camera} setCamera={setCamera} bounds={bounds} after={false} /> : <p>Input preview is unavailable for this format. The output remains previewable.</p>}<MeshCanvas mesh={preview.geometry.after} camera={camera} setCamera={setCamera} bounds={bounds} after /></div></>}
      {result && <><table className="scientific-mesh-statistics"><thead><tr><th>Recorded statistic</th><th>Before</th><th>After</th><th>Change</th></tr></thead><tbody>{['points', 'triangles', 'boundaryEdges', 'nonManifoldEdges', 'closed'].map(name => {
        const before = result.before?.[name], after = result.after?.[name]
        if (before === undefined && after === undefined) return null
        return <tr key={name}><th>{name}</th><td>{String(before ?? 'Not recorded')}</td><td>{String(after ?? 'Not recorded')}</td><td>{typeof before === 'number' && typeof after === 'number' ? (after - before).toLocaleString() : 'Not applicable'}</td></tr>
      })}</tbody></table><p className="scientific-runtime-note">{result.scope}</p>
        {result.diagnostics.length > 0 && <ul>{result.diagnostics.map((item, index) => <li key={index}>{item.severity}: {item.message}</li>)}</ul>}
        <details><summary>Artifact hashes and input provenance</summary><pre>{JSON.stringify({ inputArtifacts: result.inputArtifacts, artifacts: result.artifacts, provenance: result.provenance }, null, 2)}</pre></details>
        <details><summary>Shared request / result contract</summary><h4>Request</h4><pre>{JSON.stringify(job.request, null, 2)}</pre><h4>Result</h4><pre>{JSON.stringify(result, null, 2)}</pre></details></>}
    </>}
    <p className="scientific-runtime-note">Read-only OBJ/STL/PLY/VTP/M3DM previews require the dedicated VTK environment. At most 12,000 sampled triangles per view; statistics describe the full worker geometry. No file content is executed, no external resources are fetched, and meshes are not saved in profile restoration.</p>
  </section>
}
