import { useEffect, useMemo, useRef, useState, type MouseEvent as ReactMouseEvent } from 'react'
import { Terminal } from 'xterm'
import { FitAddon } from 'xterm-addon-fit'
import { SearchAddon } from 'xterm-addon-search'
import { WebLinksAddon } from 'xterm-addon-web-links'
import 'xterm/css/xterm.css'
import './App.css'

type BackendMessage = {
  type: string
  sessionId?: string
  clientId?: string
  data?: string
  code?: number
  message?: string
  state?: string
  profiles?: TerminalProfile[]
  statePayload?: AppState
  profileId?: string
  tasks?: TaskEntry[]
  projects?: ProjectDefinition[]
  sessions?: ExistingSession[]
  enabled?: boolean
  path?: string
  parent?: string
  entries?: FolderEntry[]
  error?: string
  transferId?: string
  scriptsPath?: string
}

type WebViewBridge = {
  postMessage: (data: unknown) => void
  addEventListener: (name: 'message', handler: (event: MessageEvent) => void) => void
  removeEventListener: (name: 'message', handler: (event: MessageEvent) => void) => void
}

type TerminalProfile = {
  id: string
  name: string
  command: string
  arguments?: string
  workingDirectory?: string
  environment?: Record<string, string>
  icon?: string
  defaultCols?: number
  defaultRows?: number
  isBuiltin?: boolean
  isAvailable?: boolean
  isTemplate?: boolean
}

type TaskEntry = {
  id?: string
  name: string
  path?: string
  command?: string
  args?: string
  workingDirectory?: string
  cwd?: string
  profileId?: string
  useTerminal?: boolean
  autoRun?: boolean
}

type ExistingSession = {
  sessionId: string
  profileId: string
  state?: string
}

type ProjectLayoutItem = {
  title: string
  profileId?: string
  taskId?: string
  cwd?: string
  autoRun?: boolean
  startOrder?: number
}

type ProjectLayout = {
  type: 'split' | 'tabs'
  direction?: 'vertical' | 'horizontal'
  panes?: ProjectLayout[]
  items?: ProjectLayoutItem[]
}

type ProjectDefinition = {
  id: string
  name: string
  root?: string
  layout?: ProjectLayout
}

type PersistedPane = {
  id: string
  profileId: string
  title: string
  cwd?: string
  cols?: number
  rows?: number
}

type PersistedGroup = {
  id: string
  title: string
  tabs: PersistedPane[]
  activeTabId?: string
}

type PersistedTab = {
  id: string
  title: string
  panes?: PersistedPane[]
  activePaneId?: string
  groups?: PersistedGroup[]
  activeGroupId?: string
  split?: boolean
  splitDirection?: 'vertical' | 'horizontal'
  splitRatio?: number
}

type AppState = {
  tabs: PersistedTab[]
  activeTabId?: string
  restoreSessions?: boolean
  theme?: string
  fontFamily?: string
  fontSize?: number
  autoFit?: boolean
  copyOnSelect?: boolean
  rightClickPaste?: boolean
  favoriteFolders?: string[]
}

type SessionInfo = {
  id: string
  title: string
  profileId: string
  status: string
  sessionId: string | null
  pendingStart: boolean
  cwd?: string
  cols?: number
  rows?: number
  taskId?: string
  autoRun?: boolean
  startOrder?: number
}

type GroupInfo = {
  id: string
  title: string
  tabs: SessionInfo[]
  activeTabId: string
}

type TabInfo = {
  id: string
  title: string
  groups: GroupInfo[]
  activeGroupId: string
  split: boolean
  splitDirection: 'vertical' | 'horizontal'
  splitRatio: number
}

type PaletteCommand = {
  id: string
  label: string
  action: () => void
  keywords?: string
}

type FolderNavState = {
  startFolder?: string
  current?: string
  recent: string[]
  backStack: string[]
  forwardStack: string[]
}

type FolderEntry = {
  name: string
  path: string
  kind?: 'drive' | 'folder'
}

type FolderListing = {
  path: string
  parent?: string
  entries: FolderEntry[]
  loading: boolean
  error?: string
}

type ContextMenuState = {
  open: boolean
  x: number
  y: number
  paneId: string | null
  hasSelection: boolean
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

const normalizeProfileList = (profiles: TerminalProfile[]) =>
  profiles.slice().sort((a, b) => a.name.localeCompare(b.name))

const App = () => {
  const termRefs = useRef<Map<string, Terminal>>(new Map())
  const fitRefs = useRef<Map<string, FitAddon>>(new Map())
  const searchRefs = useRef<Map<string, SearchAddon>>(new Map())
  const hostRefs = useRef<Map<string, HTMLDivElement>>(new Map())
  const paneToSession = useRef<Map<string, string>>(new Map())
  const sessionToPane = useRef<Map<string, string>>(new Map())
  const pendingStart = useRef<Map<string, string>>(new Map())
  const pendingTasks = useRef<Map<string, string>>(new Map())
  const closedTabs = useRef<PersistedTab[]>([])
  const profileMenuRef = useRef<HTMLDivElement | null>(null)
  const projectMenuRef = useRef<HTMLDivElement | null>(null)
  const taskMenuRef = useRef<HTMLDivElement | null>(null)
  const folderPickerRef = useRef<HTMLDivElement | null>(null)
  const contextMenuRef = useRef<HTMLDivElement | null>(null)
  const loggingSessions = useRef<Set<string>>(new Set())
  const folderNav = useRef<Map<string, FolderNavState>>(new Map())
  const [profiles, setProfiles] = useState<TerminalProfile[]>([])
  const [tasks, setTasks] = useState<TaskEntry[]>([])
  const [projects, setProjects] = useState<ProjectDefinition[]>([])
  const [tabs, setTabs] = useState<TabInfo[]>([])
  const [activeTabId, setActiveTabId] = useState<string | null>(null)
  const [selectedProfileId, setSelectedProfileId] = useState<string>('powershell')
  const [autoFit, setAutoFit] = useState(true)
  const [copyOnSelect, setCopyOnSelect] = useState(false)
  const [rightClickPaste, setRightClickPaste] = useState(true)
  const [restoreSessions, setRestoreSessions] = useState(false)
  const [theme, setTheme] = useState('midnight')
  const [fontFamily, setFontFamily] = useState('"JetBrains Mono", "Cascadia Mono", monospace')
  const [fontSize, setFontSize] = useState(14)
  const [favoriteFolders, setFavoriteFolders] = useState<string[]>([])
  const [paletteOpen, setPaletteOpen] = useState(false)
  const [paletteQuery, setPaletteQuery] = useState('')
  const [searchOpen, setSearchOpen] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [profileMenuOpen, setProfileMenuOpen] = useState(false)
  const [taskMenuOpen, setTaskMenuOpen] = useState(false)
  const [projectEditorOpen, setProjectEditorOpen] = useState(false)
  const [projectEditorQuery, setProjectEditorQuery] = useState('')
  const [projectEditorTab, setProjectEditorTab] = useState<'basics' | 'layout' | 'tasks'>('basics')
  const [projectEditorProjectId, setProjectEditorProjectId] = useState<string | null>(null)
  const [projectEditorPaneIndex, setProjectEditorPaneIndex] = useState(0)
  const [projectEditorItemIndex, setProjectEditorItemIndex] = useState(0)
  const [projectEditorTaskQuery, setProjectEditorTaskQuery] = useState('')
  const [folderPickerOpen, setFolderPickerOpen] = useState(false)
  const [folderPickerPaneId, setFolderPickerPaneId] = useState<string | null>(null)
  const [folderPickerQuery, setFolderPickerQuery] = useState('')
  const [folderPickerVersion, setFolderPickerVersion] = useState(0)
  const [folderPickerWidth, setFolderPickerWidth] = useState(420)
  const [folderListing, setFolderListing] = useState<FolderListing>({
    path: '',
    entries: [],
    loading: false,
  })
  const [profileQuery, setProfileQuery] = useState('')
  const [projectQuery, setProjectQuery] = useState('')
  const [taskQuery, setTaskQuery] = useState('')
  const [pinnedProjectIds, setPinnedProjectIds] = useState<string[]>(() => {
    if (typeof window === 'undefined') {
      return []
    }
    try {
      const stored = window.localStorage.getItem('devshell.pinnedProjects')
      return stored ? (JSON.parse(stored) as string[]) : []
    } catch {
      return []
    }
  })
  const [taskProjectId, setTaskProjectId] = useState<string | null>(null)
  const [projectTaskMenuOpen, setProjectTaskMenuOpen] = useState(true)
  const [runAllSessions, setRunAllSessions] = useState(false)
  const [recentProjectIds, setRecentProjectIds] = useState<string[]>([])
  const [activeProjectId, setActiveProjectId] = useState<string | null>(null)
  const [projectMenuProjectId, setProjectMenuProjectId] = useState<string | null>(null)
  const [editingTabId, setEditingTabId] = useState<string | null>(null)
  const [editingTitle, setEditingTitle] = useState('')
  const [dragActive, setDragActive] = useState(false)
  const [scriptsPath, setScriptsPath] = useState<string | null>(null)
  const [contextMenu, setContextMenu] = useState<ContextMenuState>({
    open: false,
    x: 0,
    y: 0,
    paneId: null,
    hasSelection: false,
  })

  const bridge = useMemo(getBridge, [])

  const postMessage = (payload: Record<string, unknown>) => {
    bridge?.postMessage(payload)
  }

  const getActiveTab = () => tabs.find((tab) => tab.id === activeTabId) ?? null

  const getActiveGroup = () => {
    const tab = getActiveTab()
    if (!tab) {
      return null
    }
    return tab.groups.find((group) => group.id === tab.activeGroupId) ?? tab.groups[0] ?? null
  }

  const getActivePane = () => {
    const group = getActiveGroup()
    if (!group) {
      return null
    }
    return group.tabs.find((pane) => pane.id === group.activeTabId) ?? group.tabs[0] ?? null
  }

  const findPaneById = (paneId: string) => {
    for (const tab of tabs) {
      for (const group of tab.groups) {
        const pane = group.tabs.find((item) => item.id === paneId)
        if (pane) {
          return pane
        }
      }
    }
    return null
  }

  const getProfileById = (profileId?: string | null) =>
    profiles.find((profile) => profile.id === profileId) ?? null

  const ensureFolderState = (pane: SessionInfo | null) => {
    if (!pane) {
      return null
    }

    const existing = folderNav.current.get(pane.id)
    const profile = getProfileById(pane.profileId)
    const seedFolder = pane.cwd ?? profile?.workingDirectory
    if (existing) {
      if (!existing.current && seedFolder) {
        existing.current = seedFolder
      }
      if (!existing.startFolder && seedFolder) {
        existing.startFolder = seedFolder
      }
      if (seedFolder && !existing.recent.includes(seedFolder)) {
        existing.recent = [seedFolder, ...existing.recent].slice(0, 12)
      }
      return existing
    }

    const state: FolderNavState = {
      startFolder: seedFolder,
      current: seedFolder,
      recent: seedFolder ? [seedFolder] : [],
      backStack: [],
      forwardStack: [],
    }
    folderNav.current.set(pane.id, state)
    return state
  }

  const normalizeFolderKey = (value: string) => value.trim().toLowerCase()

  const isFavoriteFolder = (path: string) => {
    const key = normalizeFolderKey(path)
    if (!key) {
      return false
    }
    return favoriteFolders.some((entry) => normalizeFolderKey(entry) === key)
  }

  const addFavoriteFolder = (path: string) => {
    const trimmed = path.trim()
    if (!trimmed) {
      return
    }
    setFavoriteFolders((current) => {
      if (current.some((entry) => normalizeFolderKey(entry) === normalizeFolderKey(trimmed))) {
        return current
      }
      return [trimmed, ...current].slice(0, 50)
    })
  }

  const removeFavoriteFolder = (path: string) => {
    const key = normalizeFolderKey(path)
    setFavoriteFolders((current) =>
      current.filter((entry) => normalizeFolderKey(entry) !== key)
    )
  }

  const toggleFavoriteFolder = (path: string) => {
    if (isFavoriteFolder(path)) {
      removeFavoriteFolder(path)
      return
    }
    addFavoriteFolder(path)
  }

  const clampFolderPickerWidth = (value: number) => Math.min(720, Math.max(320, value))

  const startFolderPickerResize = (event: ReactMouseEvent<HTMLDivElement>) => {
    event.preventDefault()
    const startX = event.clientX
    const startWidth = clampFolderPickerWidth(folderPickerWidth)
    const handleMove = (moveEvent: MouseEvent) => {
      const nextWidth = clampFolderPickerWidth(startWidth + (startX - moveEvent.clientX))
      setFolderPickerWidth(nextWidth)
    }
    const handleUp = () => {
      window.removeEventListener('mousemove', handleMove)
      window.removeEventListener('mouseup', handleUp)
    }
    window.addEventListener('mousemove', handleMove)
    window.addEventListener('mouseup', handleUp)
  }

  const updatePaneCwd = (paneId: string, cwd: string) => {
    setTabs((current) =>
      current.map((tab) => ({
        ...tab,
        groups: tab.groups.map((group) => ({
          ...group,
          tabs: group.tabs.map((pane) => (pane.id === paneId ? { ...pane, cwd } : pane)),
        })),
      }))
    )
  }

  const resolveShellKind = (profileId: string) => {
    const profile = getProfileById(profileId)
    const command = profile?.command?.toLowerCase() ?? profile?.name.toLowerCase() ?? ''
    if (command.includes('cmd')) {
      return 'cmd'
    }
    if (command.includes('pwsh') || command.includes('powershell')) {
      return 'powershell'
    }
    if (command.includes('bash') || command.includes('wsl')) {
      return 'bash'
    }
    return 'powershell'
  }

  const quotePowerShell = (value: string) => `"${value.replace(/"/g, '`"')}"`
  const quoteCmd = (value: string) => `"${value.replace(/"/g, '""')}"`
  const quoteBash = (value: string) => `"${value.replace(/"/g, '\\"')}"`

  const buildTaskCommand = (task: TaskEntry) => {
    const command = task.command?.trim()
    if (command) {
      return command
    }
    const path = task.path?.trim()
    if (!path) {
      return ''
    }
    const args = task.args?.trim()
    return args ? `${path} ${args}` : path
  }

  const buildChangeDirectoryCommand = (profileId: string, path: string) => {
    const kind = resolveShellKind(profileId)
    if (kind === 'cmd') {
      return `cd /d ${quoteCmd(path)}`
    }
    if (kind === 'bash') {
      return `cd ${quoteBash(path)}`
    }
    return `Set-Location -Path ${quotePowerShell(path)}`
  }

  const sendTaskToSession = (sessionId: string, task: TaskEntry) => {
    const command = buildTaskCommand(task)
    if (!command) {
      return false
    }
    const cwd = task.workingDirectory ?? task.cwd
    if (cwd) {
      const paneId = sessionToPane.current.get(sessionId)
      const pane = paneId ? findPaneById(paneId) : null
      const profileId = pane?.profileId ?? selectedProfileId
      const cd = buildChangeDirectoryCommand(profileId, cwd)
      postMessage({ type: 'input', sessionId, data: `${cd}\r\n` })
      setTimeout(() => {
        postMessage({ type: 'input', sessionId, data: `${command}\r\n` })
      }, 150)
      return true
    }
    postMessage({ type: 'input', sessionId, data: `${command}\r\n` })
    return true
  }

  const runTaskByIdInActivePane = (taskId: string) => {
    const pane = getActivePane()
    if (!pane?.sessionId) {
      window.alert('No active session to receive commands.')
      return
    }
    const task = findTask(taskId)
    if (!task) {
      window.alert(`Task not found: ${taskId}`)
      return
    }
    sendTaskToSession(pane.sessionId, task)
  }

  const applyFolderChange = (
    paneId: string,
    path: string,
    options?: { sendCommand?: boolean; pushHistory?: boolean }
  ) => {
    const trimmed = path.trim()
    if (!trimmed) {
      return
    }

    const pane = findPaneById(paneId)
    if (!pane) {
      return
    }

    const state = ensureFolderState(pane)
    const current = state?.current
    if (state) {
      if (options?.pushHistory !== false && current && current !== trimmed) {
        state.backStack.push(current)
        state.forwardStack = []
      }
      state.current = trimmed
      state.startFolder ??= current ?? trimmed
      state.recent = [trimmed, ...state.recent.filter((entry) => entry !== trimmed)].slice(0, 12)
    }

    updatePaneCwd(paneId, trimmed)
    setFolderPickerVersion((value) => value + 1)
    if (options?.sendCommand === false) {
      return
    }

    const sessionId = pane.sessionId ?? paneToSession.current.get(paneId)
    if (!sessionId) {
      window.alert('No active session to change folder.')
      return
    }

    const command = buildChangeDirectoryCommand(pane.profileId, trimmed)
    postMessage({ type: 'input', sessionId, data: `${command}\r\n` })
  }

  const focusPaneById = (paneId: string) => {
    const target = tabs
      .flatMap((tab) => tab.groups.map((group) => ({ tab, group })))
      .find(({ group }) => group.tabs.some((pane) => pane.id === paneId))

    if (!target) {
      return
    }

    if (activeTabId !== target.tab.id) {
      setActiveTabId(target.tab.id)
    }

    setTabs((current) =>
      current.map((tab) =>
        tab.id === target.tab.id
          ? {
              ...tab,
              activeGroupId: target.group.id,
              groups: tab.groups.map((group) =>
                group.id === target.group.id ? { ...group, activeTabId: paneId } : group
              ),
            }
          : tab
      )
    )

    setTimeout(() => sendResize(paneId), 0)
  }

  const openFolderPicker = (paneId: string) => {
    const pane = findPaneById(paneId)
    if (!pane) {
      return
    }
    focusPaneById(paneId)
    if (folderPickerOpen && folderPickerPaneId === paneId) {
      setFolderPickerOpen(false)
      return
    }
    ensureFolderState(pane)
    setFolderPickerPaneId(paneId)
    setFolderPickerQuery('')
    setFolderPickerOpen(true)
    setFolderPickerVersion((value) => value + 1)
  }

  const handleFolderBack = (paneId: string) => {
    const pane = findPaneById(paneId)
    const state = ensureFolderState(pane)
    if (!pane || !state || state.backStack.length === 0) {
      return
    }
    const next = state.backStack.pop() as string
    if (state.current) {
      state.forwardStack.unshift(state.current)
    }
    state.current = next
    state.recent = [next, ...state.recent.filter((entry) => entry !== next)].slice(0, 12)
    updatePaneCwd(paneId, next)
    setFolderPickerVersion((value) => value + 1)
    if (pane.sessionId) {
      const command = buildChangeDirectoryCommand(pane.profileId, next)
      postMessage({ type: 'input', sessionId: pane.sessionId, data: `${command}\r` })
    }
  }

  const handleFolderForward = (paneId: string) => {
    const pane = findPaneById(paneId)
    const state = ensureFolderState(pane)
    if (!pane || !state || state.forwardStack.length === 0) {
      return
    }
    const next = state.forwardStack.shift() as string
    if (state.current) {
      state.backStack.push(state.current)
    }
    state.current = next
    state.recent = [next, ...state.recent.filter((entry) => entry !== next)].slice(0, 12)
    updatePaneCwd(paneId, next)
    setFolderPickerVersion((value) => value + 1)
    if (pane.sessionId) {
      const command = buildChangeDirectoryCommand(pane.profileId, next)
      postMessage({ type: 'input', sessionId: pane.sessionId, data: `${command}\r` })
    }
  }

  const openFolderBrowser = (paneId: string) => {
    const pane = findPaneById(paneId)
    if (!pane?.sessionId) {
      window.alert('No active session to change folder.')
      return
    }
    const state = ensureFolderState(pane)
    const path = state?.current ?? pane.cwd
    postMessage({ type: 'folder.pick', sessionId: pane.sessionId, path })
  }

  const requestFolderListing = (paneId: string, path: string) => {
    const pane = findPaneById(paneId)
    if (!pane) {
      return
    }

    setFolderListing((current) => ({
      path,
      parent: current.path === path ? current.parent : undefined,
      entries: current.path === path ? current.entries : [],
      loading: true,
      error: undefined,
    }))
    postMessage({ type: 'folder.request', sessionId: pane.sessionId, path })
  }

  const openFolderInExplorer = (paneId: string) => {
    const pane = findPaneById(paneId)
    const state = ensureFolderState(pane)
    const path = state?.current
    if (!pane?.sessionId || !path) {
      return
    }
    postMessage({ type: 'folder.explorer', sessionId: pane.sessionId, path })
  }

  const sendResize = (paneId: string) => {
    const fit = fitRefs.current.get(paneId)
    const paneSessionId = paneToSession.current.get(paneId)
    if (!fit || !paneSessionId) {
      return
    }

    fit.fit()
    const dims = fit.proposeDimensions()
    if (!dims) {
      return
    }

    postMessage({
      type: 'resize',
      sessionId: paneSessionId,
      cols: dims.cols,
      rows: dims.rows,
    })
    setTabs((current) =>
      current.map((tab) => ({
        ...tab,
        groups: tab.groups.map((group) => ({
          ...group,
          tabs: group.tabs.map((pane) =>
            pane.id === paneId
              ? {
                  ...pane,
                  cols: dims.cols,
                  rows: dims.rows,
                }
              : pane
          ),
        })),
      }))
    )
  }

  const createSession = (
    profileId: string,
    autoStart: boolean,
    overrides?: Partial<SessionInfo>
  ) => {
    const paneId = crypto.randomUUID()
    const profile = profiles.find((item) => item.id === profileId)
    const defaultProjectRoot = activeProjectId
      ? projects.find((project) => project.id === activeProjectId)?.root
      : undefined
    const title = overrides?.title ?? profile?.name ?? 'Shell'
    const pane: SessionInfo = {
      id: paneId,
      title,
      profileId,
      status: autoStart ? 'starting' : 'disconnected',
      sessionId: null,
      pendingStart: autoStart,
      cwd: overrides?.cwd ?? defaultProjectRoot ?? profile?.workingDirectory,
      cols: overrides?.cols,
      rows: overrides?.rows,
      taskId: overrides?.taskId,
      autoRun: overrides?.autoRun,
      startOrder: overrides?.startOrder,
    }

    if (autoStart) {
      startSessionForPane(paneId, profileId, overrides)
    }

    if (pane.taskId) {
      pendingTasks.current.set(pane.id, pane.taskId)
    }

    return pane
  }

  const createGroup = (tabs: SessionInfo[], overrides?: Partial<GroupInfo>) => {
    const groupId = overrides?.id ?? crypto.randomUUID()
    return {
      id: groupId,
      title: overrides?.title ?? tabs[0]?.title ?? 'Group',
      tabs,
      activeTabId: overrides?.activeTabId ?? tabs[0]?.id ?? groupId,
    }
  }

  const createWorkspace = (groups: GroupInfo[], overrides?: Partial<TabInfo>) => {
    const newTab: TabInfo = {
      id: overrides?.id ?? crypto.randomUUID(),
      title: overrides?.title ?? groups[0]?.title ?? 'Tab',
      groups,
      activeGroupId: overrides?.activeGroupId ?? groups[0]?.id ?? '',
      split: overrides?.split ?? groups.length > 1,
      splitDirection: overrides?.splitDirection ?? 'vertical',
      splitRatio: overrides?.splitRatio ?? 0.5,
    }

    setTabs((current) => [...current, newTab])
    setActiveTabId(newTab.id)
    return newTab.id
  }

  const createTab = (
    profileId: string,
    autoStart: boolean,
    overrides?: Partial<TabInfo> & { group?: Partial<GroupInfo>; pane?: Partial<SessionInfo> }
  ) => {
    const pane = createSession(profileId, autoStart, overrides?.pane)
    const group = createGroup([pane], overrides?.group)
    return createWorkspace([group], overrides)
  }

  const startSessionForPane = (
    paneId: string,
    profileId: string,
    overrides?: Partial<SessionInfo>
  ) => {
    pendingStart.current.set(paneId, paneId)
    postMessage({
      type: 'start',
      clientId: paneId,
      profileId,
      cols: overrides?.cols,
      rows: overrides?.rows,
      cwd: overrides?.cwd,
    })
  }

  const closeTab = (tabId: string, options?: { force?: boolean }) => {
    const tab = tabs.find((item) => item.id === tabId)
    if (!tab) {
      return
    }

    const panes = tab.groups.flatMap((group) => group.tabs)
    const hasRunning = panes.some((pane) => pane.sessionId && pane.status === 'running')
    if (!options?.force && hasRunning && !window.confirm('This tab has running sessions. Close it anyway?')) {
      return
    }

    panes.forEach((pane) => {
      if (pane.sessionId) {
        postMessage({ type: 'kill', sessionId: pane.sessionId })
        sessionToPane.current.delete(pane.sessionId)
      }

      paneToSession.current.delete(pane.id)
      termRefs.current.get(pane.id)?.dispose()
      termRefs.current.delete(pane.id)
      fitRefs.current.delete(pane.id)
      searchRefs.current.delete(pane.id)
      hostRefs.current.delete(pane.id)
      pendingTasks.current.delete(pane.id)
      folderNav.current.delete(pane.id)
    })
    if (folderPickerPaneId && panes.some((pane) => pane.id === folderPickerPaneId)) {
      setFolderPickerOpen(false)
      setFolderPickerPaneId(null)
    }

    closedTabs.current.unshift(toPersistedTab(tab))
    closedTabs.current = closedTabs.current.slice(0, 8)
    setTabs((current) => current.filter((item) => item.id !== tabId))
    if (activeTabId === tabId) {
      const nextTab = tabs.find((item) => item.id !== tabId)
      setActiveTabId(nextTab?.id ?? null)
    }
  }

  const resetWorkspace = () => {
    tabs.forEach((tab) => {
      tab.groups.flatMap((group) => group.tabs).forEach((pane) => {
        if (pane.sessionId) {
          postMessage({ type: 'kill', sessionId: pane.sessionId })
          sessionToPane.current.delete(pane.sessionId)
        }
        paneToSession.current.delete(pane.id)
        termRefs.current.get(pane.id)?.dispose()
        termRefs.current.delete(pane.id)
        fitRefs.current.delete(pane.id)
        searchRefs.current.delete(pane.id)
        hostRefs.current.delete(pane.id)
        pendingTasks.current.delete(pane.id)
        folderNav.current.delete(pane.id)
      })
    })
    closedTabs.current = []
    setTabs([])
    setActiveTabId(null)
  }

  const closePane = (tabId: string, groupId: string, paneId: string) => {
    const tab = tabs.find((item) => item.id === tabId)
    if (!tab) {
      return
    }

    const group = tab.groups.find((item) => item.id === groupId)
    if (!group) {
      return
    }

    const pane = group.tabs.find((item) => item.id === paneId)
    if (!pane) {
      return
    }

    if (tab.groups.length === 1 && group.tabs.length === 1) {
      closeTab(tabId)
      return
    }

    if (pane.sessionId && pane.status === 'running') {
      if (!window.confirm('This pane has a running session. Close it anyway?')) {
        return
      }
    }

    if (pane.sessionId) {
      postMessage({ type: 'kill', sessionId: pane.sessionId })
      sessionToPane.current.delete(pane.sessionId)
    }

    paneToSession.current.delete(pane.id)
    termRefs.current.get(pane.id)?.dispose()
    termRefs.current.delete(pane.id)
    fitRefs.current.delete(pane.id)
    searchRefs.current.delete(pane.id)
    hostRefs.current.delete(pane.id)
    pendingTasks.current.delete(pane.id)
    folderNav.current.delete(pane.id)
    if (folderPickerPaneId === paneId) {
      setFolderPickerOpen(false)
      setFolderPickerPaneId(null)
    }

    setTabs((current) =>
      current.map((item) => {
        if (item.id !== tabId) {
          return item
        }

        const nextGroups = item.groups
          .map((groupItem) => {
            if (groupItem.id !== groupId) {
              return groupItem
            }

            const remainingTabs = groupItem.tabs.filter((tabItem) => tabItem.id !== paneId)
            if (remainingTabs.length === 0) {
              return null
            }
            const activeTabId =
              groupItem.activeTabId === paneId ? remainingTabs[0]?.id ?? '' : groupItem.activeTabId
            return {
              ...groupItem,
              tabs: remainingTabs,
              activeTabId,
            }
          })
          .filter((groupItem): groupItem is GroupInfo => groupItem !== null)

        const activeGroupId =
          item.activeGroupId === groupId ? nextGroups[0]?.id ?? '' : item.activeGroupId
        return {
          ...item,
          groups: nextGroups,
          activeGroupId,
          split: nextGroups.length > 1,
        }
      })
    )
  }

  const killActiveSession = () => {
    const pane = getActivePane()
    if (!pane?.sessionId) {
      return
    }

    postMessage({ type: 'kill', sessionId: pane.sessionId })
  }

  const splitActiveTab = () => {
    const tab = getActiveTab()
    if (!tab) {
      return
    }

    if (tab.groups.length >= 2) {
      return
    }

    const pane = createSession(selectedProfileId, true)
    const group = createGroup([pane])
    setTabs((current) =>
      current.map((item) =>
        item.id === tab.id
          ? {
              ...item,
              groups: [...item.groups, group],
              split: true,
              activeGroupId: group.id,
            }
          : item
      )
    )
  }

  const requestWorkingDirectory = () => {
    const pane = getActivePane()
    if (!pane) {
      window.alert('No active session to change folder.')
      return
    }
    openFolderPicker(pane.id)
  }

  const focusGroup = (groupId: string) => {
    const tab = getActiveTab()
    const group = tab?.groups.find((item) => item.id === groupId)
    if (group?.activeTabId) {
      setTimeout(() => sendResize(group.activeTabId), 0)
    }
    setTabs((current) =>
      current.map((item) =>
        item.id === activeTabId
          ? {
              ...item,
              activeGroupId: groupId,
            }
          : item
      )
    )
  }

  const focusPane = (groupId: string, paneId: string) => {
    setTabs((current) =>
      current.map((item) => {
        if (item.id !== activeTabId) {
          return item
        }
        return {
          ...item,
          activeGroupId: groupId,
          groups: item.groups.map((group) =>
            group.id === groupId ? { ...group, activeTabId: paneId } : group
          ),
        }
      })
    )
    setTimeout(() => sendResize(paneId), 0)
  }

  const applySplitRatio = (tabId: string, ratio: number) => {
    setTabs((current) =>
      current.map((item) =>
        item.id === tabId
          ? {
              ...item,
              splitRatio: Math.min(0.8, Math.max(0.2, ratio)),
            }
          : item
      )
    )
  }

  const toPersistedTab = (tab: TabInfo): PersistedTab => ({
    id: tab.id,
    title: tab.title,
    groups: tab.groups.map((group) => ({
      id: group.id,
      title: group.title,
      tabs: group.tabs.map((pane) => ({
        id: pane.id,
        title: pane.title,
        profileId: pane.profileId,
        cwd: pane.cwd,
        cols: pane.cols,
        rows: pane.rows,
      })),
      activeTabId: group.activeTabId,
    })),
    activeGroupId: tab.activeGroupId,
    split: tab.split,
    splitDirection: tab.splitDirection,
    splitRatio: tab.splitRatio,
  })

  const handlePaneInput = (paneId: string, data: string) => {
    const sessionId = paneToSession.current.get(paneId)
    if (!sessionId) {
      return
    }

    postMessage({ type: 'input', sessionId, data })
  }

  const copySelectionForPane = async (paneId: string) => {
    const term = termRefs.current.get(paneId)
    if (!term) {
      return
    }
    const selection = term.getSelection()
    if (!selection) {
      return
    }
    try {
      await navigator.clipboard?.writeText(selection)
    } catch {
      // Ignore clipboard failures (permissions, etc.).
    }
  }

  const pasteClipboardForPane = async (paneId: string) => {
    try {
      const text = await navigator.clipboard?.readText()
      if (text) {
        handlePaneInput(paneId, text)
      }
    } catch {
      // Ignore clipboard failures (permissions, etc.).
    }
  }

  const openContextMenu = (paneId: string, event: MouseEvent) => {
    if (!rightClickPaste) {
      return
    }
    event.preventDefault()
    const term = termRefs.current.get(paneId)
    const selection = term?.getSelection() ?? ''
    setContextMenu({
      open: true,
      x: event.clientX,
      y: event.clientY,
      paneId,
      hasSelection: Boolean(selection),
    })
  }

  const closeContextMenu = () => {
    setContextMenu((current) =>
      current.open
        ? {
            open: false,
            x: 0,
            y: 0,
            paneId: null,
            hasSelection: false,
          }
        : current
    )
  }

  const isTerminalEventTarget = (paneId: string, target: EventTarget | null) => {
    if (!(target instanceof Node)) {
      return false
    }
    const host = hostRefs.current.get(paneId)
    return host ? host.contains(target) : false
  }

  const findTask = (taskId: string) =>
    tasks.find((task) => task.id === taskId || task.name === taskId) ?? null

  const initializeFromState = (state: AppState) => {
    setRestoreSessions(state.restoreSessions ?? true)
    setTheme(state.theme ?? 'midnight')
    setFontFamily(state.fontFamily ?? '"JetBrains Mono", "Cascadia Mono", monospace')
    setFontSize(state.fontSize ?? 14)
    setAutoFit(state.autoFit ?? true)
    setCopyOnSelect(state.copyOnSelect ?? false)
    setRightClickPaste(state.rightClickPaste ?? true)
    setFavoriteFolders(state.favoriteFolders ?? [])

    if (!state.tabs || state.tabs.length === 0) {
      createTab(selectedProfileId, true)
      return
    }

    const restoredTabs: TabInfo[] = state.tabs.map((tab) => {
      const groups = tab.groups?.length
        ? tab.groups.map((group) => ({
            id: group.id,
            title: group.title,
            tabs: group.tabs.map((pane) => ({
              id: pane.id,
              title: pane.title,
              profileId: pane.profileId,
              status: state.restoreSessions ? 'starting' : 'disconnected',
              sessionId: null,
              pendingStart: state.restoreSessions ?? true,
              cwd: pane.cwd,
              cols: pane.cols,
              rows: pane.rows,
            })),
            activeTabId: group.activeTabId ?? group.tabs[0]?.id ?? group.id,
          }))
        : tab.panes?.length
          ? [
              {
                id: crypto.randomUUID(),
                title: tab.title,
                tabs: tab.panes.map((pane) => ({
                  id: pane.id,
                  title: pane.title,
                  profileId: pane.profileId,
                  status: state.restoreSessions ? 'starting' : 'disconnected',
                  sessionId: null,
                  pendingStart: state.restoreSessions ?? true,
                  cwd: pane.cwd,
                  cols: pane.cols,
                  rows: pane.rows,
                })),
                activeTabId: tab.activePaneId ?? tab.panes[0]?.id ?? tab.id,
              },
            ]
          : []

      const fallbackGroup = groups.length ? groups : [createGroup([createSession(selectedProfileId, false)])]
      return {
        id: tab.id,
        title: tab.title,
        groups: fallbackGroup,
        activeGroupId: tab.activeGroupId ?? fallbackGroup[0]?.id ?? tab.id,
        split: tab.split ?? fallbackGroup.length > 1,
        splitDirection: tab.splitDirection ?? 'vertical',
        splitRatio: tab.splitRatio ?? 0.5,
      }
    })

    setTabs(restoredTabs)
    setActiveTabId(state.activeTabId ?? restoredTabs[0]?.id ?? null)

    if (state.restoreSessions) {
      restoredTabs.forEach((tab) => {
        tab.groups.forEach((group) => {
          group.tabs.forEach((pane) => {
            startSessionForPane(pane.id, pane.profileId, pane)
          })
        })
      })
    }
  }

  const initializeFromSessions = (sessions: ExistingSession[], profileList: TerminalProfile[]) => {
    const restoredTabs: TabInfo[] = sessions.map((session) => {
      const profile = profileList.find((item) => item.id === session.profileId)
      const title = profile?.name ?? session.profileId
      const paneId = crypto.randomUUID()
      const pane: SessionInfo = {
        id: paneId,
        title,
        profileId: session.profileId,
        status: session.state ?? 'running',
        sessionId: session.sessionId,
        pendingStart: false,
      }
      paneToSession.current.set(paneId, session.sessionId)
      sessionToPane.current.set(session.sessionId, paneId)
      postMessage({ type: 'session.attach', sessionId: session.sessionId, clientId: paneId })
      const group: GroupInfo = {
        id: crypto.randomUUID(),
        title,
        tabs: [pane],
        activeTabId: paneId,
      }
      return {
        id: crypto.randomUUID(),
        title,
        groups: [group],
        activeGroupId: group.id,
        split: false,
        splitDirection: 'vertical',
        splitRatio: 0.5,
      }
    })

    setTabs(restoredTabs)
    setActiveTabId(restoredTabs[0]?.id ?? null)
  }

  const buildAppState = (): AppState => ({
    tabs: tabs.map(toPersistedTab),
    activeTabId: activeTabId ?? undefined,
    restoreSessions,
    theme,
    fontFamily,
    fontSize,
    autoFit,
    copyOnSelect,
    rightClickPaste,
    favoriteFolders,
  })

  useEffect(() => {
    if (!bridge) {
      return
    }

    postMessage({ type: 'app.ready' })
  }, [bridge])

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
        case 'app.init': {
          const incomingProfiles = message.profiles ?? []
          setProfiles(normalizeProfileList(incomingProfiles))
          setTasks(message.tasks ?? [])
          setProjects(message.projects ?? [])
          setScriptsPath(message.scriptsPath ?? null)
          const incomingState = message.statePayload
          if (incomingState && incomingState.tabs?.length) {
            initializeFromState(incomingState)
          } else if (message.sessions && message.sessions.length > 0) {
            initializeFromSessions(message.sessions, incomingProfiles)
          } else if (incomingState) {
            initializeFromState(incomingState)
          } else {
            createTab(selectedProfileId, true)
          }
          break
        }
        case 'profiles.list': {
          const incomingProfiles = message.profiles ?? []
          setProfiles(normalizeProfileList(incomingProfiles))
          break
        }
        case 'tasks.list': {
          setTasks(message.tasks ?? [])
          break
        }
        case 'projects.list': {
          setProjects(message.projects ?? [])
          break
        }
        case 'ready': {
          const paneId = message.clientId ?? pendingStart.current.keys().next().value
          if (!paneId) {
            return
          }

          pendingStart.current.delete(paneId)
          if (!message.sessionId) {
            return
          }

          paneToSession.current.set(paneId, message.sessionId)
          sessionToPane.current.set(message.sessionId, paneId)
          setTabs((current) =>
            current.map((tab) => ({
              ...tab,
              groups: tab.groups.map((group) => ({
                ...group,
                tabs: group.tabs.map((pane) =>
                  pane.id === paneId
                    ? {
                        ...pane,
                        sessionId: message.sessionId ?? null,
                        status: 'running',
                        pendingStart: false,
                      }
                    : pane
                ),
              })),
            }))
          )
          if (autoFit) {
            sendResize(paneId)
          }

          termRefs.current.get(paneId)?.writeln(`\r\n[ready] ${paneId}`)

          const pane = findPaneById(paneId)
          if (pane?.cwd) {
            setTimeout(() => {
              applyFolderChange(paneId, pane.cwd ?? '', { pushHistory: false })
            }, 200)
          }

          const taskId = pendingTasks.current.get(paneId) ?? pane?.taskId
          if (taskId) {
            const paneAutoRun = pane?.autoRun !== false
            const task = findTask(taskId)
            if (!paneAutoRun || task?.autoRun === false) {
              pendingTasks.current.delete(paneId)
            } else if (task) {
              sendTaskToSession(message.sessionId, task)
              pendingTasks.current.delete(paneId)
            } else {
              schedulePendingTask(paneId, taskId)
            }
          }
          break
        }
        case 'output': {
          if (!message.sessionId) {
            return
          }
          const paneId = sessionToPane.current.get(message.sessionId)
          if (!paneId) {
            return
          }
          termRefs.current.get(paneId)?.write(message.data ?? '')
          break
        }
        case 'exit': {
          if (!message.sessionId) {
            return
          }
          const paneId = sessionToPane.current.get(message.sessionId)
          if (!paneId) {
            return
          }
          sessionToPane.current.delete(message.sessionId)
          paneToSession.current.delete(paneId)
          pendingTasks.current.delete(paneId)
          setTabs((current) =>
            current.map((tab) => ({
              ...tab,
              groups: tab.groups.map((group) => ({
                ...group,
                tabs: group.tabs.map((pane) =>
                  pane.id === paneId
                    ? {
                        ...pane,
                        sessionId: null,
                        status: `exited (${message.code ?? 0})`,
                      }
                    : pane
                ),
              })),
            }))
          )
          break
        }
        case 'status': {
          if (!message.sessionId) {
            return
          }
          const paneId = sessionToPane.current.get(message.sessionId)
          if (!paneId) {
            return
          }
          setTabs((current) =>
            current.map((tab) => ({
              ...tab,
              groups: tab.groups.map((group) => ({
                ...group,
                tabs: group.tabs.map((pane) =>
                  pane.id === paneId
                    ? {
                        ...pane,
                        status: message.state ?? pane.status,
                      }
                    : pane
                ),
              })),
            }))
          )
          break
        }
        case 'folder.changed': {
          if (!message.sessionId || !message.path) {
            return
          }
          const paneId = sessionToPane.current.get(message.sessionId)
          if (!paneId) {
            return
          }
          applyFolderChange(paneId, message.path, { sendCommand: false })
          break
        }
        case 'folder.list': {
          if (message.path === undefined) {
            return
          }
          setFolderListing((current) => {
            if (current.path !== message.path) {
              return current
            }
            return {
              path: message.path ?? current.path,
              parent: message.parent,
              entries: message.entries ?? [],
              loading: false,
              error: message.error,
            }
          })
          break
        }
        case 'error': {
          const paneId =
            message.clientId ?? (message.sessionId ? sessionToPane.current.get(message.sessionId) : null)
          if (!paneId) {
            return
          }
          termRefs.current.get(paneId)?.writeln(`\r\n[error] ${message.message ?? 'unknown error'}`)
          setTabs((current) =>
            current.map((tab) => ({
              ...tab,
              groups: tab.groups.map((group) => ({
                ...group,
                tabs: group.tabs.map((pane) =>
                  pane.id === paneId
                    ? {
                        ...pane,
                        status: 'error',
                        pendingStart: false,
                      }
                    : pane
                ),
              })),
            }))
          )
          break
        }
        case 'logging.status': {
          if (!message.sessionId) {
            return
          }
          if (message.enabled) {
            loggingSessions.current.add(message.sessionId)
          } else {
            loggingSessions.current.delete(message.sessionId)
          }
          const paneId = sessionToPane.current.get(message.sessionId)
          if (paneId) {
            const term = termRefs.current.get(paneId)
            if (term) {
              const info = message.enabled ? `logging to ${message.path ?? 'file'}` : 'logging stopped'
              term.writeln(`\r\n[info] ${info}`)
            }
          }
          break
        }
        case 'file.status': {
          if (!message.transferId) {
            return
          }
          const pane = getActivePane()
          if (!pane) {
            return
          }
          const term = termRefs.current.get(pane.id)
          if (term) {
            term.writeln(`\r\n[file] ${message.state ?? 'status'} ${message.path ?? ''}`.trim())
          }
          break
        }
        default:
          break
      }
    }

    bridge.addEventListener('message', handleMessage)
    return () => bridge.removeEventListener('message', handleMessage)
  }, [bridge, autoFit, selectedProfileId])

  useEffect(() => {
    if (!profileMenuOpen) {
      return
    }

    const handleClick = (event: MouseEvent) => {
      const target = event.target as Node
      if (profileMenuRef.current && !profileMenuRef.current.contains(target)) {
        setProfileMenuOpen(false)
      }
    }

    window.addEventListener('click', handleClick)
    return () => window.removeEventListener('click', handleClick)
  }, [profileMenuOpen])

  useEffect(() => {
    if (!projectMenuProjectId) {
      return
    }

    const handleClick = (event: MouseEvent) => {
      const target = event.target as Node
      if (projectMenuRef.current && !projectMenuRef.current.contains(target)) {
        setProjectMenuProjectId(null)
      }
    }

    window.addEventListener('click', handleClick)
    return () => window.removeEventListener('click', handleClick)
  }, [projectMenuProjectId])

  useEffect(() => {
    if (typeof window === 'undefined') {
      return
    }
    try {
      window.localStorage.setItem('devshell.pinnedProjects', JSON.stringify(pinnedProjectIds))
    } catch {
      // Ignore storage errors (private mode, blocked, etc.)
    }
  }, [pinnedProjectIds])

  useEffect(() => {
    if (pinnedProjectIds.length === 0) {
      return
    }
    const available = new Set(projects.map((project) => project.id))
    setPinnedProjectIds((current) => current.filter((id) => available.has(id)))
  }, [projects, pinnedProjectIds.length])

  useEffect(() => {
    if (!taskMenuOpen) {
      return
    }

    const handleClick = (event: MouseEvent) => {
      const target = event.target as Node
      if (taskMenuRef.current && !taskMenuRef.current.contains(target)) {
        setTaskMenuOpen(false)
      }
    }

    window.addEventListener('click', handleClick)
    return () => window.removeEventListener('click', handleClick)
  }, [taskMenuOpen])

  useEffect(() => {
    if (!folderPickerOpen) {
      return
    }

    const handleClick = (event: MouseEvent) => {
      const target = event.target as Node
      if (folderPickerRef.current && !folderPickerRef.current.contains(target)) {
        setFolderPickerOpen(false)
      }
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setFolderPickerOpen(false)
      }
    }

    window.addEventListener('click', handleClick)
    window.addEventListener('keydown', handleKeyDown)
    return () => {
      window.removeEventListener('click', handleClick)
      window.removeEventListener('keydown', handleKeyDown)
    }
  }, [folderPickerOpen])

  useEffect(() => {
    if (!folderPickerOpen || !folderPickerPaneId) {
      return
    }
    const pane = findPaneById(folderPickerPaneId)
    if (!pane) {
      return
    }
    const state = ensureFolderState(pane)
    const targetPath = state?.current ?? pane.cwd ?? ''
    if (folderListing.loading && folderListing.path === targetPath) {
      return
    }
    const isSamePath = folderListing.path === targetPath
    const hasResults = folderListing.entries.length > 0 || Boolean(folderListing.error)
    if (!isSamePath || !hasResults) {
      requestFolderListing(pane.id, targetPath)
    }
  }, [folderPickerOpen, folderPickerPaneId, folderPickerVersion])

  useEffect(() => {
    if (!contextMenu.open) {
      return
    }

    const handleDismiss = (event: MouseEvent) => {
      const target = event.target as Node
      if (contextMenuRef.current && contextMenuRef.current.contains(target)) {
        return
      }
      closeContextMenu()
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        closeContextMenu()
      }
    }

    window.addEventListener('click', handleDismiss)
    window.addEventListener('contextmenu', handleDismiss)
    window.addEventListener('keydown', handleKeyDown)
    return () => {
      window.removeEventListener('click', handleDismiss)
      window.removeEventListener('contextmenu', handleDismiss)
      window.removeEventListener('keydown', handleKeyDown)
    }
  }, [contextMenu.open])

  useEffect(() => {
    if (projects.length === 0) {
      if (taskProjectId !== null) {
        setTaskProjectId(null)
      }
      return
    }

    const hasSelected =
      taskProjectId && projects.some((project) => project.id === taskProjectId)
    if (hasSelected) {
      return
    }

    setTaskProjectId(activeProjectId ?? projects[0]?.id ?? null)
  }, [projects, activeProjectId, taskProjectId])

  useEffect(() => {
    const handleResize = () => {
      if (!autoFit) {
        return
      }

      const tab = getActiveTab()
      if (!tab) {
        return
      }

      tab.groups.forEach((group) => {
        if (group.activeTabId) {
          sendResize(group.activeTabId)
        }
      })
    }

    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [autoFit, tabs, activeTabId])

  useEffect(() => {
    tabs.forEach((tab) => {
      tab.groups.forEach((group) => {
        group.tabs.forEach((pane) => {
        if (termRefs.current.has(pane.id)) {
          return
        }

        const host = hostRefs.current.get(pane.id)
        if (!host) {
          return
        }

        const term = new Terminal({
          fontFamily,
          fontSize,
          cursorBlink: true,
          scrollback: 8000,
          theme: {
            background: theme === 'midnight' ? '#0e1116' : '#0d1014',
            foreground: theme === 'midnight' ? '#d9e2f1' : '#e5e8f0',
            cursor: '#8ad1ff',
            selectionBackground: theme === 'midnight' ? '#2c3a54' : '#2c2f3f',
          },
        })

        const fitAddon = new FitAddon()
        const searchAddon = new SearchAddon()
        const webLinksAddon = new WebLinksAddon()
        term.loadAddon(fitAddon)
        term.loadAddon(searchAddon)
        term.loadAddon(webLinksAddon)
        term.open(host)
        fitAddon.fit()

        term.onData((data) => handlePaneInput(pane.id, data))
        term.onSelectionChange(() => {
          if (!copyOnSelect) {
            return
          }

          const selection = term.getSelection()
          if (selection) {
            navigator.clipboard?.writeText(selection).catch(() => undefined)
          }
        })

        host.addEventListener('contextmenu', (event) => {
          openContextMenu(pane.id, event)
        })

        termRefs.current.set(pane.id, term)
        fitRefs.current.set(pane.id, fitAddon)
        searchRefs.current.set(pane.id, searchAddon)
        })
      })
    })
  }, [tabs, fontFamily, fontSize, theme, copyOnSelect, rightClickPaste])

  useEffect(() => {
    if (!bridge) {
      return
    }

    const payload = buildAppState()
    postMessage({ type: 'app.state', state: payload })
  }, [
    tabs,
    activeTabId,
    restoreSessions,
    theme,
    fontFamily,
    fontSize,
    autoFit,
    copyOnSelect,
    rightClickPaste,
    favoriteFolders,
  ])

  useEffect(() => {
    if (pendingTasks.current.size === 0) {
      return
    }
    pendingTasks.current.forEach((taskId, paneId) => {
      schedulePendingTask(paneId, taskId)
    })
  }, [tasks])

  useEffect(() => {
    const handleKey = (event: KeyboardEvent) => {
      const pane = getActivePane()
      if (pane && isTerminalEventTarget(pane.id, event.target)) {
        const key = event.key.toLowerCase()
        if (event.ctrlKey && !event.altKey) {
          if (key === 'c') {
            const term = termRefs.current.get(pane.id)
            const selection = term?.getSelection()
            if (selection) {
              event.preventDefault()
              void copySelectionForPane(pane.id)
              closeContextMenu()
              return
            }
          }

          if (key === 'v') {
            event.preventDefault()
            void pasteClipboardForPane(pane.id)
            closeContextMenu()
            return
          }
        }
      }

      if (event.ctrlKey && event.shiftKey && event.key.toLowerCase() === 'p') {
        event.preventDefault()
        setPaletteOpen(true)
        setPaletteQuery('')
        return
      }
      if (event.ctrlKey && event.shiftKey && event.key.toLowerCase() === 'd') {
        event.preventDefault()
        const pane = getActivePane()
        if (pane) {
          openFolderPicker(pane.id)
        }
        return
      }

      if (event.ctrlKey && event.key.toLowerCase() === 'w') {
        event.preventDefault()
        if (activeTabId) {
          closeTab(activeTabId)
        }
        return
      }

      if (event.ctrlKey && event.shiftKey && event.key.toLowerCase() === 't') {
        event.preventDefault()
        const last = closedTabs.current.shift()
        if (last) {
          const restoredGroups: GroupInfo[] = last.groups?.length
            ? last.groups.map((group) => ({
                id: group.id,
                title: group.title,
                tabs: group.tabs.map((pane) => ({
                  id: pane.id,
                  title: pane.title,
                  profileId: pane.profileId,
                  status: 'starting',
                  sessionId: null,
                  pendingStart: true,
                  cwd: pane.cwd,
                  cols: pane.cols,
                  rows: pane.rows,
                })),
                activeTabId: group.activeTabId ?? group.tabs[0]?.id ?? group.id,
              }))
            : last.panes?.length
              ? [
                  {
                    id: crypto.randomUUID(),
                    title: last.title,
                    tabs: last.panes.map((pane) => ({
                      id: pane.id,
                      title: pane.title,
                      profileId: pane.profileId,
                      status: 'starting',
                      sessionId: null,
                      pendingStart: true,
                      cwd: pane.cwd,
                      cols: pane.cols,
                      rows: pane.rows,
                    })),
                    activeTabId: last.activePaneId ?? last.panes[0]?.id ?? last.id,
                  },
                ]
              : []

          if (restoredGroups.length === 0) {
            return
          }

          createWorkspace(restoredGroups, {
            id: last.id,
            title: last.title,
            split: last.split ?? restoredGroups.length > 1,
            splitDirection: last.splitDirection ?? 'vertical',
            splitRatio: last.splitRatio ?? 0.5,
            activeGroupId: last.activeGroupId ?? restoredGroups[0]?.id ?? last.id,
          })
          restoredGroups.forEach((group) => {
            group.tabs.forEach((pane) => {
              startSessionForPane(pane.id, pane.profileId, pane)
            })
          })
        }
        return
      }

      if (event.ctrlKey && event.key === 'Tab') {
        event.preventDefault()
        if (tabs.length > 1 && activeTabId) {
          const index = tabs.findIndex((tab) => tab.id === activeTabId)
          const nextIndex = (index + 1) % tabs.length
          setActiveTabId(tabs[nextIndex].id)
        }
        return
      }

      if (event.altKey && !event.shiftKey && !event.ctrlKey) {
        const number = parseInt(event.key, 10)
        if (!Number.isNaN(number) && number >= 1 && number <= 9) {
          const tab = tabs[number - 1]
          if (tab) {
            event.preventDefault()
            setActiveTabId(tab.id)
          }
        }
      }

      if (event.ctrlKey && event.key.toLowerCase() === 'f') {
        event.preventDefault()
        setSearchOpen(true)
      }
    }

    window.addEventListener('keydown', handleKey)
    return () => window.removeEventListener('keydown', handleKey)
  }, [tabs, activeTabId, selectedProfileId])

  const paletteCommands: PaletteCommand[] = [
    {
      id: 'new-tab',
      label: 'New Tab',
      action: () => createTab(selectedProfileId, true),
      keywords: 'tab new session',
    },
    {
      id: 'split',
      label: 'Split Pane (Vertical)',
      action: splitActiveTab,
      keywords: 'split pane',
    },
    {
      id: 'kill',
      label: 'Kill Active Session',
      action: killActiveSession,
      keywords: 'kill terminate',
    },
    {
      id: 'theme',
      label: 'Toggle Theme',
      action: () => setTheme((current) => (current === 'midnight' ? 'graphite' : 'midnight')),
      keywords: 'theme color',
    },
    {
      id: 'font-inc',
      label: 'Increase Font Size',
      action: () => setFontSize((current) => Math.min(22, current + 1)),
      keywords: 'font size',
    },
    {
      id: 'font-dec',
      label: 'Decrease Font Size',
      action: () => setFontSize((current) => Math.max(10, current - 1)),
      keywords: 'font size',
    },
    {
      id: 'logging',
      label: 'Toggle Session Logging',
      action: toggleLogging,
      keywords: 'log session',
    },
    {
      id: 'change-folder',
      label: 'Change Working Folder...',
      action: requestWorkingDirectory,
      keywords: 'folder cwd directory browse',
    },
  ]

  const filteredCommands = paletteCommands.filter((command) => {
    const query = paletteQuery.toLowerCase()
    if (!query) {
      return true
    }
    return (
      command.label.toLowerCase().includes(query) ||
      (command.keywords ?? '').toLowerCase().includes(query)
    )
  })

  const handlePaletteSelect = (command: PaletteCommand) => {
    command.action()
    setPaletteOpen(false)
    setPaletteQuery('')
  }

  const tryRunPendingTask = (paneId: string, taskId: string) => {
    const task = findTask(taskId)
    const pane = findPaneById(paneId)
    if (task?.autoRun === false || pane?.autoRun === false) {
      pendingTasks.current.delete(paneId)
      return false
    }
    if (!task) {
      return false
    }
    const sessionId = paneToSession.current.get(paneId)
    if (!sessionId) {
      return false
    }
    const cwd = task.workingDirectory ?? task.cwd ?? 'unknown cwd'
    const commandLabel = task.command ?? task.path ?? 'command'
    termRefs.current
      .get(paneId)
      ?.writeln(`\r\n[task] ${task.name} :: ${commandLabel} @ ${cwd}`)
    if (!sendTaskToSession(sessionId, task)) {
      return false
    }
    pendingTasks.current.delete(paneId)
    return true
  }

  const schedulePendingTask = (
    paneId: string,
    taskId: string,
    attempt = 0,
    orderDelayMs = 0
  ) => {
    if (attempt > 10) {
      return
    }
    const delay = (attempt === 0 ? 200 : 200 + attempt * 150) + orderDelayMs
    setTimeout(() => {
      const ran = tryRunPendingTask(paneId, taskId)
      if (!ran && pendingTasks.current.has(paneId)) {
        schedulePendingTask(paneId, taskId, attempt + 1, orderDelayMs)
      }
    }, delay)
  }

  const handleSearch = () => {
    const pane = getActivePane()
    if (!pane) {
      return
    }
    const addon = searchRefs.current.get(pane.id)
    if (addon && searchQuery) {
      addon.findNext(searchQuery)
    }
  }

  const handleTaskSelect = (task: TaskEntry) => {
    setTaskMenuOpen(false)
    if (!task.path && !task.command) {
      window.alert('Task is missing a command.')
      return
    }

    if (runAllSessions) {
      const targetPanes = tabs
        .flatMap((tab) => tab.groups)
        .flatMap((group) => group.tabs)
        .filter((pane) => pane.sessionId)
        .filter((pane) => !task.profileId || task.profileId === pane.profileId)

      if (targetPanes.length === 0) {
        handleTaskRunInNewTab(task)
        return
      }

      targetPanes.forEach((pane) => {
        sendTaskToSession(pane.sessionId as string, task)
      })
      return
    }

    const activePane = getActivePane()
    if (!activePane?.sessionId) {
      handleTaskRunInNewTab(task)
      return
    }

    sendTaskToSession(activePane.sessionId, task)
  }

  const handleTaskRunInNewTab = (task: TaskEntry) => {
    setTaskMenuOpen(false)
    if (!task.path && !task.command) {
      window.alert('Task is missing a command.')
      return
    }
    const profileId = task.profileId ?? selectedProfileId
    const taskId = task.id ?? task.name
    createTab(profileId, true, {
      title: task.name,
      pane: {
        taskId,
        cwd: task.cwd ?? task.workingDirectory,
      },
    })
  }

  const buildGroupFromLayout = (
    layout: ProjectLayout,
    projectRoot?: string
  ): GroupInfo | null => {
    if (layout.type === 'tabs') {
      const items = layout.items ?? []
      if (items.length === 0) {
        return null
      }
      const panes = items.map((item) =>
        {
          const task = item.taskId ? findTask(item.taskId) : null
          const taskCwd = task?.workingDirectory ?? task?.cwd
          return createSession(item.profileId ?? selectedProfileId, true, {
            title: item.title,
            taskId: item.taskId,
            cwd: item.cwd ?? taskCwd ?? projectRoot,
            autoRun: item.autoRun,
            startOrder: item.startOrder,
          })
        }
      )
      return createGroup(panes)
    }

    if (layout.type === 'split' && layout.panes?.length) {
      return buildGroupFromLayout(layout.panes[0], projectRoot)
    }

    return null
  }

  const collectProjectTitles = (layout?: ProjectLayout): string[] => {
    if (!layout) {
      return []
    }
    if (layout.type === 'tabs') {
      return (layout.items ?? [])
        .map((item) => item.title)
        .filter((title): title is string => Boolean(title))
    }
    if (layout.type === 'split') {
      return (layout.panes ?? []).flatMap((pane) => collectProjectTitles(pane))
    }
    return []
  }

  const collectProjectLayoutItems = (layout?: ProjectLayout): ProjectLayoutItem[] => {
    if (!layout) {
      return []
    }
    if (layout.type === 'tabs') {
      return layout.items ?? []
    }
    if (layout.type === 'split') {
      return (layout.panes ?? []).flatMap((pane) => collectProjectLayoutItems(pane))
    }
    return []
  }

  const formatShellBadge = (kind: string) => {
    if (kind === 'powershell') {
      return 'PWSh'
    }
    if (kind === 'cmd') {
      return 'CMD'
    }
    if (kind === 'bash') {
      return 'Bash'
    }
    return kind.toUpperCase()
  }

  const inferProjectEnvBadge = (projectRoot?: string) => {
    if (!projectRoot) {
      return null
    }
    const root = projectRoot.toLowerCase()
    const signals = tasks
      .filter((task) => {
        const cwd = task.cwd ?? task.workingDirectory
        return cwd?.toLowerCase().startsWith(root)
      })
      .map((task) =>
        `${task.command ?? ''} ${task.path ?? ''} ${task.args ?? ''}`.toLowerCase()
      )

    if (signals.some((text) => text.includes('docker'))) {
      return 'DOCKER'
    }
    if (signals.some((text) => text.includes('npm') || text.includes('pnpm') || text.includes('yarn'))) {
      return 'NODE'
    }
    if (
      signals.some(
        (text) =>
          text.includes('conda') || text.includes('venv') || text.includes('python') || text.includes('pip')
      )
    ) {
      return 'PY'
    }
    if (signals.some((text) => text.includes('mvn') || text.includes('gradle'))) {
      return 'JAVA'
    }
    return null
  }

  const getProjectBadges = (project: ProjectDefinition) => {
    const items = collectProjectLayoutItems(project.layout)
    const primaryProfileId = items.find((item) => item.profileId)?.profileId ?? selectedProfileId
    const badges = [formatShellBadge(resolveShellKind(primaryProfileId))]
    const envBadge = inferProjectEnvBadge(project.root)
    if (envBadge) {
      badges.push(envBadge)
    }
    return badges
  }

  const getProjectSubtitle = (project: ProjectDefinition) => {
    const titles = collectProjectTitles(project.layout)
    if (titles.length > 0) {
      return titles.slice(0, 4).join(' + ')
    }
    return project.root ?? 'Workspace'
  }

  const getTaskSubtitle = (task: TaskEntry) => {
    const command = task.command ?? task.path ?? 'command'
    const cwd = task.cwd ?? task.workingDirectory
    return cwd ? `${command} - ${cwd}` : command
  }

  const scheduleProjectTasks = (groups: GroupInfo[]) => {
    const panes = groups
      .flatMap((group) => group.tabs)
      .filter((pane) => pane.taskId && pane.autoRun !== false)
      .filter((pane) => {
        const task = findTask(pane.taskId as string)
        return !task || task.autoRun !== false
      })

    const sorted = panes.slice().sort((a, b) => {
      const left = a.startOrder ?? Number.MAX_SAFE_INTEGER
      const right = b.startOrder ?? Number.MAX_SAFE_INTEGER
      if (left === right) {
        return a.title.localeCompare(b.title)
      }
      return left - right
    })

    sorted.forEach((pane, index) => {
      const taskId = pane.taskId as string
      pendingTasks.current.set(pane.id, taskId)
      schedulePendingTask(pane.id, taskId, 0, index * 250)
    })
  }

  const openProject = (project: ProjectDefinition) => {
    resetWorkspace()
    setProjectMenuProjectId(null)
    setActiveProjectId(project.id)
    setTaskProjectId(project.id)
    setRecentProjectIds((current) => {
      const next = [project.id, ...current.filter((item) => item !== project.id)]
      return next.slice(0, 6)
    })
    const root = project.root
    const layout = project.layout
    if (!layout) {
      createTab(selectedProfileId, true, { title: project.name, pane: { cwd: root } })
      return
    }

    if (layout.type === 'tabs') {
      const group = buildGroupFromLayout(layout, root)
      if (group) {
        createWorkspace([group], {
          title: project.name,
          split: false,
          splitDirection: 'vertical',
        })
        scheduleProjectTasks([group])
        return
      }
      createTab(selectedProfileId, true, { title: project.name, pane: { cwd: root } })
      return
    }

    if (layout.type === 'split') {
      const groups = (layout.panes ?? [])
        .map((pane) => buildGroupFromLayout(pane, root))
        .filter((group): group is GroupInfo => group !== null)
        .slice(0, 2)

      if (groups.length === 0) {
        createTab(selectedProfileId, true, { title: project.name, pane: { cwd: root } })
        return
      }

      createWorkspace(groups, {
        title: project.name,
        split: groups.length > 1,
        splitDirection: layout.direction ?? 'vertical',
      })
      scheduleProjectTasks(groups)
    }
  }

  const selectProject = (project: ProjectDefinition) => {
    setActiveProjectId(project.id)
    setTaskProjectId(project.id)
    setRecentProjectIds((current) => {
      const next = [project.id, ...current.filter((item) => item !== project.id)]
      return next.slice(0, 6)
    })
  }

  const togglePinnedProject = (projectId: string) => {
    setPinnedProjectIds((current) => {
      if (current.includes(projectId)) {
        return current.filter((id) => id !== projectId)
      }
      return [projectId, ...current]
    })
  }

  function toggleLogging() {
    const pane = getActivePane()
    if (!pane?.sessionId) {
      window.alert('No active session to log.')
      return
    }
    if (loggingSessions.current.has(pane.sessionId)) {
      postMessage({ type: 'logging.stop', sessionId: pane.sessionId })
      return
    }

    const defaultName = `session-${pane.sessionId}.log`
    const path = window.prompt('Log file path', defaultName)
    if (!path) {
      return
    }
    postMessage({ type: 'logging.start', sessionId: pane.sessionId, path })
  }

  const uploadFile = async (file: File) => {
    const pane = getActivePane()
    if (!pane?.sessionId) {
      window.alert('No active session to receive files.')
      return
    }

    const suggested = file.name
    const targetPath = window.prompt('Save file as', suggested)
    if (!targetPath) {
      return
    }

    const transferId = crypto.randomUUID()
    postMessage({
      type: 'file.upload.start',
      sessionId: pane.sessionId,
      transferId,
      targetPath,
      fileName: file.name,
      size: file.size,
    })

    const chunkSize = 64 * 1024
    let offset = 0
    while (offset < file.size) {
      const slice = file.slice(offset, offset + chunkSize)
      const buffer = await slice.arrayBuffer()
      const base64 = arrayBufferToBase64(buffer)
      postMessage({
        type: 'file.upload.chunk',
        sessionId: pane.sessionId,
        transferId,
        data: base64,
      })
      offset += chunkSize
    }

    postMessage({ type: 'file.upload.end', sessionId: pane.sessionId, transferId })
  }

  const arrayBufferToBase64 = (buffer: ArrayBuffer | Uint8Array) => {
    const bytes = buffer instanceof Uint8Array ? buffer : new Uint8Array(buffer)
    let binary = ''
    const chunk = 0x8000
    for (let i = 0; i < bytes.length; i += chunk) {
      binary += String.fromCharCode(...bytes.subarray(i, i + chunk))
    }
    return btoa(binary)
  }

  const handleProfileSelect = (profile: TerminalProfile) => {
    setProfileMenuOpen(false)
    if (profile.isTemplate) {
      const name = window.prompt('Profile name')
      if (!name) {
        return
      }
      const command = window.prompt('Executable path (e.g. C:\\tools\\my.exe)')
      if (!command) {
        return
      }
      const args = window.prompt('Arguments (optional)') ?? ''
      const cwd = window.prompt('Working directory (optional)') ?? ''
      const profileId = `custom-${crypto.randomUUID()}`
      const newProfile: TerminalProfile = {
        id: profileId,
        name,
        command,
        arguments: args || undefined,
        workingDirectory: cwd || undefined,
        isBuiltin: false,
        isAvailable: true,
      }
      postMessage({ type: 'profiles.save', profile: newProfile })
      createTab(profileId, true)
      return
    }

    setSelectedProfileId(profile.id)
    createTab(profile.id, true)
  }

  const getTaskKey = (task: TaskEntry) => task.id ?? task.name

  const openProjectEditor = (project?: ProjectDefinition) => {
    setProjectMenuProjectId(null)
    setProjectEditorOpen(true)
    setProjectEditorTab('basics')
    setProjectEditorQuery('')
    setProjectEditorTaskQuery('')
    const target =
      project ??
      (activeProjectId ? projects.find((item) => item.id === activeProjectId) : null) ??
      projects[0] ??
      null
    setProjectEditorProjectId(target?.id ?? null)
    setProjectEditorPaneIndex(0)
    setProjectEditorItemIndex(0)
  }

  const closeProjectEditor = () => {
    setProjectEditorOpen(false)
  }

  const createProject = () => {
    const newProject: ProjectDefinition = {
      id: `project-${crypto.randomUUID()}`,
      name: 'New project',
      root: '',
      layout: { type: 'tabs', items: [] },
    }
    setProjects((current) => [...current, newProject])
    setProjectEditorProjectId(newProject.id)
    setProjectEditorOpen(true)
    setProjectEditorTab('basics')
    setProjectEditorTaskQuery('')
    setProjectEditorPaneIndex(0)
    setProjectEditorItemIndex(0)
  }

  const duplicateProject = (project: ProjectDefinition | null) => {
    if (!project) {
      return
    }
    const copy = JSON.parse(JSON.stringify(project)) as ProjectDefinition
    copy.id = `project-${crypto.randomUUID()}`
    copy.name = `${project.name} copy`
    setProjects((current) => [...current, copy])
    setProjectEditorProjectId(copy.id)
  }

  const deleteProject = (project: ProjectDefinition | null) => {
    if (!project) {
      return
    }
    if (!window.confirm(`Delete project "${project.name}"?`)) {
      return
    }
    setProjects((current) => {
      const next = current.filter((item) => item.id !== project.id)
      const nextSelected = next[0]?.id ?? null
      setProjectEditorProjectId(nextSelected)
      return next
    })
  }

  const updateSelectedProject = (
    updater: (project: ProjectDefinition) => ProjectDefinition
  ) => {
    if (!projectEditorProjectId) {
      return
    }
    setProjects((current) =>
      current.map((project) =>
        project.id === projectEditorProjectId ? updater(project) : project
      )
    )
  }

  const createEmptyTabLayout = (): ProjectLayout => ({ type: 'tabs', items: [] })

  const normalizeLayout = (layout?: ProjectLayout): ProjectLayout =>
    layout ?? createEmptyTabLayout()

  const updateSelectedProjectLayout = (
    updater: (layout: ProjectLayout) => ProjectLayout
  ) => {
    updateSelectedProject((project) => {
      const baseLayout = normalizeLayout(project.layout)
      return { ...project, layout: updater(baseLayout) }
    })
  }

  const updateLayoutItems = (
    paneIndex: number,
    updater: (items: ProjectLayoutItem[]) => ProjectLayoutItem[]
  ) => {
    updateSelectedProjectLayout((layout) => {
      if (layout.type === 'split') {
        const panes = layout.panes?.length
          ? layout.panes
          : [createEmptyTabLayout(), createEmptyTabLayout()]
        const nextPanes = panes.map((pane, index) => {
          const safePane = pane.type === 'tabs' ? pane : createEmptyTabLayout()
          if (index !== paneIndex) {
            return { ...safePane, items: [...(safePane.items ?? [])] }
          }
          return {
            ...safePane,
            items: updater([...(safePane.items ?? [])]),
          }
        })
        return { ...layout, panes: nextPanes }
      }

      return { ...layout, items: updater([...(layout.items ?? [])]) }
    })
  }

  const applySplit = (direction: 'vertical' | 'horizontal') => {
    updateSelectedProjectLayout((layout) => {
      if (layout.type === 'split') {
        const panes = layout.panes?.length
          ? layout.panes
          : [createEmptyTabLayout(), createEmptyTabLayout()]
        return { ...layout, direction, panes }
      }
      return {
        type: 'split',
        direction,
        panes: [layout, createEmptyTabLayout()],
      }
    })
    setProjectEditorPaneIndex(0)
    setProjectEditorItemIndex(0)
  }

  const removeSplit = () => {
    updateSelectedProjectLayout((layout) => {
      if (layout.type !== 'split') {
        return layout
      }
      const panes = layout.panes ?? []
      const firstPane = panes[0]
      if (firstPane && firstPane.type === 'tabs') {
        return { ...firstPane, items: [...(firstPane.items ?? [])] }
      }
      return createEmptyTabLayout()
    })
    setProjectEditorPaneIndex(0)
    setProjectEditorItemIndex(0)
  }

  const updateTaskEntry = (taskId: string, updater: (task: TaskEntry) => TaskEntry) => {
    setTasks((current) =>
      current.map((task) => (getTaskKey(task) === taskId ? updater(task) : task))
    )
  }

  const resolveTaskDirectory = (task: TaskEntry) => task.workingDirectory ?? task.cwd ?? ''

  const stripProjectRoot = (path: string, root: string) => {
    if (!root) {
      return path
    }
    const normalizedRoot = root.endsWith('\\') || root.endsWith('/')
      ? root
      : `${root}\\`
    const lowerPath = path.toLowerCase()
    const lowerRoot = normalizedRoot.toLowerCase()
    if (lowerPath.startsWith(lowerRoot)) {
      return path.slice(normalizedRoot.length).replace(/^\\+/, '')
    }
    return path
  }

  const joinProjectRoot = (root: string, relative: string) => {
    if (!root) {
      return relative
    }
    const trimmedRoot = root.replace(/[\\/]+$/, '')
    const trimmedRelative = relative.replace(/^[\\/]+/, '')
    return trimmedRelative ? `${trimmedRoot}\\${trimmedRelative}` : trimmedRoot
  }

  const saveScriptsFile = async () => {
    if (!scriptsPath) {
      window.alert('Scripts path not available.')
      return
    }
    const payload = `${JSON.stringify({ projects, tasks }, null, 2)}\n`
    const encoder = new TextEncoder()
    const bytes = encoder.encode(payload)
    const transferId = crypto.randomUUID()
    postMessage({
      type: 'file.upload.start',
      transferId,
      targetPath: scriptsPath,
      size: bytes.length,
    })
    const chunkSize = 64 * 1024
    for (let offset = 0; offset < bytes.length; offset += chunkSize) {
      const chunk = bytes.slice(offset, offset + chunkSize)
      postMessage({
        type: 'file.upload.chunk',
        transferId,
        data: arrayBufferToBase64(chunk.buffer),
      })
    }
    postMessage({ type: 'file.upload.end', transferId })
  }

  const activePane = getActivePane()
  const activeShellKind = activePane ? resolveShellKind(activePane.profileId) : null
  const contextMenuStyle = contextMenu.open
    ? {
        left: Math.min(contextMenu.x, window.innerWidth - 180),
        top: Math.min(contextMenu.y, window.innerHeight - 110),
      }
    : { left: 0, top: 0 }
  const availableTasks = tasks.filter(
    (task) =>
      task.useTerminal !== false &&
      (!task.profileId || task.profileId === activePane?.profileId)
  )
  const activeProject = projects.find((project) => project.id === activeProjectId) ?? null
  const taskProject = taskProjectId
    ? projects.find((project) => project.id === taskProjectId) ?? activeProject
    : activeProject
  const taskProjectRoot = taskProject?.root
  const projectTasks = taskProjectRoot
    ? availableTasks.filter((task) => {
        const cwd = task.cwd ?? task.workingDirectory
        return cwd?.toLowerCase().startsWith(taskProjectRoot.toLowerCase())
      })
    : []
  const globalTasks = availableTasks.filter((task) => !projectTasks.includes(task))
  const taskQueryLower = taskQuery.trim().toLowerCase()
  const filteredProjectTasks = projectTasks.filter((task) =>
    taskQueryLower
      ? `${task.name} ${task.command ?? ''} ${task.path ?? ''}`
          .toLowerCase()
          .includes(taskQueryLower)
      : true
  )
  const filteredGlobalTasks = globalTasks.filter((task) =>
    taskQueryLower
      ? `${task.name} ${task.command ?? ''} ${task.path ?? ''}`
          .toLowerCase()
          .includes(taskQueryLower)
      : true
  )
  const profileQueryLower = profileQuery.trim().toLowerCase()
  const filteredProfiles = profiles.filter((profile) =>
    profileQueryLower ? profile.name.toLowerCase().includes(profileQueryLower) : true
  )
  const projectQueryLower = projectQuery.trim().toLowerCase()
  const projectMatchesQuery = (project: ProjectDefinition) => {
    if (!projectQueryLower) {
      return true
    }
    const root = project.root?.toLowerCase() ?? ''
    return (
      project.name.toLowerCase().includes(projectQueryLower) ||
      (root && root.includes(projectQueryLower))
    )
  }
  const filteredProjects = projects.filter((project) => projectMatchesQuery(project))
  const projectEditorQueryLower = projectEditorQuery.trim().toLowerCase()
  const filteredEditorProjects = projects.filter((project) =>
    projectEditorQueryLower ? project.name.toLowerCase().includes(projectEditorQueryLower) : true
  )
  const editorProject =
    projects.find((project) => project.id === projectEditorProjectId) ?? null
  const editorLayout = editorProject ? normalizeLayout(editorProject.layout) : null
  const editorLayoutDirection =
    editorLayout?.type === 'split' ? editorLayout.direction ?? 'vertical' : 'vertical'
  const editorIsSplit = editorLayout?.type === 'split'
  const editorPanes = editorLayout
    ? editorLayout.type === 'split'
      ? editorLayout.panes?.length
        ? editorLayout.panes
        : [createEmptyTabLayout(), createEmptyTabLayout()]
      : [editorLayout]
    : []
  const editorPaneIndex = Math.min(
    projectEditorPaneIndex,
    Math.max(editorPanes.length - 1, 0)
  )
  const editorPane = editorPanes[editorPaneIndex]
  const editorItems = editorPane?.items ?? []
  const editorItemIndex = editorItems.length
    ? Math.min(projectEditorItemIndex, editorItems.length - 1)
    : 0
  const editorItem = editorItems[editorItemIndex] ?? null
  const editorProjectRoot = editorProject?.root ?? ''
  const projectEditorTaskQueryLower = projectEditorTaskQuery.trim().toLowerCase()
  const taskMatchesQuery = (task: TaskEntry) =>
    projectEditorTaskQueryLower
      ? `${task.name} ${task.command ?? ''} ${task.path ?? ''}`
          .toLowerCase()
          .includes(projectEditorTaskQueryLower)
      : true
  const editorProjectTasks = tasks.filter((task) => {
    if (!editorProjectRoot) {
      return taskMatchesQuery(task)
    }
    const cwd = resolveTaskDirectory(task)
    const inRoot = cwd.toLowerCase().startsWith(editorProjectRoot.toLowerCase())
    return inRoot && taskMatchesQuery(task)
  })
  const editorOtherTasks = editorProjectRoot
    ? tasks.filter((task) => {
        const cwd = resolveTaskDirectory(task)
        const inRoot = cwd.toLowerCase().startsWith(editorProjectRoot.toLowerCase())
        return !inRoot && taskMatchesQuery(task)
      })
    : []
  const pinnedProjects = pinnedProjectIds
    .map((id) => projects.find((project) => project.id === id))
    .filter((project): project is ProjectDefinition => Boolean(project))
    .filter((project) => projectMatchesQuery(project))
  const pinnedProjectSet = new Set(pinnedProjects.map((project) => project.id))
  const recentProjects = recentProjectIds
    .map((id) => projects.find((project) => project.id === id))
    .filter((project): project is ProjectDefinition => Boolean(project))
    .filter((project) => projectMatchesQuery(project))
    .filter((project) => !pinnedProjectSet.has(project.id))
  const recentProjectSet = new Set(recentProjects.map((project) => project.id))
  const otherProjects = filteredProjects.filter(
    (project) => !pinnedProjectSet.has(project.id) && !recentProjectSet.has(project.id)
  )
  const folderPickerPane = folderPickerPaneId ? findPaneById(folderPickerPaneId) : null
  const folderPickerProfile = folderPickerPane ? getProfileById(folderPickerPane.profileId) : null
  const folderPickerCwd = folderPickerPane?.cwd ?? folderPickerProfile?.workingDirectory ?? ''
  const folderPickerCwdDisplay = folderPickerCwd || 'Unknown'
  const folderPickerState =
    folderPickerPane && folderPickerVersion >= 0 ? ensureFolderState(folderPickerPane) : null
  const folderPickerWidthValue = clampFolderPickerWidth(folderPickerWidth)
  const folderPickerCurrent = folderPickerState?.current ?? folderPickerCwd
  const isFolderFavorite = folderPickerCurrent ? isFavoriteFolder(folderPickerCurrent) : false
  const folderQueryLower = folderPickerQuery.trim().toLowerCase()
  const filteredFavoriteFolders = favoriteFolders.filter((path) =>
    path.toLowerCase().includes(folderQueryLower)
  )
  const filteredFolderRecent = folderPickerState
    ? folderPickerState.recent.filter((path) => path.toLowerCase().includes(folderQueryLower))
    : []
  const folderBrowsePath = folderPickerState?.current ?? folderPickerCwd
  const folderEntries = folderListing.path === folderBrowsePath ? folderListing.entries : []
  const folderListingError = folderListing.path === folderBrowsePath ? folderListing.error : undefined
  const folderListingLoading =
    folderListing.path === folderBrowsePath ? folderListing.loading : false
  const folderParent =
    folderListing.path === folderBrowsePath ? folderListing.parent : undefined

  const renderTaskRow = (task: TaskEntry) => {
    const taskKey = getTaskKey(task)
    const cwd = resolveTaskDirectory(task)
    const relativeCwd = stripProjectRoot(cwd, editorProjectRoot)
    return (
      <div key={taskKey} className="task-editor-row">
        <div className="task-editor-meta">
          <div className="task-editor-name">{task.name}</div>
          <div className="task-editor-id">{taskKey}</div>
        </div>
        <div className="task-editor-fields">
          <div className="editor-field">
            <label>Command</label>
            <input
              className="editor-input"
              value={task.command ?? ''}
              onChange={(event) =>
                updateTaskEntry(taskKey, (current) => ({
                  ...current,
                  command: event.target.value,
                }))
              }
            />
          </div>
          <div className="editor-field">
            <label>Working folder</label>
            <input
              className="editor-input"
              value={relativeCwd}
              onChange={(event) => {
                const absolute = joinProjectRoot(editorProjectRoot, event.target.value)
                updateTaskEntry(taskKey, (current) => ({
                  ...current,
                  workingDirectory: absolute,
                  cwd: absolute,
                }))
              }}
            />
          </div>
        </div>
      </div>
    )
  }

  const renderProjectRow = (project: ProjectDefinition) => {
    const badges = getProjectBadges(project)
    const isActive = project.id === activeProjectId
    const isPinned = pinnedProjectIds.includes(project.id)
    const isMenuOpen = projectMenuProjectId === project.id

    return (
      <div key={project.id} className={`project-row ${isActive ? 'active' : ''}`}>
        <button
          className="project-row-main"
          onClick={() => {
            selectProject(project)
            setProjectMenuProjectId(null)
          }}
          onDoubleClick={() => openProject(project)}
        >
          <div className="project-row-title">{project.name}</div>
          <div className="project-row-subtitle">{project.root ?? 'Workspace'}</div>
          <div className="project-row-badges">
            {badges.map((badge) => (
              <span key={`${project.id}-${badge}`} className="project-badge">
                {badge}
              </span>
            ))}
          </div>
        </button>
        <div className="project-row-actions">
          <button
            className="project-row-menu-button"
            onClick={(event) => {
              event.stopPropagation()
              setProjectMenuProjectId((current) => (current === project.id ? null : project.id))
            }}
            title="Project actions"
          >
            ⋯
          </button>
          {isMenuOpen && (
            <div
              className="project-row-menu-panel"
              ref={projectMenuRef}
              onClick={(event) => event.stopPropagation()}
            >
              <button
                className="project-row-menu-item"
                onClick={() => openProject(project)}
              >
                Open workspace
              </button>
              <button
                className="project-row-menu-item"
                onClick={() => openProjectEditor(project)}
              >
                Edit
              </button>
              <button
                className="project-row-menu-item"
                onClick={() => {
                  togglePinnedProject(project.id)
                  setProjectMenuProjectId(null)
                }}
              >
                {isPinned ? 'Unpin' : 'Pin'}
              </button>
            </div>
          )}
        </div>
      </div>
    )
  }

  return (
    <div className={`shell-app theme-${theme}`}>
      <div className="shell-layout">
        <aside className="project-sidebar">
          <div className="project-sidebar-header">
            <div className="project-sidebar-title">Projects</div>
            <div className="project-sidebar-subtitle">Pinned • Recent • All</div>
          </div>
          <input
            className="project-sidebar-search"
            value={projectQuery}
            onChange={(event) => setProjectQuery(event.target.value)}
            placeholder="Search projects..."
          />
          <div className="project-sidebar-sections">
            <div className="project-section">
              <div className="project-section-title">Pinned</div>
              {pinnedProjects.map((project) => renderProjectRow(project))}
              {pinnedProjects.length === 0 && (
                <div className="project-sidebar-empty">No pinned projects</div>
              )}
            </div>
            <div className="project-section">
              <div className="project-section-title">Recent</div>
              {recentProjects.map((project) => renderProjectRow(project))}
              {recentProjects.length === 0 && (
                <div className="project-sidebar-empty">No recent projects</div>
              )}
            </div>
            <div className="project-section">
              <div className="project-section-title">All</div>
              {otherProjects.map((project) => renderProjectRow(project))}
              {otherProjects.length === 0 && (
                <div className="project-sidebar-empty">No projects</div>
              )}
            </div>
          </div>
          <div className="project-sidebar-footer">
            <button className="row-action primary" onClick={() => createProject()}>
              New project
            </button>
            <button className="row-action ghost" onClick={() => openProjectEditor()}>
              Manage
            </button>
          </div>
        </aside>
        <div className="shell-main">
          <header className="shell-toolbar">
            <div className="brand">
              <div className="brand-title">DevShell</div>
              <div className="brand-subtitle">ConPTY bridge + WebView2</div>
              {(scriptsPath || activeProject) && (
                <div className="brand-note">
                  {scriptsPath && <div>Scripts: {scriptsPath}</div>}
                  {activeProject && (
                    <div>Default CWD: {activeProject.root ?? 'Workspace'}</div>
                  )}
                </div>
              )}
            </div>
            <div className="tab-strip">
              {tabs.map((tab) => (
                <button
                  key={tab.id}
                  className={`tab ${activeTabId === tab.id ? 'active' : ''}`}
                  onClick={() => setActiveTabId(tab.id)}
                  onDoubleClick={() => {
                    setEditingTabId(tab.id)
                    setEditingTitle(tab.title)
                  }}
                >
                  <span className="tab-dot" />
                  {editingTabId === tab.id ? (
                    <input
                      className="tab-edit"
                      value={editingTitle}
                      onChange={(event) => setEditingTitle(event.target.value)}
                      onBlur={() => {
                        setTabs((current) =>
                          current.map((item) =>
                            item.id === tab.id
                              ? { ...item, title: editingTitle || item.title }
                              : item
                          )
                        )
                        setEditingTabId(null)
                      }}
                      onKeyDown={(event) => {
                        if (event.key === 'Enter') {
                          event.currentTarget.blur()
                        }
                      }}
                    />
                  ) : (
                    <span>{tab.title}</span>
                  )}
                  <span
                    className="tab-close"
                    onClick={(event) => {
                      event.stopPropagation()
                      closeTab(tab.id)
                    }}
                  >
                    x
                  </span>
                </button>
              ))}
            </div>
            <div className="actions">
              <div className="profile-actions" ref={profileMenuRef}>
                <button
                  className="action primary"
                  onClick={() => {
                    setProfileMenuOpen((current) => !current)
                    setProfileQuery('')
                  }}
                >
                  New tab v
                </button>
                {profileMenuOpen && (
                  <div className="menu-panel profile-menu">
                    <div className="menu-header">
                      <div>
                        <div className="menu-title">Profiles</div>
                        <div className="menu-subtitle">New tab ▾</div>
                      </div>
                    </div>
                    <input
                      className="menu-search"
                      value={profileQuery}
                      onChange={(event) => setProfileQuery(event.target.value)}
                      placeholder="Search profiles..."
                    />
                    <div className="menu-section">
                      <div className="menu-section-title">Profiles</div>
                      {filteredProfiles.map((profile) => (
                        <button
                          key={profile.id}
                          className="menu-row profile-row"
                          disabled={profile.isAvailable === false}
                          onClick={() => handleProfileSelect(profile)}
                        >
                          <div className="row-main">
                            <div className="row-title">{profile.name}</div>
                            {profile.workingDirectory && (
                              <div className="row-subtitle">
                                default folder {profile.workingDirectory}
                              </div>
                            )}
                          </div>
                          {profile.isAvailable === false && (
                            <div className="row-tag warning">missing</div>
                          )}
                        </button>
                      ))}
                      {filteredProfiles.length === 0 && (
                        <div className="menu-empty">No profiles</div>
                      )}
                    </div>
                    <div className="menu-footer">
                      <button
                        className="menu-footer-action"
                        disabled
                        title="Profile management is not wired yet."
                      >
                        Manage profiles...
                      </button>
                    </div>
                  </div>
                )}
              </div>
              <div className="task-actions" ref={taskMenuRef}>
            <button
              className="action ghost"
              disabled={availableTasks.length === 0}
              onClick={() => {
                if (availableTasks.length > 0) {
                  setTaskMenuOpen((current) => !current)
                  setTaskQuery('')
                  setProjectTaskMenuOpen(true)
                }
              }}
            >
              Tasks v
            </button>
            {taskMenuOpen && (
              <div className="menu-panel task-menu">
                <div className="menu-header">
                  <div>
                    <div className="menu-title">Tasks</div>
                    <div className="menu-subtitle">Run scripts</div>
                  </div>
                  <label className="menu-toggle">
                    <input
                      type="checkbox"
                      checked={runAllSessions}
                      onChange={(event) => setRunAllSessions(event.target.checked)}
                    />
                    Run in all sessions
                  </label>
                </div>
                <input
                  className="menu-search"
                  value={taskQuery}
                  onChange={(event) => setTaskQuery(event.target.value)}
                  placeholder="Search tasks..."
                />
                {projects.length > 0 && (
                  <div className="menu-projects">
                    {projects.map((project) => (
                      <button
                        key={project.id}
                        className={`menu-project-button ${
                          project.id === taskProject?.id ? 'active' : ''
                        }`}
                        onClick={() => setTaskProjectId(project.id)}
                      >
                        {project.name}
                      </button>
                    ))}
                  </div>
                )}
                {taskProject && (
                  <div className="menu-section">
                    <button
                      className="menu-row menu-row-button"
                      onClick={() => setProjectTaskMenuOpen((current) => !current)}
                    >
                      <div className="row-main">
                        <div className="row-title">
                          Project tasks ({taskProject.name})
                        </div>
                        <div className="row-subtitle">
                          {projectTaskMenuOpen ? 'Hide list' : 'Show list'}
                        </div>
                      </div>
                      <div className="row-tag">
                        {projectTaskMenuOpen ? 'v' : '>'} {filteredProjectTasks.length}
                      </div>
                    </button>
                    {projectTaskMenuOpen && (
                      <>
                        {filteredProjectTasks.map((task) => (
                          <div key={task.id ?? task.name} className="menu-row task-row">
                            <div className="row-main">
                              <div className="row-title">{task.name}</div>
                              <div className="row-subtitle">
                                {getTaskSubtitle(task)}
                              </div>
                            </div>
                            <div className="row-actions">
                              <button
                                className="row-action primary"
                                onClick={() => handleTaskSelect(task)}
                              >
                                ▶ Run here
                              </button>
                              <button
                                className="row-action ghost"
                                onClick={() => handleTaskRunInNewTab(task)}
                              >
                                ➕ New tab
                              </button>
                            </div>
                          </div>
                        ))}
                        {filteredProjectTasks.length === 0 && (
                          <div className="menu-empty">No project tasks</div>
                        )}
                      </>
                    )}
                  </div>
                )}
                <div className="menu-section">
                  <div className="menu-section-title">Other tasks</div>
                  {filteredGlobalTasks.map((task) => (
                    <div key={task.id ?? task.name} className="menu-row task-row">
                      <div className="row-main">
                        <div className="row-title">{task.name}</div>
                        <div className="row-subtitle">{getTaskSubtitle(task)}</div>
                      </div>
                      <div className="row-actions">
                        <button
                          className="row-action primary"
                          onClick={() => handleTaskSelect(task)}
                        >
                          ▶ Run here
                        </button>
                        <button
                          className="row-action ghost"
                          onClick={() => handleTaskRunInNewTab(task)}
                        >
                          ➕ New tab
                        </button>
                      </div>
                    </div>
                  ))}
                  {filteredGlobalTasks.length === 0 && (
                    <div className="menu-empty">No tasks</div>
                  )}
                </div>
              </div>
            )}
          </div>
          <div className="quick-actions">
            {profiles
              .filter((profile) => profile.id === 'powershell' || profile.id === 'cmd')
              .map((profile) => (
                <button
                  key={profile.id}
                  className="action ghost"
                  disabled={profile.isAvailable === false}
                  onClick={() => handleProfileSelect(profile)}
                >
                  {profile.name}
                </button>
              ))}
            {activePane && (activeShellKind === 'powershell' || activeShellKind === 'cmd') && (
              <>
                <button
                  className="action ghost"
                  onClick={() => void copySelectionForPane(activePane.id)}
                >
                  Copy
                </button>
                <button
                  className="action ghost"
                  disabled={!activePane.sessionId}
                  onClick={() => void pasteClipboardForPane(activePane.id)}
                >
                  Paste
                </button>
              </>
            )}
            <button
              className="action ghost"
              onClick={() => runTaskByIdInActivePane('react-dev')}
            >
              Run npm build
            </button>
          </div>
          <button className="action ghost" onClick={splitActiveTab}>
            Split
          </button>
          <button className="action danger" onClick={killActiveSession}>
            Kill session
          </button>
          <button
            className="action ghost"
            onClick={() => {
              if (activePane) {
                termRefs.current.get(activePane.id)?.clear()
              }
            }}
          >
            Clear
          </button>
          <button className="action ghost" onClick={() => setAutoFit((current) => !current)}>
            {autoFit ? 'Auto fit: on' : 'Auto fit: off'}
          </button>
        </div>
        <div className="status">
          <span className="status-dot" />
          <span>{activePane?.status ?? 'disconnected'}</span>
        </div>
      </header>
      <main className="terminal-pane">
        <div
          className="terminal-frame"
          onDragOver={(event) => {
            event.preventDefault()
            setDragActive(true)
          }}
          onDragLeave={() => setDragActive(false)}
          onDrop={(event) => {
            event.preventDefault()
            setDragActive(false)
            const files = Array.from(event.dataTransfer.files)
            if (files.length === 0) {
              return
            }
            files.forEach((file) => {
              void uploadFile(file)
            })
          }}
        >
          {tabs.map((tab) => (
            <div
              key={tab.id}
              className={`terminal-host ${activeTabId === tab.id ? 'active' : ''}`}
              style={
                tab.split
                  ? {
                      gridTemplateColumns:
                        tab.splitDirection === 'horizontal'
                          ? '1fr'
                          : `${tab.splitRatio * 100}% 6px ${(
                              100 -
                              tab.splitRatio * 100
                            ).toFixed(2)}%`,
                      gridTemplateRows:
                        tab.splitDirection === 'horizontal'
                          ? `${tab.splitRatio * 100}% 6px ${(
                              100 -
                              tab.splitRatio * 100
                            ).toFixed(2)}%`
                          : undefined,
                    }
                  : undefined
              }
            >
              {tab.groups.map((group) => {
                const headerPane =
                  group.tabs.find((pane) => pane.id === group.activeTabId) ?? group.tabs[0]
                const headerProfile = headerPane ? getProfileById(headerPane.profileId) : null
                const headerCwd =
                  headerPane?.cwd ?? headerProfile?.workingDirectory ?? 'Unknown'
                const isFolderOpen =
                  folderPickerOpen && folderPickerPaneId === headerPane?.id && folderPickerState

                return (
                  <div
                    key={group.id}
                    className={`pane ${tab.activeGroupId === group.id ? 'active' : ''}`}
                    onClick={() => focusGroup(group.id)}
                  >
                    <div className="pane-header">
                      <div className="pane-tabs">
                        {group.tabs.map((pane) => (
                          <button
                            key={pane.id}
                            className={`pane-tab ${group.activeTabId === pane.id ? 'active' : ''}`}
                            onClick={(event) => {
                              event.stopPropagation()
                              focusPane(group.id, pane.id)
                            }}
                            onContextMenu={(event) => {
                              event.preventDefault()
                              event.stopPropagation()
                              openFolderPicker(pane.id)
                            }}
                          >
                            <span>{pane.title}</span>
                            <span
                              className="pane-tab-close"
                              onClick={(event) => {
                                event.stopPropagation()
                                closePane(tab.id, group.id, pane.id)
                              }}
                            >
                              x
                            </span>
                          </button>
                        ))}
                      </div>
                      {headerPane && (
                        <div className="pane-actions">
                          <button
                            className={`pane-cwd ${isFolderOpen ? 'active' : ''}`}
                            onClick={(event) => {
                              event.stopPropagation()
                              openFolderPicker(headerPane.id)
                            }}
                            title={headerCwd}
                          >
                            <span className="pane-cwd-icon">📁</span>
                            <span className="pane-cwd-label">CWD:</span>
                            <span className="pane-cwd-path">{headerCwd}</span>
                          </button>
                        </div>
                      )}
                    </div>
                    {group.tabs.map((pane) => (
                      <div
                        key={pane.id}
                        className={`terminal-host-inner ${
                          group.activeTabId === pane.id ? 'active' : 'hidden'
                        }`}
                        ref={(node) => {
                          if (node) {
                            hostRefs.current.set(pane.id, node)
                          } else {
                            hostRefs.current.delete(pane.id)
                          }
                        }}
                      />
                    ))}
                  </div>
                )
              })}
              {tab.split && (
                <div
                  className={`splitter ${
                    tab.splitDirection === 'horizontal' ? 'horizontal' : 'vertical'
                  }`}
                  onMouseDown={(event) => {
                    event.preventDefault()
                    const isHorizontal = tab.splitDirection === 'horizontal'
                    const startPoint = isHorizontal ? event.clientY : event.clientX
                    const startRatio = tab.splitRatio
                    const container = event.currentTarget.parentElement
                    const handleMove = (moveEvent: MouseEvent) => {
                      if (!container) {
                        return
                      }
                      const delta = isHorizontal
                        ? moveEvent.clientY - startPoint
                        : moveEvent.clientX - startPoint
                      const size = isHorizontal
                        ? container.getBoundingClientRect().height
                        : container.getBoundingClientRect().width
                      const ratio = startRatio + delta / size
                      applySplitRatio(tab.id, ratio)
                    }
                    const handleUp = () => {
                      window.removeEventListener('mousemove', handleMove)
                      window.removeEventListener('mouseup', handleUp)
                    }
                    window.addEventListener('mousemove', handleMove)
                    window.addEventListener('mouseup', handleUp)
                  }}
                />
              )}
            </div>
          ))}
          {dragActive && (
            <div className="drop-overlay">
              <div className="drop-message">Drop files to upload</div>
            </div>
          )}
        </div>
      </main>
      <div className="settings-strip">
        <label className="setting">
          <input
            type="checkbox"
            checked={restoreSessions}
            onChange={(event) => setRestoreSessions(event.target.checked)}
          />
          Restore sessions
        </label>
        <label className="setting">
          <input
            type="checkbox"
            checked={copyOnSelect}
            onChange={(event) => setCopyOnSelect(event.target.checked)}
          />
          Copy on select
        </label>
        <label className="setting">
          <input
            type="checkbox"
            checked={rightClickPaste}
            onChange={(event) => setRightClickPaste(event.target.checked)}
          />
          Context menu
        </label>
      </div>
    </div>
  </div>

      {folderPickerOpen && folderPickerPane && folderPickerState && (
        <div className="folder-panel-overlay" onClick={() => setFolderPickerOpen(false)}>
          <aside
            className="folder-picker"
            ref={folderPickerRef}
            onClick={(event) => event.stopPropagation()}
            style={{ width: folderPickerWidthValue, maxWidth: '92vw' }}
          >
            <div className="folder-resizer" onMouseDown={startFolderPickerResize} />
            <div className="folder-picker-header">
              <div>
                <div className="folder-picker-title">
                  Change directory — {folderPickerProfile?.name ?? folderPickerPane.profileId}
                </div>
                <div className="folder-picker-subtitle">
                  {folderPickerPane.title} • Session scoped
                </div>
              </div>
              <div className="folder-picker-actions">
                <div className="folder-picker-nav">
                  <button
                    className="folder-nav"
                    disabled={!folderPickerState?.backStack.length}
                    onClick={() => handleFolderBack(folderPickerPane.id)}
                  >
                    Back
                  </button>
                  <button
                    className="folder-nav"
                    disabled={!folderPickerState?.forwardStack.length}
                    onClick={() => handleFolderForward(folderPickerPane.id)}
                  >
                    Forward
                  </button>
                </div>
                <button className="folder-close" onClick={() => setFolderPickerOpen(false)}>
                  Close
                </button>
              </div>
            </div>
            <div className="folder-section">
              <div className="folder-section-title">Search / paste path</div>
              <div className="folder-input-row">
                <input
                  className="folder-input"
                  value={folderPickerQuery}
                  onChange={(event) => setFolderPickerQuery(event.target.value)}
                  placeholder="Type to filter or paste a path..."
                  autoFocus
                  onKeyDown={(event) => {
                    if (event.key === 'Enter') {
                      applyFolderChange(folderPickerPane.id, folderPickerQuery)
                      setFolderPickerQuery('')
                    }
                  }}
                />
                <button
                  className="folder-go"
                  onClick={() => {
                    applyFolderChange(folderPickerPane.id, folderPickerQuery)
                    setFolderPickerQuery('')
                  }}
                >
                  Go
                </button>
              </div>
            </div>
            <div className="folder-section">
              <div className="folder-section-title">Current</div>
              <div className="folder-current">
                <span className="folder-current-path">
                  {folderPickerState?.current ?? folderPickerCwdDisplay}
                </span>
                <div className="folder-current-actions">
                  <button
                    className="folder-mini"
                    onClick={() => {
                      const value = folderPickerState?.current ?? folderPickerCwd
                      if (value) {
                        navigator.clipboard?.writeText(value).catch(() => undefined)
                      }
                    }}
                  >
                    Copy
                  </button>
                  <button
                    className={`folder-mini ${isFolderFavorite ? 'active' : ''}`}
                    disabled={!folderPickerCurrent}
                    onClick={() => {
                      if (folderPickerCurrent) {
                        toggleFavoriteFolder(folderPickerCurrent)
                      }
                    }}
                  >
                    {isFolderFavorite ? 'Unfavorite' : 'Favorite'}
                  </button>
                </div>
              </div>
            </div>
            <div className="folder-section">
              <div className="folder-section-title">Favorites</div>
              <div className="folder-list">
                {filteredFavoriteFolders.map((path) => (
                  <div key={path} className="folder-favorite-row">
                    <button
                      className="folder-row folder-favorite-main"
                      onClick={() => applyFolderChange(folderPickerPane.id, path)}
                    >
                      {path}
                    </button>
                    <button
                      className="folder-mini folder-favorite-remove"
                      onClick={() => removeFavoriteFolder(path)}
                    >
                      Remove
                    </button>
                  </div>
                ))}
                {filteredFavoriteFolders.length === 0 && (
                  <div className="folder-empty">No favorites yet</div>
                )}
              </div>
            </div>
            <div className="folder-section">
              <div className="folder-section-title">Folders</div>
              <div className="folder-location">
                <span className="folder-location-path">
                  {folderBrowsePath || 'Drives'}
                </span>
                <div className="folder-location-actions">
                  <button
                    className="folder-mini"
                    disabled={!folderParent}
                    onClick={() => {
                      if (folderParent) {
                        applyFolderChange(folderPickerPane.id, folderParent)
                      }
                    }}
                  >
                    Up
                  </button>
                  <button
                    className="folder-mini"
                    disabled={!folderBrowsePath}
                    onClick={() => {
                      if (folderBrowsePath) {
                        requestFolderListing(folderPickerPane.id, folderBrowsePath)
                      }
                    }}
                  >
                    Refresh
                  </button>
                </div>
              </div>
              <div className="folder-list">
                {folderListingLoading && (
                  <div className="folder-empty">Loading folders...</div>
                )}
                {!folderListingLoading && folderListingError && (
                  <div className="folder-empty">{folderListingError}</div>
                )}
                {!folderListingLoading && !folderListingError && folderParent && (
                  <button
                    className="folder-row folder-up"
                    onClick={() => applyFolderChange(folderPickerPane.id, folderParent)}
                  >
                    .. (Up one level)
                  </button>
                )}
                {!folderListingLoading &&
                  !folderListingError &&
                  folderEntries.map((entry) => (
                    <button
                      key={entry.path}
                      className="folder-row folder-entry"
                      onClick={() => applyFolderChange(folderPickerPane.id, entry.path)}
                    >
                      <span className="folder-entry-name">{entry.name}</span>
                    </button>
                  ))}
                {!folderListingLoading &&
                  !folderListingError &&
                  folderEntries.length === 0 && (
                    <div className="folder-empty">No subfolders</div>
                  )}
              </div>
            </div>
            <div className="folder-section">
              <div className="folder-section-title">Recent (this session)</div>
              <div className="folder-list">
                {filteredFolderRecent.map((path) => (
                  <button
                    key={path}
                    className="folder-row"
                    onClick={() => applyFolderChange(folderPickerPane.id, path)}
                  >
                    {path}
                  </button>
                ))}
                {filteredFolderRecent.length === 0 && (
                  <div className="folder-empty">No folders yet</div>
                )}
              </div>
            </div>
            <div className="folder-section">
              <div className="folder-section-title">Convenience</div>
              <div className="folder-list">
                <button
                  className="folder-row"
                  disabled={!folderPickerState?.startFolder}
                  onClick={() => {
                    if (folderPickerState?.startFolder) {
                      applyFolderChange(folderPickerPane.id, folderPickerState.startFolder)
                    }
                  }}
                >
                  Back to start folder
                </button>
                <button
                  className="folder-row"
                  onClick={() => openFolderBrowser(folderPickerPane.id)}
                >
                  Browse...
                </button>
                <button
                  className="folder-row"
                  disabled={!folderPickerState?.current}
                  onClick={() => openFolderInExplorer(folderPickerPane.id)}
                >
                  Open in Explorer
                </button>
              </div>
            </div>
          </aside>
        </div>
      )}

      {paletteOpen && (
        <div className="palette-overlay" onClick={() => setPaletteOpen(false)}>
          <div className="palette" onClick={(event) => event.stopPropagation()}>
            <input
              className="palette-input"
              value={paletteQuery}
              onChange={(event) => setPaletteQuery(event.target.value)}
              placeholder="Type a command..."
              autoFocus
            />
            <div className="palette-list">
              {filteredCommands.map((command) => (
                <button
                  key={command.id}
                  className="palette-item"
                  onClick={() => handlePaletteSelect(command)}
                >
                  {command.label}
                </button>
              ))}
              {filteredCommands.length === 0 && <div className="palette-empty">No matches</div>}
            </div>
          </div>
        </div>
      )}

      {searchOpen && (
        <div className="search-overlay">
          <div className="search-box">
            <input
              value={searchQuery}
              onChange={(event) => setSearchQuery(event.target.value)}
              placeholder="Search scrollback..."
              className="search-input"
            />
            <button className="action ghost" onClick={handleSearch}>
              Find next
            </button>
            <button className="action ghost" onClick={() => setSearchOpen(false)}>
              Close
            </button>
          </div>
        </div>
      )}

      {contextMenu.open && contextMenu.paneId && (
        <div className="context-menu" ref={contextMenuRef} style={contextMenuStyle}>
          <button
            className="context-menu-item"
            disabled={!contextMenu.hasSelection}
            onClick={() => {
              void copySelectionForPane(contextMenu.paneId as string)
              closeContextMenu()
            }}
          >
            Copy
          </button>
          <button
            className="context-menu-item"
            onClick={() => {
              void pasteClipboardForPane(contextMenu.paneId as string)
              closeContextMenu()
            }}
          >
            Paste
          </button>
        </div>
      )}

      {projectEditorOpen && (
        <div className="project-editor-overlay" onClick={closeProjectEditor}>
          <div
            className="project-editor"
            onClick={(event) => event.stopPropagation()}
          >
            <aside className="project-editor-sidebar">
              <div className="project-editor-sidebar-header">
                <div className="project-editor-title">Projects</div>
                <div className="project-editor-subtitle">Edit / manage</div>
              </div>
              <input
                className="project-editor-search"
                value={projectEditorQuery}
                onChange={(event) => setProjectEditorQuery(event.target.value)}
                placeholder="Search projects..."
              />
              <div className="project-editor-list">
                {filteredEditorProjects.map((project) => (
                  <button
                    key={project.id}
                    className={`project-editor-item ${
                      project.id === projectEditorProjectId ? 'active' : ''
                    }`}
                    onClick={() => {
                      setProjectEditorProjectId(project.id)
                      setProjectEditorPaneIndex(0)
                      setProjectEditorItemIndex(0)
                    }}
                  >
                    <div className="project-editor-item-title">{project.name}</div>
                    <div className="project-editor-item-subtitle">
                      {getProjectSubtitle(project)}
                    </div>
                  </button>
                ))}
                {filteredEditorProjects.length === 0 && (
                  <div className="project-editor-empty">No projects</div>
                )}
              </div>
              <div className="project-editor-sidebar-actions">
                <button className="row-action primary" onClick={() => createProject()}>
                  New
                </button>
                <button
                  className="row-action ghost"
                  onClick={() => duplicateProject(editorProject)}
                  disabled={!editorProject}
                >
                  Duplicate
                </button>
                <button
                  className="row-action danger"
                  onClick={() => deleteProject(editorProject)}
                  disabled={!editorProject}
                >
                  Delete
                </button>
              </div>
            </aside>
            <section className="project-editor-main">
              <div className="project-editor-toolbar">
                <div>
                  <div className="project-editor-heading">Project Editor</div>
                  <div className="project-editor-subheading">
                    {editorProject?.name ?? 'Select a project'}
                  </div>
                </div>
                <div className="project-editor-toolbar-actions">
                  <button
                    className="action primary"
                    onClick={() => void saveScriptsFile()}
                    disabled={!scriptsPath}
                    title={scriptsPath ? 'Save scripts.json' : 'Scripts path unavailable'}
                  >
                    Save
                  </button>
                  <button
                    className="action ghost"
                    onClick={() => {
                      if (editorProject) {
                        openProject(editorProject)
                        closeProjectEditor()
                      }
                    }}
                    disabled={!editorProject}
                  >
                    Launch
                  </button>
                  <button className="action ghost" onClick={resetWorkspace}>
                    Stop
                  </button>
                  <button
                    className="action ghost"
                    onClick={() => {
                      if (editorProject) {
                        resetWorkspace()
                        openProject(editorProject)
                        closeProjectEditor()
                      }
                    }}
                    disabled={!editorProject}
                  >
                    Relaunch
                  </button>
                  <button className="action danger" onClick={closeProjectEditor}>
                    Close
                  </button>
                </div>
              </div>
              <div className="project-editor-tabs">
                {(['basics', 'layout', 'tasks'] as const).map((tab) => (
                  <button
                    key={tab}
                    className={`project-editor-tab ${
                      projectEditorTab === tab ? 'active' : ''
                    }`}
                    onClick={() => setProjectEditorTab(tab)}
                  >
                    {tab === 'basics' && 'Basics'}
                    {tab === 'layout' && 'Layout'}
                    {tab === 'tasks' && 'Tasks'}
                  </button>
                ))}
              </div>
              <div className="project-editor-panel">
                {!editorProject && (
                  <div className="editor-empty">Select a project to start editing.</div>
                )}

                {editorProject && projectEditorTab === 'basics' && (
                  <div className="editor-grid">
                    <div className="editor-field">
                      <label>Project name</label>
                      <input
                        className="editor-input"
                        value={editorProject.name}
                        onChange={(event) =>
                          updateSelectedProject((project) => ({
                            ...project,
                            name: event.target.value,
                          }))
                        }
                      />
                    </div>
                    <div className="editor-field">
                      <label>Root folder</label>
                      <div className="editor-input-row">
                        <input
                          className="editor-input"
                          value={editorProject.root ?? ''}
                          onChange={(event) =>
                            updateSelectedProject((project) => ({
                              ...project,
                              root: event.target.value,
                            }))
                          }
                          placeholder="G:\\work\\MyProject"
                        />
                        <button
                          className="row-action ghost"
                          onClick={() => {
                            if (activePane?.cwd) {
                              updateSelectedProject((project) => ({
                                ...project,
                                root: activePane.cwd,
                              }))
                            }
                          }}
                          disabled={!activePane?.cwd}
                        >
                          Use active
                        </button>
                      </div>
                    </div>
                    <div className="editor-field">
                      <label>Project id</label>
                      <input
                        className="editor-input"
                        value={editorProject.id}
                        readOnly
                      />
                    </div>
                  </div>
                )}

                {editorProject && projectEditorTab === 'layout' && (
                  <div className="layout-editor">
                    <div className="layout-preview">
                      <div
                        className={`layout-canvas ${
                          editorIsSplit ? `split-${editorLayoutDirection}` : 'single'
                        }`}
                      >
                        {editorPanes.map((pane, index) => (
                          <div
                            key={`pane-${index}`}
                            className={`layout-pane ${
                              index === editorPaneIndex ? 'active' : ''
                            }`}
                            onClick={() => setProjectEditorPaneIndex(index)}
                          >
                            <div className="layout-pane-title">
                              Pane {index + 1}
                            </div>
                            <div className="layout-chip-list">
                              {(pane.items ?? []).map((item, itemIndex) => (
                                <button
                                  key={`${item.title}-${itemIndex}`}
                                  className={`layout-chip ${
                                    index === editorPaneIndex &&
                                    itemIndex === editorItemIndex
                                      ? 'active'
                                      : ''
                                  }`}
                                  onClick={() => {
                                    setProjectEditorPaneIndex(index)
                                    setProjectEditorItemIndex(itemIndex)
                                  }}
                                >
                                  {item.title || `Tab ${itemIndex + 1}`}
                                </button>
                              ))}
                              {(pane.items ?? []).length === 0 && (
                                <div className="layout-empty">No tabs</div>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                      <div className="layout-controls">
                        <button
                          className="row-action ghost"
                          onClick={() => applySplit('vertical')}
                        >
                          Split vertical
                        </button>
                        <button
                          className="row-action ghost"
                          onClick={() => applySplit('horizontal')}
                        >
                          Split horizontal
                        </button>
                        <button
                          className="row-action ghost"
                          onClick={removeSplit}
                          disabled={!editorIsSplit}
                        >
                          Remove pane
                        </button>
                        <button
                          className="row-action primary"
                          onClick={() => {
                            const nextIndex = editorItems.length
                            updateLayoutItems(editorPaneIndex, (items) => [
                              ...items,
                              {
                                title: `Tab ${items.length + 1}`,
                                profileId: selectedProfileId,
                              },
                            ])
                            setProjectEditorItemIndex(nextIndex)
                          }}
                        >
                          Add tab
                        </button>
                        <button
                          className="row-action danger"
                          onClick={() => {
                            if (!editorItem) {
                              return
                            }
                            updateLayoutItems(editorPaneIndex, (items) =>
                              items.filter((_, index) => index !== editorItemIndex)
                            )
                            setProjectEditorItemIndex((current) => Math.max(0, current - 1))
                          }}
                          disabled={!editorItem}
                        >
                          Remove tab
                        </button>
                      </div>
                    </div>
                    <div className="layout-details">
                      {!editorItem && (
                        <div className="editor-empty">Select a tab to edit.</div>
                      )}
                      {editorItem && (
                        <div className="layout-form">
                          <div className="editor-field">
                            <label>Title</label>
                            <input
                              className="editor-input"
                              value={editorItem.title}
                              onChange={(event) =>
                                updateLayoutItems(editorPaneIndex, (items) =>
                                  items.map((item, index) =>
                                    index === editorItemIndex
                                      ? { ...item, title: event.target.value }
                                      : item
                                  )
                                )
                              }
                            />
                          </div>
                          <div className="editor-field">
                            <label>Profile</label>
                            <select
                              className="editor-select"
                              value={editorItem.profileId ?? ''}
                              onChange={(event) =>
                                updateLayoutItems(editorPaneIndex, (items) =>
                                  items.map((item, index) =>
                                    index === editorItemIndex
                                      ? {
                                          ...item,
                                          profileId:
                                            event.target.value || undefined,
                                        }
                                      : item
                                  )
                                )
                              }
                            >
                              <option value="">Default ({selectedProfileId})</option>
                              {profiles.map((profile) => (
                                <option key={profile.id} value={profile.id}>
                                  {profile.name}
                                </option>
                              ))}
                            </select>
                          </div>
                          <div className="editor-field">
                            <label>Task</label>
                            <select
                              className="editor-select"
                              value={editorItem.taskId ?? ''}
                              onChange={(event) =>
                                updateLayoutItems(editorPaneIndex, (items) =>
                                  items.map((item, index) =>
                                    index === editorItemIndex
                                      ? {
                                          ...item,
                                          taskId: event.target.value || undefined,
                                        }
                                      : item
                                  )
                                )
                              }
                            >
                              <option value="">No task</option>
                              {tasks.map((task) => (
                                <option key={getTaskKey(task)} value={getTaskKey(task)}>
                                  {task.name}
                                </option>
                              ))}
                            </select>
                          </div>
                          <div className="editor-field editor-field-inline">
                            <label>Auto-run</label>
                            <input
                              type="checkbox"
                              checked={editorItem.autoRun !== false}
                              onChange={(event) =>
                                updateLayoutItems(editorPaneIndex, (items) =>
                                  items.map((item, index) =>
                                    index === editorItemIndex
                                      ? { ...item, autoRun: event.target.checked }
                                      : item
                                  )
                                )
                              }
                            />
                          </div>
                          <div className="editor-field">
                            <label>Start order</label>
                            <input
                              className="editor-input"
                              type="number"
                              value={editorItem.startOrder ?? ''}
                              onChange={(event) => {
                                const value = event.target.value
                                updateLayoutItems(editorPaneIndex, (items) =>
                                  items.map((item, index) =>
                                    index === editorItemIndex
                                      ? {
                                          ...item,
                                          startOrder: value ? Number(value) : undefined,
                                        }
                                      : item
                                  )
                                )
                              }}
                              placeholder="1"
                            />
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {editorProject && projectEditorTab === 'tasks' && (
                  <div className="task-editor">
                    <div className="task-editor-header">
                      <div>
                        <div className="task-editor-title">Tasks</div>
                        <div className="task-editor-subtitle">
                          Edit command + working folder (relative to project root)
                        </div>
                      </div>
                      <input
                        className="project-editor-search"
                        value={projectEditorTaskQuery}
                        onChange={(event) => setProjectEditorTaskQuery(event.target.value)}
                        placeholder="Filter tasks..."
                      />
                    </div>
                    <div className="task-editor-list">
                      {editorProjectRoot && (
                        <div className="task-editor-section">Project tasks</div>
                      )}
                      {editorProjectTasks.map((task) => renderTaskRow(task))}
                      {editorProjectTasks.length === 0 && (
                        <div className="editor-empty">
                          {editorProjectRoot
                            ? 'No tasks under project root.'
                            : 'No tasks defined.'}
                        </div>
                      )}
                      {editorOtherTasks.length > 0 && (
                        <>
                          <div className="task-editor-section">Other tasks</div>
                          {editorOtherTasks.map((task) => renderTaskRow(task))}
                        </>
                      )}
                    </div>
                  </div>
                )}
              </div>
            </section>
          </div>
        </div>
      )}
    </div>
  )
}

export default App


