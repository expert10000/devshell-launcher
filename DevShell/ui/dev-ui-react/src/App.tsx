import { useEffect, useMemo, useRef, useState } from 'react'
import { Terminal } from 'xterm'
import { FitAddon } from 'xterm-addon-fit'
import 'xterm/css/xterm.css'
import './App.css'

type BackendMessage = {
  type: string
  sessionId?: string
  data?: string
  exitCode?: number
  message?: string
}

type WebViewBridge = {
  postMessage: (data: unknown) => void
  addEventListener: (name: 'message', handler: (event: MessageEvent) => void) => void
  removeEventListener: (name: 'message', handler: (event: MessageEvent) => void) => void
}

const getBridge = (): WebViewBridge | null => {
  const chrome = (window as Window & { chrome?: { webview?: WebViewBridge } }).chrome
  return chrome?.webview ?? null
}

const parseMessage = (event: MessageEvent): BackendMessage | null => {
  if (typeof event.data === 'string') {
    try {
      return JSON.parse(event.data) as BackendMessage
    } catch {
      return null
    }
  }

  if (typeof event.data === 'object' && event.data) {
    return event.data as BackendMessage
  }

  return null
}

function App() {
  const terminalHostRef = useRef<HTMLDivElement | null>(null)
  const termRef = useRef<Terminal | null>(null)
  const fitRef = useRef<FitAddon | null>(null)
  const sessionIdRef = useRef<string | null>(null)
  const [status, setStatus] = useState('disconnected')
  const [shell, setShell] = useState<'powershell' | 'cmd'>('powershell')
  const [fallbackUsed, setFallbackUsed] = useState(false)

  const bridge = useMemo(getBridge, [])

  const postMessage = (payload: Record<string, unknown>) => {
    bridge?.postMessage(payload)
  }

  const sendResize = () => {
    if (!termRef.current || !fitRef.current || !sessionIdRef.current) {
      return
    }

    fitRef.current.fit()
    const dims = fitRef.current.proposeDimensions()
    if (!dims) {
      return
    }

    postMessage({
      type: 'terminal.resize',
      sessionId: sessionIdRef.current,
      cols: dims.cols,
      rows: dims.rows,
    })
  }

  const startSession = (shellType: 'powershell' | 'cmd' = 'powershell') => {
    setStatus('starting')
    if (shellType === 'powershell') {
      setFallbackUsed(false)
    }
    postMessage({ type: 'terminal.start', shell: shellType })
  }

  const killSession = () => {
    if (!sessionIdRef.current) {
      return
    }

    postMessage({ type: 'terminal.kill', sessionId: sessionIdRef.current })
  }

  useEffect(() => {
    if (!terminalHostRef.current) {
      return
    }

    const term = new Terminal({
      fontFamily: '"JetBrains Mono", "Cascadia Mono", monospace',
      fontSize: 14,
      cursorBlink: true,
      scrollback: 5000,
      theme: {
        background: '#0e1116',
        foreground: '#d9e2f1',
        cursor: '#8ad1ff',
        selectionBackground: '#2c3a54',
      },
    })

    const fitAddon = new FitAddon()
    term.loadAddon(fitAddon)
    term.open(terminalHostRef.current)
    fitAddon.fit()

    term.onData((data) => {
      if (!sessionIdRef.current) {
        return
      }

      postMessage({
        type: 'terminal.stdin',
        sessionId: sessionIdRef.current,
        data,
      })
    })

    termRef.current = term
    fitRef.current = fitAddon

    if (bridge) {
      startSession(shell)
    } else {
      setStatus('offline')
    }

    const handleResize = () => {
      sendResize()
    }

    window.addEventListener('resize', handleResize)
    return () => {
      window.removeEventListener('resize', handleResize)
      term.dispose()
    }
  }, [bridge, shell])

  useEffect(() => {
    if (!bridge) {
      return
    }

    const handleMessage = (event: MessageEvent) => {
      const message = parseMessage(event)
      if (!message) {
        return
      }

      switch (message.type) {
        case 'terminal.ready': {
          if (message.sessionId) {
            sessionIdRef.current = message.sessionId
            setStatus('connected')
            sendResize()
          }
          break
        }
        case 'terminal.stdout': {
          if (!termRef.current || message.sessionId !== sessionIdRef.current) {
            return
          }
          termRef.current.write(message.data ?? '')
          break
        }
        case 'terminal.exit': {
          if (message.sessionId === sessionIdRef.current) {
            sessionIdRef.current = null
            const exitCode = message.exitCode ?? 0
            setStatus(`exited (${exitCode})`)

            if (exitCode === -1073741502 && shell === 'powershell' && !fallbackUsed) {
              setFallbackUsed(true)
              termRef.current?.writeln(
                '\r\n[info] PowerShell failed (0xC0000142). Starting cmd.exe...'
              )
              startSession('cmd')
            }
          }
          break
        }
        case 'terminal.error': {
          if (termRef.current) {
            termRef.current.writeln(`\r\n[error] ${message.message ?? 'unknown error'}`)
          }
          setStatus('error')
          break
        }
        default:
          break
      }
    }

    bridge.addEventListener('message', handleMessage)
    return () => bridge.removeEventListener('message', handleMessage)
  }, [bridge])

  return (
    <div className="shell-app">
      <header className="shell-toolbar">
        <div className="brand">
          <div className="brand-title">DevShell</div>
          <div className="brand-subtitle">ConPTY bridge • WebView2</div>
        </div>
        <div className="actions">
          <div className="shell-toggle">
            <button
              className={`toggle ${shell === 'powershell' ? 'active' : ''}`}
              onClick={() => setShell('powershell')}
            >
              PowerShell
            </button>
            <button
              className={`toggle ${shell === 'cmd' ? 'active' : ''}`}
              onClick={() => setShell('cmd')}
            >
              CMD
            </button>
          </div>
          <button
            className="action ghost"
            onClick={() => startSession(shell)}
          >
            New session
          </button>
          <button className="action danger" onClick={killSession}>
            Kill session
          </button>
          <button
            className="action ghost"
            onClick={() => termRef.current?.clear()}
          >
            Clear
          </button>
          <button className="action primary" onClick={sendResize}>
            Fit to window
          </button>
        </div>
        <div className="status">
          <span className="status-dot" />
          <span>{status}</span>
        </div>
      </header>
      <main className="terminal-pane">
        <div className="terminal-frame">
          <div ref={terminalHostRef} className="terminal-host" />
        </div>
      </main>
    </div>
  )
}

export default App
