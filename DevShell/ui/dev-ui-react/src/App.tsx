import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
  type MouseEvent as ReactMouseEvent,
} from 'react'
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
  workspace?: WorkspaceConfig
  environment?: Record<string, string>
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

type WorkspaceGlobals = {
  defaultShell?: string
  terminal?: {
    fontSize?: number
    scrollback?: number
  }
  vars?: Record<string, string>
}

type WorkspaceTaskStep = {
  run: string
}

type WorkspaceTask = {
  group?: string
  shell?: string
  cwd?: string
  steps?: WorkspaceTaskStep[]
  dependsOn?: string[]
  runInNewTab?: boolean
  focusTab?: boolean
  useTemplate?: string
}

type WorkspaceLaunchTab = {
  task: string
  title?: string
}

type WorkspaceLaunch = {
  id: string
  name: string
  projectId: string
  openTabs: WorkspaceLaunchTab[]
}

type WorkspaceConfig = {
  version?: number
  globals?: WorkspaceGlobals
  templates?: Record<string, WorkspaceTask>
  projects?: ProjectDefinition[]
  workspaces?: WorkspaceLaunch[]
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
  pinned?: boolean
  vars?: Record<string, string>
  bootstrap?: WorkspaceTask
  tasks?: Record<string, WorkspaceTask>
  quickTasks?: string[]
  layout?: ProjectLayout
}

type ResolvedTaskStep = {
  run: string
  cwd?: string
}

type ResolvedTask = {
  key: string
  name: string
  projectId: string
  group: string
  shell?: string
  cwd?: string
  steps: ResolvedTaskStep[]
  dependsOn: string[]
  runInNewTab?: boolean
  focusTab?: boolean
}

type TaskExecutionStep = {
  run: string
  cwd?: string
  taskName: string
}

type PendingTaskRun =
  | { kind: 'legacy'; taskId: string }
  | { kind: 'workspace'; taskKey: string }

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
  leftWidth?: number
  rightWidth?: number
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
  const pendingTasks = useRef<Map<string, PendingTaskRun>>(new Map())
  const bootstrappedSessions = useRef<Map<string, Set<string>>>(new Map())
  const closedTabs = useRef<PersistedTab[]>([])
  const profileMenuRef = useRef<HTMLDivElement | null>(null)
  const projectMenuRef = useRef<HTMLDivElement | null>(null)
  const taskMenuRef = useRef<HTMLDivElement | null>(null)
  const shellLayoutRef = useRef<HTMLDivElement | null>(null)
  const folderPickerRef = useRef<HTMLDivElement | null>(null)
  const folderPickerWasOpen = useRef(false)
  const contextMenuRef = useRef<HTMLDivElement | null>(null)
  const loggingSessions = useRef<Set<string>>(new Set())
  const folderNav = useRef<Map<string, FolderNavState>>(new Map())
  const [profiles, setProfiles] = useState<TerminalProfile[]>([])
  const [workspace, setWorkspace] = useState<WorkspaceConfig>({ version: 2, projects: [] })
  const [projects, setProjects] = useState<ProjectDefinition[]>([])
  const [legacyTasks, setLegacyTasks] = useState<TaskEntry[]>([])
  const [environment, setEnvironment] = useState<Record<string, string>>({})
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
  const [leftWidth, setLeftWidth] = useState(280)
  const [rightWidth, setRightWidth] = useState(370)
  const [folderPickerTab, setFolderPickerTab] = useState<
    'browse' | 'favorites' | 'recent' | 'tools'
  >('browse')
  const [folderListing, setFolderListing] = useState<FolderListing>({
    path: '',
    entries: [],
    loading: false,
  })
  const [profileQuery, setProfileQuery] = useState('')
  const [projectQuery, setProjectQuery] = useState('')
  const [projectFilter, setProjectFilter] = useState<'all' | 'pinned' | 'recent'>('all')
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
  const autoFitRef = useRef(autoFit)
  const copyOnSelectRef = useRef(copyOnSelect)
  const rightClickPasteRef = useRef(rightClickPaste)
  const hostResizeObservers = useRef<Map<string, ResizeObserver>>(new Map())
  const hostResizeRafs = useRef<Map<string, number>>(new Map())

  const bridge = useMemo(getBridge, [])

  useEffect(() => {
    autoFitRef.current = autoFit
  }, [autoFit])

  useEffect(() => {
    copyOnSelectRef.current = copyOnSelect
  }, [copyOnSelect])

  useEffect(() => {
    rightClickPasteRef.current = rightClickPaste
  }, [rightClickPaste])

  const postMessage = (payload: Record<string, unknown>) => {
    bridge?.postMessage(payload)
  }

  const isWorkspaceV2 = workspace.version === 2

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

  const quotePowerShell = (value: string) => '"' + value.replace(/"/g, '`"') + '"'
  const quoteCmd = (value: string) => `"${value.replace(/"/g, '""')}"`
  const quoteBash = (value: string) => `"${value.replace(/"/g, '\\"')}"`

  const buildLegacyTaskCommand = (task: TaskEntry) => {
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

  const getEnvValue = (name: string) => {
    if (!name) {
      return undefined
    }
    return (
      environment[name] ??
      environment[name.toUpperCase()] ??
      environment[name.toLowerCase()]
    )
  }

  const expandVariables = (
    value: string,
    context: {
      project: ProjectDefinition
      globalsVars: Record<string, string>
      projectVars: Record<string, string>
    }
  ) => {
    if (!value) {
      return value
    }
    let next = value
    for (let i = 0; i < 5; i += 1) {
      const replaced = next.replace(/\$\{([^}]+)\}/g, (match, token) => {
        const raw = token.trim()
        if (!raw) {
          return match
        }
        if (raw.startsWith('env:')) {
          const name = raw.slice(4)
          const envValue = getEnvValue(name)
          return envValue ?? match
        }
        if (raw.startsWith('project.')) {
          const key = raw.slice('project.'.length)
          if (key === 'root') {
            return context.project.root ?? match
          }
          if (key === 'id') {
            return context.project.id
          }
          if (key === 'name') {
            return context.project.name
          }
          return match
        }
        if (raw.startsWith('globals.vars.')) {
          const name = raw.slice('globals.vars.'.length)
          return context.globalsVars[name] ?? match
        }
        if (raw.startsWith('vars.')) {
          const name = raw.slice('vars.'.length)
          return (
            context.projectVars[name] ??
            context.globalsVars[name] ??
            match
          )
        }
        return match
      })
      if (replaced === next) {
        break
      }
      next = replaced
    }
    return next
  }

  const mergeWorkspaceTask = (base: WorkspaceTask | undefined, override: WorkspaceTask) => {
    const merged: WorkspaceTask = { ...(base ?? {}), ...(override ?? {}) }
    if (override.steps === undefined && base?.steps !== undefined) {
      merged.steps = base.steps
    }
    if (override.dependsOn === undefined && base?.dependsOn !== undefined) {
      merged.dependsOn = base.dependsOn
    }
    if (override.group === undefined && base?.group !== undefined) {
      merged.group = base.group
    }
    if (override.shell === undefined && base?.shell !== undefined) {
      merged.shell = base.shell
    }
    if (override.cwd === undefined && base?.cwd !== undefined) {
      merged.cwd = base.cwd
    }
    if (override.runInNewTab === undefined && base?.runInNewTab !== undefined) {
      merged.runInNewTab = base.runInNewTab
    }
    if (override.focusTab === undefined && base?.focusTab !== undefined) {
      merged.focusTab = base.focusTab
    }
    return merged
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

  const sendLegacyTaskToSession = (sessionId: string, task: TaskEntry) => {
    const command = buildLegacyTaskCommand(task)
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

  const buildTaskKey = (projectId: string, taskName: string) => `${projectId}:${taskName}`

  const resolveWorkspaceTask = (project: ProjectDefinition, taskName: string) => {
    const rawTask = project.tasks?.[taskName]
    if (!rawTask) {
      return null
    }
    const template = rawTask.useTemplate
      ? workspace.templates?.[rawTask.useTemplate]
      : undefined
    const merged = mergeWorkspaceTask(template, rawTask)
    const globalsVars = workspace.globals?.vars ?? {}
    const projectVars = project.vars ?? {}
    const context = { project, globalsVars, projectVars }
    const cwd = merged.cwd ? expandVariables(merged.cwd, context) : undefined
    const steps = (merged.steps ?? []).map((step) => ({
      run: expandVariables(step.run, context),
    }))
    const defaultShell = workspace.globals?.defaultShell ?? selectedProfileId
    return {
      key: buildTaskKey(project.id, taskName),
      name: taskName,
      projectId: project.id,
      group: merged.group ?? 'Other',
      shell: merged.shell ?? defaultShell,
      cwd,
      steps,
      dependsOn: merged.dependsOn ?? [],
      runInNewTab: merged.runInNewTab,
      focusTab: merged.focusTab,
    } as ResolvedTask
  }

  const resolveProjectTasks = (project: ProjectDefinition) => {
    if (!project.tasks) {
      return []
    }
    return Object.keys(project.tasks)
      .map((taskName) => resolveWorkspaceTask(project, taskName))
      .filter((task): task is ResolvedTask => Boolean(task))
  }

  const groupTasksByGroup = (tasks: ResolvedTask[]) => {
    const grouped = new Map<string, ResolvedTask[]>()
    tasks.forEach((task) => {
      const group = task.group || 'Other'
      const existing = grouped.get(group)
      if (existing) {
        existing.push(task)
      } else {
        grouped.set(group, [task])
      }
    })
    const preferredOrder = ['Dev', 'Build', 'Test', 'Docker', 'Utils', 'Other']
    const sortedGroups = Array.from(grouped.keys()).sort((left, right) => {
      const leftIndex = preferredOrder.indexOf(left)
      const rightIndex = preferredOrder.indexOf(right)
      if (leftIndex === -1 && rightIndex === -1) {
        return left.localeCompare(right)
      }
      if (leftIndex === -1) {
        return 1
      }
      if (rightIndex === -1) {
        return -1
      }
      return leftIndex - rightIndex
    })
    return sortedGroups.map((group) => ({ group, tasks: grouped.get(group) ?? [] }))
  }

  const resolvedTaskIndex = useMemo(() => {
    const byKey = new Map<string, ResolvedTask>()
    const byProject = new Map<string, ResolvedTask[]>()
    if (!isWorkspaceV2) {
      return { byKey, byProject }
    }
    projects.forEach((project) => {
      const resolved = resolveProjectTasks(project)
      byProject.set(project.id, resolved)
      resolved.forEach((task) => {
        byKey.set(task.key, task)
      })
    })
    return { byKey, byProject }
  }, [isWorkspaceV2, projects, workspace, environment, selectedProfileId])

  const buildTaskExecutionPlan = (task: ResolvedTask) => {
    const projectTasks = resolvedTaskIndex.byProject.get(task.projectId) ?? []
    const byName = new Map(projectTasks.map((entry) => [entry.name, entry]))
    const ordered: TaskExecutionStep[] = []
    const visiting = new Set<string>()
    const visited = new Set<string>()

    const visit = (current: ResolvedTask) => {
      if (visited.has(current.name)) {
        return
      }
      if (visiting.has(current.name)) {
        return
      }
      visiting.add(current.name)
      current.dependsOn.forEach((dep) => {
        const next = byName.get(dep)
        if (next) {
          visit(next)
        }
      })
      current.steps.forEach((step) => {
        ordered.push({ run: step.run, cwd: current.cwd, taskName: current.name })
      })
      visiting.delete(current.name)
      visited.add(current.name)
    }

    visit(task)
    return ordered
  }

  const resolveBootstrapSteps = (project: ProjectDefinition) => {
    const bootstrap = project.bootstrap
    if (!bootstrap?.steps?.length) {
      return []
    }
    const globalsVars = workspace.globals?.vars ?? {}
    const projectVars = project.vars ?? {}
    const context = { project, globalsVars, projectVars }
    const cwd = bootstrap.cwd ? expandVariables(bootstrap.cwd, context) : undefined
    return bootstrap.steps.map((step) => ({
      run: expandVariables(step.run, context),
      cwd,
      taskName: 'bootstrap',
    }))
  }

  const queueTaskSteps = (
    sessionId: string,
    profileId: string,
    steps: TaskExecutionStep[],
    options?: { delayMs?: number }
  ) => {
    let delay = options?.delayMs ?? 0
    let lastCwd: string | undefined
    steps.forEach((step) => {
      const commands: string[] = []
      if (step.cwd && step.cwd !== lastCwd) {
        commands.push(buildChangeDirectoryCommand(profileId, step.cwd))
        lastCwd = step.cwd
      }
      commands.push(step.run)
      const payload = `${commands.join('\r\n')}\r\n`
      setTimeout(() => {
        postMessage({ type: 'input', sessionId, data: payload })
      }, delay)
      delay += 150
    })
    return delay
  }

  const runWorkspaceTaskInSession = (
    task: ResolvedTask,
    sessionId: string,
    paneId: string
  ) => {
    const pane = findPaneById(paneId)
    const profileId = pane?.profileId ?? task.shell ?? selectedProfileId
    const project = projects.find((item) => item.id === task.projectId)
    let delay = 0
    if (project) {
      const bootstrapSteps = resolveBootstrapSteps(project)
      if (bootstrapSteps.length > 0) {
        const existing = bootstrappedSessions.current.get(sessionId)
        if (!existing?.has(project.id)) {
          delay = queueTaskSteps(sessionId, profileId, bootstrapSteps, { delayMs: delay })
          if (existing) {
            existing.add(project.id)
          } else {
            bootstrappedSessions.current.set(sessionId, new Set([project.id]))
          }
        }
      }
    }

    const plan = buildTaskExecutionPlan(task)
    if (plan.length === 0) {
      return
    }

    termRefs.current
      .get(paneId)
      ?.writeln(`\r\n[task] ${task.name} (${task.group})`)

    queueTaskSteps(sessionId, profileId, plan, { delayMs: delay })
  }

  const runWorkspaceTask = (
    task: ResolvedTask,
    options?: { forceNewTab?: boolean; title?: string }
  ) => {
    const activePane = getActivePane()
    const targetProfileId = task.shell ?? selectedProfileId
    const resolvedProfileId = profiles.some((profile) => profile.id === targetProfileId)
      ? targetProfileId
      : selectedProfileId
    const shellMismatch =
      Boolean(activePane?.profileId) && task.shell
        ? task.shell.toLowerCase() !== activePane?.profileId.toLowerCase()
        : false
    const shouldNewTab =
      options?.forceNewTab ?? task.runInNewTab ?? shellMismatch ?? false

    if (!activePane?.sessionId || shouldNewTab) {
      const { paneId } = createTabWithPane(resolvedProfileId, true, {
        title: options?.title ?? task.name,
        pane: { cwd: task.cwd },
      }, { focus: task.focusTab !== false })
      pendingTasks.current.set(paneId, { kind: 'workspace', taskKey: task.key })
      return
    }

    runWorkspaceTaskInSession(task, activePane.sessionId, activePane.id)
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

  const refitActivePanes = () => {
    const activeTab = getActiveTab()
    if (!activeTab) {
      return
    }
    activeTab.groups.forEach((group) => {
      if (group.activeTabId) {
        setTimeout(() => sendResize(group.activeTabId), 0)
      }
    })
  }

  const getLayoutMetrics = () => {
    const width =
      shellLayoutRef.current?.clientWidth ??
      document.documentElement.clientWidth ??
      window.innerWidth
    const isWide = width >= 1700
    const isMedium = width >= 1450
    return {
      width,
      gapTotal: 10 * 4,
      resizerTotal: 6 * 2,
      leftMin: isWide ? 260 : isMedium ? 220 : 180,
      rightMin: isWide ? 320 : isMedium ? 280 : 240,
      leftMax: isWide ? 520 : 420,
      rightMax: isWide ? 560 : 420,
      centerMin: isWide ? 360 : 300,
    }
  }

  const clampSidebarWidths = (nextLeft: number, nextRight: number) => {
    const { width, gapTotal, resizerTotal, leftMin, centerMin, rightMin, leftMax, rightMax } =
      getLayoutMetrics()
    const available = Math.max(0, width - gapTotal - resizerTotal)
    let left = Math.min(leftMax, Math.max(leftMin, nextLeft))
    let right = Math.min(rightMax, Math.max(rightMin, nextRight))
    let overflow = left + right + centerMin - available

    if (overflow > 0) {
      const rightSlack = Math.max(0, right - rightMin)
      const reduceRight = Math.min(rightSlack, overflow)
      right -= reduceRight
      overflow -= reduceRight
    }

    if (overflow > 0) {
      const leftSlack = Math.max(0, left - leftMin)
      const reduceLeft = Math.min(leftSlack, overflow)
      left -= reduceLeft
      overflow -= reduceLeft
    }

    // If the window is very narrow, allow sidebars to shrink below preferred mins
    // to prevent any clipping/off-screen layout.
    if (overflow > 0) {
      const hardRightMin = 170
      const rightHardSlack = Math.max(0, right - hardRightMin)
      const reduceRight = Math.min(rightHardSlack, overflow)
      right -= reduceRight
      overflow -= reduceRight
    }

    if (overflow > 0) {
      const hardLeftMin = 140
      const leftHardSlack = Math.max(0, left - hardLeftMin)
      const reduceLeft = Math.min(leftHardSlack, overflow)
      left -= reduceLeft
      overflow -= reduceLeft
    }

    return { left, right }
  }

  const leftResize = (event: ReactMouseEvent) => {
    event.preventDefault()
    const startX = event.clientX
    const startWidth = leftWidth

    const handleMove = (moveEvent: MouseEvent) => {
      const { width, gapTotal, resizerTotal, leftMin, centerMin, rightMin, leftMax } =
        getLayoutMetrics()
      const maxLeft = Math.max(
        leftMin,
        width - centerMin - Math.max(rightMin, rightWidth) - gapTotal - resizerTotal
      )
      const nextWidth = Math.min(
        Math.min(leftMax, maxLeft),
        Math.max(leftMin, startWidth + (moveEvent.clientX - startX))
      )
      setLeftWidth(nextWidth)
    }

    const handleUp = () => {
      window.removeEventListener('mousemove', handleMove)
      window.removeEventListener('mouseup', handleUp)
      refitActivePanes()
    }

    window.addEventListener('mousemove', handleMove)
    window.addEventListener('mouseup', handleUp)
  }

  const rightResize = (event: ReactMouseEvent) => {
    event.preventDefault()
    const startX = event.clientX
    const startWidth = rightWidth

    const handleMove = (moveEvent: MouseEvent) => {
      const { width, gapTotal, resizerTotal, leftMin, centerMin, rightMin, rightMax } =
        getLayoutMetrics()
      const maxRight = Math.max(
        rightMin,
        width - centerMin - Math.max(leftMin, leftWidth) - gapTotal - resizerTotal
      )
      const nextWidth = Math.min(
        Math.min(rightMax, maxRight),
        Math.max(rightMin, startWidth - (moveEvent.clientX - startX))
      )
      setRightWidth(nextWidth)
    }

    const handleUp = () => {
      window.removeEventListener('mousemove', handleMove)
      window.removeEventListener('mouseup', handleUp)
      refitActivePanes()
    }

    window.addEventListener('mousemove', handleMove)
    window.addEventListener('mouseup', handleUp)
  }

  useEffect(() => {
    const syncToLayout = () => {
      const { left, right } = clampSidebarWidths(leftWidth, rightWidth)
      if (left !== leftWidth) {
        setLeftWidth(left)
      }
      if (right !== rightWidth) {
        setRightWidth(right)
      }
    }

    syncToLayout()
    window.addEventListener('resize', syncToLayout)
    return () => window.removeEventListener('resize', syncToLayout)
  }, [leftWidth, rightWidth])

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
      pendingTasks.current.set(pane.id, { kind: 'legacy', taskId: pane.taskId })
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

  const createWorkspace = (
    groups: GroupInfo[],
    overrides?: Partial<TabInfo>,
    options?: { focus?: boolean }
  ) => {
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
    if (options?.focus !== false) {
      setActiveTabId(newTab.id)
    }
    return newTab.id
  }

  const createTabWithPane = (
    profileId: string,
    autoStart: boolean,
    overrides?: Partial<TabInfo> & { group?: Partial<GroupInfo>; pane?: Partial<SessionInfo> },
    options?: { focus?: boolean }
  ) => {
    const pane = createSession(profileId, autoStart, overrides?.pane)
    const group = createGroup([pane], overrides?.group)
    const tabId = createWorkspace([group], overrides, options)
    return { tabId, paneId: pane.id }
  }

  const createTab = (
    profileId: string,
    autoStart: boolean,
    overrides?: Partial<TabInfo> & { group?: Partial<GroupInfo>; pane?: Partial<SessionInfo> }
  ) => createTabWithPane(profileId, autoStart, overrides).tabId

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
        bootstrappedSessions.current.delete(pane.sessionId)
      }

      paneToSession.current.delete(pane.id)
      termRefs.current.get(pane.id)?.dispose()
      termRefs.current.delete(pane.id)
      fitRefs.current.delete(pane.id)
      searchRefs.current.delete(pane.id)
      hostRefs.current.delete(pane.id)
      hostResizeObservers.current.get(pane.id)?.disconnect()
      hostResizeObservers.current.delete(pane.id)
      const pendingResize = hostResizeRafs.current.get(pane.id)
      if (pendingResize != null) {
        cancelAnimationFrame(pendingResize)
      }
      hostResizeRafs.current.delete(pane.id)
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
          bootstrappedSessions.current.delete(pane.sessionId)
        }
        paneToSession.current.delete(pane.id)
        termRefs.current.get(pane.id)?.dispose()
        termRefs.current.delete(pane.id)
        fitRefs.current.delete(pane.id)
        searchRefs.current.delete(pane.id)
        hostRefs.current.delete(pane.id)
        hostResizeObservers.current.get(pane.id)?.disconnect()
        hostResizeObservers.current.delete(pane.id)
        const pendingResize = hostResizeRafs.current.get(pane.id)
        if (pendingResize != null) {
          cancelAnimationFrame(pendingResize)
        }
        hostResizeRafs.current.delete(pane.id)
        pendingTasks.current.delete(pane.id)
        folderNav.current.delete(pane.id)
      })
    })
    bootstrappedSessions.current.clear()
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
      bootstrappedSessions.current.delete(pane.sessionId)
    }

    paneToSession.current.delete(pane.id)
    termRefs.current.get(pane.id)?.dispose()
    termRefs.current.delete(pane.id)
    fitRefs.current.delete(pane.id)
    searchRefs.current.delete(pane.id)
    hostRefs.current.delete(pane.id)
    hostResizeObservers.current.get(pane.id)?.disconnect()
    hostResizeObservers.current.delete(pane.id)
    const pendingResize = hostResizeRafs.current.get(pane.id)
    if (pendingResize != null) {
      cancelAnimationFrame(pendingResize)
    }
    hostResizeRafs.current.delete(pane.id)
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

  const clearPane = (pane: SessionInfo) => {
    const kind = resolveShellKind(pane.profileId)
    const command = kind === 'cmd' || kind === 'powershell' ? 'cls' : 'clear'
    handlePaneInput(pane.id, `${command}\r`)
  }

  const killPaneSession = (pane: SessionInfo) => {
    if (!pane.sessionId) {
      return
    }
    postMessage({ type: 'kill', sessionId: pane.sessionId })
  }

  const openContextMenu = (paneId: string, event: MouseEvent) => {
    if (!rightClickPasteRef.current) {
      return
    }
    event.preventDefault()
    event.stopPropagation()
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

  const findLegacyTask = (taskId: string) =>
    legacyTasks.find((task) => task.id === taskId || task.name === taskId) ?? null

  const findResolvedTask = (taskKey: string) => resolvedTaskIndex.byKey.get(taskKey) ?? null

  const initializeFromState = (state: AppState) => {
    setRestoreSessions(state.restoreSessions ?? true)
    setTheme(state.theme ?? 'midnight')
    setFontFamily(state.fontFamily ?? '"JetBrains Mono", "Cascadia Mono", monospace')
    setFontSize(state.fontSize ?? 14)
    setAutoFit(state.autoFit ?? true)
    setCopyOnSelect(state.copyOnSelect ?? false)
    setRightClickPaste(state.rightClickPaste ?? true)
    setFavoriteFolders(state.favoriteFolders ?? [])
    if (state.leftWidth != null) {
      setLeftWidth(state.leftWidth)
    }
    if (state.rightWidth != null) {
      setRightWidth(state.rightWidth)
    }

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
    leftWidth,
    rightWidth,
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
          const incomingWorkspace = message.workspace
          const incomingState = message.statePayload
          const incomingEnvironment = message.environment ?? {}
          setProfiles(normalizeProfileList(incomingProfiles))
          setEnvironment(incomingEnvironment)
          if (incomingWorkspace) {
            setWorkspace(incomingWorkspace)
            setProjects(incomingWorkspace.projects ?? [])
            setLegacyTasks([])
            const defaultShell = incomingWorkspace.globals?.defaultShell
            if (defaultShell && incomingProfiles.some((profile) => profile.id === defaultShell)) {
              setSelectedProfileId(defaultShell)
            }
            const workspaceFontSize = incomingWorkspace.globals?.terminal?.fontSize
            if (workspaceFontSize && !incomingState?.fontSize) {
              setFontSize(workspaceFontSize)
            }
          } else {
            setWorkspace({ version: 1, projects: message.projects ?? [] })
            setProjects(message.projects ?? [])
            setLegacyTasks(message.tasks ?? [])
          }
          setScriptsPath(message.scriptsPath ?? null)
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
          if (message.workspace) {
            setWorkspace(message.workspace)
            setProjects(message.workspace.projects ?? [])
            setLegacyTasks([])
            if (message.workspace.globals?.defaultShell) {
              setSelectedProfileId(message.workspace.globals.defaultShell)
            }
          } else {
            setLegacyTasks(message.tasks ?? [])
          }
          break
        }
        case 'projects.list': {
          if (message.workspace) {
            setWorkspace(message.workspace)
            setProjects(message.workspace.projects ?? [])
          } else {
            setProjects(message.projects ?? [])
          }
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

          const pending = pendingTasks.current.get(paneId)
          if (pending) {
            if (pending.kind === 'legacy') {
              const paneAutoRun = pane?.autoRun !== false
              const task = findLegacyTask(pending.taskId)
              if (!paneAutoRun || task?.autoRun === false) {
                pendingTasks.current.delete(paneId)
              } else if (task) {
                sendLegacyTaskToSession(message.sessionId, task)
                pendingTasks.current.delete(paneId)
              } else {
                schedulePendingTask(paneId, pending.taskId)
              }
            } else {
              const task = findResolvedTask(pending.taskKey)
              if (task) {
                runWorkspaceTaskInSession(task, message.sessionId, paneId)
              }
              pendingTasks.current.delete(paneId)
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
    if (isWorkspaceV2) {
      return
    }
    if (typeof window === 'undefined') {
      return
    }
    try {
      window.localStorage.setItem('devshell.pinnedProjects', JSON.stringify(pinnedProjectIds))
    } catch {
      // Ignore storage errors (private mode, blocked, etc.)
    }
  }, [pinnedProjectIds, isWorkspaceV2])

  useEffect(() => {
    if (isWorkspaceV2) {
      return
    }
    if (pinnedProjectIds.length === 0) {
      return
    }
    const available = new Set(projects.map((project) => project.id))
    setPinnedProjectIds((current) => current.filter((id) => available.has(id)))
  }, [projects, pinnedProjectIds.length, isWorkspaceV2])

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
    termRefs.current.forEach((terminal) => {
      terminal.options.disableStdin = folderPickerOpen
      if (terminal.textarea) {
        terminal.textarea.readOnly = folderPickerOpen
      }
    })

    if (!folderPickerOpen) {
      if (folderPickerWasOpen.current) {
        const pane =
          (folderPickerPaneId ? findPaneById(folderPickerPaneId) : null) ?? getActivePane()
        const sessionId =
          pane?.sessionId ?? (pane ? paneToSession.current.get(pane.id) : null)
        if (sessionId) {
          postMessage({ type: 'input', sessionId, data: String.fromCharCode(3) })
        }
      }
      folderPickerWasOpen.current = false
      return
    }

    folderPickerWasOpen.current = true
    setFolderPickerTab('browse')

    const handleClick = (event: MouseEvent) => {
      const target = event.target as Node
      if (folderPickerRef.current && !folderPickerRef.current.contains(target)) {
        setFolderPickerOpen(false)
      }
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault()
        event.stopPropagation()
        event.stopImmediatePropagation()
        setFolderPickerOpen(false)
      }
    }

    window.addEventListener('click', handleClick)
    window.addEventListener('keydown', handleKeyDown, true)
    return () => {
      window.removeEventListener('click', handleClick)
      window.removeEventListener('keydown', handleKeyDown, true)
    }
  }, [folderPickerOpen, folderPickerPaneId])

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

    window.addEventListener('mousedown', handleDismiss, true)
    window.addEventListener('keydown', handleKeyDown)
    return () => {
      window.removeEventListener('mousedown', handleDismiss, true)
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
    if (isWorkspaceV2 && projectEditorTab !== 'basics') {
      setProjectEditorTab('basics')
    }
  }, [isWorkspaceV2, projectEditorTab])

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
          scrollback: terminalScrollback,
          theme: {
            background:
              theme === 'midnight'
                ? '#0e1116'
                : theme === 'graphite'
                  ? '#0d1014'
                  : '#f7f7f8',
            foreground:
              theme === 'midnight'
                ? '#d9e2f1'
                : theme === 'graphite'
                  ? '#e5e8f0'
                  : '#1f2430',
            cursor: theme === 'daylight' ? '#0068d6' : '#8ad1ff',
            selectionBackground:
              theme === 'midnight'
                ? '#2c3a54'
                : theme === 'graphite'
                  ? '#2c2f3f'
                  : '#cfe3ff',
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
        const updateScrollState = () => {
          const baseY = term.buffer?.active?.baseY ?? 0
          term.element?.classList.toggle('no-scrollback', baseY === 0)
        }
        term.onScroll(updateScrollState)
        term.onWriteParsed(updateScrollState)
        term.onResize(updateScrollState)
        updateScrollState()

        term.onData((data) => handlePaneInput(pane.id, data))
        term.onSelectionChange(() => {
          if (!copyOnSelectRef.current) {
            return
          }

          const selection = term.getSelection()
          if (selection) {
            navigator.clipboard?.writeText(selection).catch(() => undefined)
          }
        })

        host.addEventListener('mousedown', (event) => {
          if (event.button !== 2) {
            return
          }
          openContextMenu(pane.id, event)
        })
        host.addEventListener('contextmenu', (event) => {
          openContextMenu(pane.id, event)
        })
        if (!hostResizeObservers.current.has(pane.id) && typeof ResizeObserver !== 'undefined') {
          const observer = new ResizeObserver(() => {
            if (!autoFitRef.current) {
              return
            }
            const pending = hostResizeRafs.current.get(pane.id)
            if (pending != null) {
              cancelAnimationFrame(pending)
            }
            const raf = requestAnimationFrame(() => {
              hostResizeRafs.current.delete(pane.id)
              sendResize(pane.id)
            })
            hostResizeRafs.current.set(pane.id, raf)
          })
          observer.observe(host)
          hostResizeObservers.current.set(pane.id, observer)
        }

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
    pendingTasks.current.forEach((pending, paneId) => {
      if (pending.kind === 'legacy') {
        schedulePendingTask(paneId, pending.taskId)
      }
    })
  }, [legacyTasks])

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

  const workspacePaletteCommands: PaletteCommand[] = isWorkspaceV2
    ? (workspace.workspaces ?? []).map((entry) => ({
        id: `workspace-${entry.id}`,
        label: `Workspace: ${entry.name}`,
        action: () => launchWorkspace(entry),
        keywords: `workspace ${entry.projectId}`,
      }))
    : []

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
      label: 'Cycle Theme',
      action: () =>
        setTheme((current) =>
          current === 'midnight' ? 'graphite' : current === 'graphite' ? 'daylight' : 'midnight'
        ),
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
    ...workspacePaletteCommands,
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
    const task = findLegacyTask(taskId)
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
    if (!sendLegacyTaskToSession(sessionId, task)) {
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

  const handleLegacyTaskSelect = (task: TaskEntry) => {
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
        handleLegacyTaskRunInNewTab(task)
        return
      }

      targetPanes.forEach((pane) => {
        sendLegacyTaskToSession(pane.sessionId as string, task)
      })
      return
    }

    const activePane = getActivePane()
    if (!activePane?.sessionId) {
      handleLegacyTaskRunInNewTab(task)
      return
    }

    sendLegacyTaskToSession(activePane.sessionId, task)
  }

  const handleLegacyTaskRunInNewTab = (task: TaskEntry) => {
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

  const handleWorkspaceTaskSelect = (task: ResolvedTask) => {
    setTaskMenuOpen(false)
    if (task.steps.length === 0) {
      window.alert('Task is missing steps.')
      return
    }

    if (runAllSessions) {
      const targetPanes = tabs
        .flatMap((tab) => tab.groups)
        .flatMap((group) => group.tabs)
        .filter((pane) => pane.sessionId)
        .filter(
          (pane) =>
            !task.shell ||
            task.shell.toLowerCase() === pane.profileId.toLowerCase()
        )

      if (targetPanes.length === 0) {
        handleWorkspaceTaskRunInNewTab(task)
        return
      }

      targetPanes.forEach((pane) => {
        runWorkspaceTaskInSession(task, pane.sessionId as string, pane.id)
      })
      return
    }

    const activePane = getActivePane()
    if (!activePane?.sessionId) {
      handleWorkspaceTaskRunInNewTab(task)
      return
    }

    if (
      task.shell &&
      task.shell.toLowerCase() !== activePane.profileId.toLowerCase()
    ) {
      handleWorkspaceTaskRunInNewTab(task)
      return
    }

    runWorkspaceTaskInSession(task, activePane.sessionId, activePane.id)
  }

  const handleWorkspaceTaskRunInNewTab = (task: ResolvedTask) => {
    setTaskMenuOpen(false)
    if (task.steps.length === 0) {
      window.alert('Task is missing steps.')
      return
    }
    runWorkspaceTask(task, { forceNewTab: true })
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
          const task = item.taskId ? findLegacyTask(item.taskId) : null
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
    const signals = legacyTasks
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

  const getLegacyTaskSubtitle = (task: TaskEntry) => {
    const command = task.command ?? task.path ?? 'command'
    const cwd = task.cwd ?? task.workingDirectory
    return cwd ? `${command} - ${cwd}` : command
  }

  const getWorkspaceTaskSubtitle = (task: ResolvedTask) => {
    const command = task.steps[0]?.run ?? 'command'
    const cwd = task.cwd
    return cwd ? `${command} - ${cwd}` : command
  }

  const scheduleProjectTasks = (groups: GroupInfo[]) => {
    const panes = groups
      .flatMap((group) => group.tabs)
      .filter((pane) => pane.taskId && pane.autoRun !== false)
      .filter((pane) => {
        const task = findLegacyTask(pane.taskId as string)
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
      pendingTasks.current.set(pane.id, { kind: 'legacy', taskId })
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
    if (isWorkspaceV2) {
      const profileId = workspace.globals?.defaultShell ?? selectedProfileId
      createTab(profileId, true, { title: project.name, pane: { cwd: root } })
      return
    }
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

  function launchWorkspace(entry: WorkspaceLaunch) {
    resetWorkspace()
    setProjectMenuProjectId(null)
    const project = projects.find((item) => item.id === entry.projectId) ?? null
    if (project) {
      setActiveProjectId(project.id)
      setTaskProjectId(project.id)
      setRecentProjectIds((current) => {
        const next = [project.id, ...current.filter((item) => item !== project.id)]
        return next.slice(0, 6)
      })
    }
    entry.openTabs.forEach((tab) => {
      if (!project) {
        return
      }
      const task = findResolvedTask(buildTaskKey(project.id, tab.task))
      if (!task) {
        return
      }
      runWorkspaceTask(task, { forceNewTab: true, title: tab.title ?? task.name })
    })
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
    if (isWorkspaceV2) {
      setProjects((current) =>
        current.map((project) =>
          project.id === projectId ? { ...project, pinned: !project.pinned } : project
        )
      )
      return
    }
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

  const getQuickStartProfile = (kind: 'powershell' | 'cmd') => {
    if (kind === 'powershell') {
      return (
        getProfileById('powershell') ??
        profiles.find((profile) => {
          const name = profile.name.toLowerCase()
          const command = profile.command.toLowerCase()
          return name.includes('powershell') || command.includes('powershell')
        }) ??
        null
      )
    }

    return (
      getProfileById('cmd') ??
      profiles.find((profile) => {
        const name = profile.name.toLowerCase()
        const command = profile.command.toLowerCase()
        return name === 'cmd' || command.includes('cmd.exe')
      }) ??
      null
    )
  }

  const startQuickShell = (kind: 'powershell' | 'cmd') => {
    const profile = getQuickStartProfile(kind)
    if (!profile || profile.isAvailable === false) {
      return
    }

    setSelectedProfileId(profile.id)
    createTab(profile.id, true)
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
    const newProject: ProjectDefinition = isWorkspaceV2
      ? {
          id: `project-${crypto.randomUUID()}`,
          name: 'New project',
          root: '',
          pinned: false,
          tasks: {},
          quickTasks: [],
        }
      : {
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
    setLegacyTasks((current) =>
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
    const payloadObject = isWorkspaceV2
      ? {
          ...workspace,
          version: workspace.version ?? 2,
          projects,
        }
      : { projects, tasks: legacyTasks }
    const payload = `${JSON.stringify(payloadObject, null, 2)}\n`
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

  const terminalScrollback = workspace.globals?.terminal?.scrollback ?? 8000
  const activePane = getActivePane()
  const contextMenuStyle = contextMenu.open
    ? {
        left: Math.min(contextMenu.x, window.innerWidth - 180),
        top: Math.min(contextMenu.y, window.innerHeight - 110),
      }
    : { left: 0, top: 0 }
  const activeProject = projects.find((project) => project.id === activeProjectId) ?? null
  const taskProject = taskProjectId
    ? projects.find((project) => project.id === taskProjectId) ?? activeProject
    : activeProject
  const taskQueryLower = taskQuery.trim().toLowerCase()
  const legacyAvailableTasks = legacyTasks.filter(
    (task) =>
      task.useTerminal !== false &&
      (!task.profileId || task.profileId === activePane?.profileId)
  )
  const legacyTaskProjectRoot = taskProject?.root
  const legacyProjectTasks = legacyTaskProjectRoot
    ? legacyAvailableTasks.filter((task) => {
        const cwd = task.cwd ?? task.workingDirectory
        return cwd?.toLowerCase().startsWith(legacyTaskProjectRoot.toLowerCase())
      })
    : []
  const legacyGlobalTasks = legacyAvailableTasks.filter((task) => !legacyProjectTasks.includes(task))

  const legacyTaskMatchesQuery = (task: TaskEntry) =>
    taskQueryLower
      ? `${task.name} ${task.command ?? ''} ${task.path ?? ''}`
          .toLowerCase()
          .includes(taskQueryLower)
      : true

  const taskMatchesQuery = (task: ResolvedTask) => {
    if (!taskQueryLower) {
      return true
    }
    const steps = task.steps.map((step) => step.run).join(' ')
    return `${task.name} ${task.group} ${steps}`.toLowerCase().includes(taskQueryLower)
  }

  const taskProjectTasks = isWorkspaceV2
    ? taskProject
      ? resolvedTaskIndex.byProject.get(taskProject.id) ?? []
      : []
    : legacyProjectTasks
  const filteredProjectTasks = isWorkspaceV2
    ? (taskProjectTasks as ResolvedTask[]).filter(taskMatchesQuery)
    : legacyProjectTasks.filter(legacyTaskMatchesQuery)
  const filteredGlobalTasks = isWorkspaceV2
    ? []
    : legacyGlobalTasks.filter(legacyTaskMatchesQuery)
  const groupedProjectTasks = isWorkspaceV2
    ? groupTasksByGroup(filteredProjectTasks as ResolvedTask[])
    : []
  const taskMenuHasItems = isWorkspaceV2
    ? resolvedTaskIndex.byKey.size > 0
    : legacyAvailableTasks.length > 0
  const panelProject = activeProject ?? taskProject ?? null
  const panelWorkspaceTasks = isWorkspaceV2
    ? panelProject
      ? resolvedTaskIndex.byProject.get(panelProject.id) ?? []
      : []
    : []
  const panelLegacyTasks =
    !isWorkspaceV2 && panelProject?.root
      ? legacyAvailableTasks.filter((task) => {
          const cwd = task.cwd ?? task.workingDirectory
          return cwd?.toLowerCase().startsWith(panelProject.root?.toLowerCase() ?? '')
        })
      : []
  const panelTaskCount = isWorkspaceV2
    ? panelWorkspaceTasks.length
    : panelLegacyTasks.length
  const panelGroupedTasks = isWorkspaceV2
    ? groupTasksByGroup(panelWorkspaceTasks)
    : []
  const panelQuickTasks = isWorkspaceV2 && panelProject
    ? (panelProject.quickTasks ?? [])
        .map((taskName) => findResolvedTask(buildTaskKey(panelProject.id, taskName)))
        .filter((task): task is ResolvedTask => Boolean(task))
    : []
  const profileQueryLower = profileQuery.trim().toLowerCase()
  const filteredProfiles = profiles.filter((profile) =>
    profileQueryLower ? profile.name.toLowerCase().includes(profileQueryLower) : true
  )
  const quickPowerShellProfile = getQuickStartProfile('powershell')
  const quickCmdProfile = getQuickStartProfile('cmd')
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
  const projectEditorTabs = isWorkspaceV2
    ? (['basics'] as const)
    : (['basics', 'layout', 'tasks'] as const)
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
  const legacyEditorTaskMatchesQuery = (task: TaskEntry) =>
    projectEditorTaskQueryLower
      ? `${task.name} ${task.command ?? ''} ${task.path ?? ''}`
          .toLowerCase()
          .includes(projectEditorTaskQueryLower)
      : true
  const editorProjectTasks = isWorkspaceV2
    ? []
    : legacyTasks.filter((task) => {
        if (!editorProjectRoot) {
          return legacyEditorTaskMatchesQuery(task)
        }
        const cwd = resolveTaskDirectory(task)
        const inRoot = cwd.toLowerCase().startsWith(editorProjectRoot.toLowerCase())
        return inRoot && legacyEditorTaskMatchesQuery(task)
      })
  const editorOtherTasks =
    editorProjectRoot && !isWorkspaceV2
      ? legacyTasks.filter((task) => {
          const cwd = resolveTaskDirectory(task)
          const inRoot = cwd.toLowerCase().startsWith(editorProjectRoot.toLowerCase())
          return !inRoot && legacyEditorTaskMatchesQuery(task)
        })
      : []
  const pinnedProjects = isWorkspaceV2
    ? projects.filter((project) => project.pinned).filter((project) => projectMatchesQuery(project))
    : pinnedProjectIds
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
  const allProjects = [...pinnedProjects, ...recentProjects, ...otherProjects]
  const visibleProjects =
    projectFilter === 'pinned'
      ? pinnedProjects
      : projectFilter === 'recent'
        ? recentProjects
        : allProjects
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
    const isPinned = isWorkspaceV2 ? project.pinned === true : pinnedProjectIds.includes(project.id)
    const isMenuOpen = projectMenuProjectId === project.id
    const projectWorkspaces = (workspace.workspaces ?? []).filter(
      (entry) => entry.projectId === project.id
    )

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
              {isWorkspaceV2 &&
                projectWorkspaces.map((entry) => (
                  <button
                    key={entry.id}
                    className="project-row-menu-item"
                    onClick={() => launchWorkspace(entry)}
                  >
                    Launch {entry.name}
                  </button>
                ))}
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
      <div
        className="shell-layout"
        ref={shellLayoutRef}
        style={
          {
            '--left-width': `${leftWidth}px`,
            '--right-width': `${rightWidth}px`,
          } as CSSProperties
        }
      >
        <aside className="project-sidebar">
          <div className="project-sidebar-header">
            <div className="project-sidebar-title">Projects</div>
            <div className="project-sidebar-filters">
              <button
                className={`project-filter ${projectFilter === 'pinned' ? 'active' : ''}`}
                onClick={() => setProjectFilter('pinned')}
              >
                Pinned
              </button>
              <button
                className={`project-filter ${projectFilter === 'recent' ? 'active' : ''}`}
                onClick={() => setProjectFilter('recent')}
              >
                Recent
              </button>
              <button
                className={`project-filter ${projectFilter === 'all' ? 'active' : ''}`}
                onClick={() => setProjectFilter('all')}
              >
                All
              </button>
            </div>
          </div>
          <input
            className="project-sidebar-search"
            value={projectQuery}
            onChange={(event) => setProjectQuery(event.target.value)}
            placeholder="Search projects..."
          />
          <div className="project-sidebar-list">
            {visibleProjects.map((project) => renderProjectRow(project))}
            {visibleProjects.length === 0 && (
              <div className="project-sidebar-empty">
                {projectFilter === 'pinned'
                  ? 'No pinned projects'
                  : projectFilter === 'recent'
                    ? 'No recent projects'
                    : 'No projects'}
              </div>
            )}
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
        <div className="sidebar-resizer left" onMouseDown={leftResize} />
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
              <div className="quick-shell-actions">
                <button
                  className="action quick-shell-action"
                  disabled={!quickPowerShellProfile || quickPowerShellProfile.isAvailable === false}
                  onClick={() => startQuickShell('powershell')}
                  title="Start a PowerShell tab"
                >
                  PowerShell
                </button>
                <button
                  className="action quick-shell-action"
                  disabled={!quickCmdProfile || quickCmdProfile.isAvailable === false}
                  onClick={() => startQuickShell('cmd')}
                  title="Start a CMD tab"
                >
                  CMD
                </button>
              </div>
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
              disabled={!taskMenuHasItems}
              onClick={() => {
                if (taskMenuHasItems) {
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
                        {isWorkspaceV2 ? (
                          groupedProjectTasks.map((group) => (
                            <div key={group.group} className="menu-section">
                              <div className="menu-section-title">{group.group}</div>
                              {group.tasks.map((task) => (
                                <div key={task.key} className="menu-row task-row">
                                  <div className="row-main">
                                    <div className="row-title">{task.name}</div>
                                    <div className="row-subtitle">
                                      {getWorkspaceTaskSubtitle(task)}
                                    </div>
                                  </div>
                                  <div className="row-actions">
                                    <button
                                      className="row-action primary"
                                      onClick={() => handleWorkspaceTaskSelect(task)}
                                    >
                                      ▶ Run here
                                    </button>
                                    <button
                                      className="row-action ghost"
                                      onClick={() => handleWorkspaceTaskRunInNewTab(task)}
                                    >
                                      ➕ New tab
                                    </button>
                                  </div>
                                </div>
                              ))}
                            </div>
                          ))
                        ) : (
                          (filteredProjectTasks as TaskEntry[]).map((task) => (
                            <div key={task.id ?? task.name} className="menu-row task-row">
                              <div className="row-main">
                                <div className="row-title">{task.name}</div>
                                <div className="row-subtitle">
                                  {getLegacyTaskSubtitle(task)}
                                </div>
                              </div>
                              <div className="row-actions">
                                <button
                                  className="row-action primary"
                                  onClick={() => handleLegacyTaskSelect(task)}
                                >
                                  ▶ Run here
                                </button>
                                <button
                                  className="row-action ghost"
                                  onClick={() => handleLegacyTaskRunInNewTab(task)}
                                >
                                  ➕ New tab
                                </button>
                              </div>
                            </div>
                          ))
                        )}
                        {filteredProjectTasks.length === 0 && (
                          <div className="menu-empty">No project tasks</div>
                        )}
                      </>
                    )}
                  </div>
                )}
                {!isWorkspaceV2 && (
                  <div className="menu-section">
                    <div className="menu-section-title">Other tasks</div>
                    {(filteredGlobalTasks as TaskEntry[]).map((task) => (
                      <div key={task.id ?? task.name} className="menu-row task-row">
                        <div className="row-main">
                          <div className="row-title">{task.name}</div>
                          <div className="row-subtitle">{getLegacyTaskSubtitle(task)}</div>
                        </div>
                        <div className="row-actions">
                          <button
                            className="row-action primary"
                            onClick={() => handleLegacyTaskSelect(task)}
                          >
                            ▶ Run here
                          </button>
                          <button
                            className="row-action ghost"
                            onClick={() => handleLegacyTaskRunInNewTab(task)}
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
                )}
              </div>
            )}
          </div>
          <div className="theme-switch">
            <button
              className={`action ghost ${theme === 'midnight' ? 'active' : ''}`}
              onClick={() => setTheme('midnight')}
            >
              Dark
            </button>
            <button
              className={`action ghost ${theme === 'daylight' ? 'active' : ''}`}
              onClick={() => setTheme('daylight')}
            >
              Light
            </button>
          </div>
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
          {tabs.map((tab) => {
            const hasSplit = tab.split && tab.groups.length > 1
            const splitClass = hasSplit ? `split-${tab.splitDirection}` : 'split-none'
            return (
            <div
              key={tab.id}
              className={`terminal-host ${activeTabId === tab.id ? 'active' : ''} ${splitClass}`}
              style={
                hasSplit
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
                          <div className="pane-clip">
                            <button
                              className="pane-clip-btn"
                              onClick={(event) => {
                                event.stopPropagation()
                                void copySelectionForPane(headerPane.id)
                              }}
                            >
                              Copy
                            </button>
                            <button
                              className="pane-clip-btn"
                              disabled={!headerPane.sessionId}
                              onClick={(event) => {
                                event.stopPropagation()
                                void pasteClipboardForPane(headerPane.id)
                              }}
                            >
                              Paste
                            </button>
                            <button
                              className="pane-clear-btn"
                              disabled={!headerPane.sessionId}
                              onClick={(event) => {
                                event.stopPropagation()
                                clearPane(headerPane)
                              }}
                            >
                              Clear
                            </button>
                            <button
                              className="pane-split-btn"
                              onClick={(event) => {
                                event.stopPropagation()
                                splitActiveTab()
                              }}
                            >
                              Split
                            </button>
                            <button
                              className="pane-kill-btn"
                              disabled={!headerPane.sessionId}
                              onClick={(event) => {
                                event.stopPropagation()
                                killPaneSession(headerPane)
                              }}
                            >
                              Kill
                            </button>
                          </div>
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
              {hasSplit && (
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
          )})}
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
        <div className="sidebar-resizer right" onMouseDown={rightResize} />
        <aside className="task-sidebar">
          <div className="task-sidebar-header">
            <div className="task-sidebar-title">Tasks</div>
            <div className="task-sidebar-subtitle">
              {panelProject ? `${panelProject.name} • ${panelTaskCount}` : 'Select a project'}
            </div>
          </div>
          {panelProject && panelQuickTasks.length > 0 && (
            <div className="task-sidebar-quick">
              <div className="task-panel-section-title">Quick</div>
              <div className="task-sidebar-quick-list">
                {panelQuickTasks.map((task) => (
                  <button
                    key={task.key}
                    className="task-chip"
                    title={getWorkspaceTaskSubtitle(task)}
                    onClick={() => handleWorkspaceTaskSelect(task)}
                  >
                    {task.name}
                  </button>
                ))}
              </div>
            </div>
          )}
          <div className="task-sidebar-list">
            {!panelProject && (
              <div className="task-sidebar-empty">Select a project to see tasks.</div>
            )}
            {panelProject && panelTaskCount === 0 && (
              <div className="task-sidebar-empty">No tasks for this project.</div>
            )}
            {panelProject &&
              panelTaskCount > 0 &&
              (isWorkspaceV2 ? (
                panelGroupedTasks.map((group) => (
                  <div key={group.group} className="task-panel-section">
                    <div className="task-panel-section-title">{group.group}</div>
                    {group.tasks.map((task) => (
                      <div key={task.key} className="task-panel-row">
                        <div className="row-main">
                          <div className="row-title">{task.name}</div>
                          <div className="row-subtitle">
                            {getWorkspaceTaskSubtitle(task)}
                          </div>
                        </div>
                        <div className="row-actions">
                          <button
                            className="row-action primary"
                            onClick={() => handleWorkspaceTaskSelect(task)}
                          >
                            Run
                          </button>
                          <button
                            className="row-action ghost"
                            onClick={() => handleWorkspaceTaskRunInNewTab(task)}
                          >
                            New tab
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                ))
              ) : (
                panelLegacyTasks.map((task) => (
                  <div key={task.id ?? task.name} className="task-panel-row">
                    <div className="row-main">
                      <div className="row-title">{task.name}</div>
                      <div className="row-subtitle">{getLegacyTaskSubtitle(task)}</div>
                    </div>
                    <div className="row-actions">
                      <button
                        className="row-action primary"
                        onClick={() => handleLegacyTaskSelect(task)}
                      >
                        Run
                      </button>
                      <button
                        className="row-action ghost"
                        onClick={() => handleLegacyTaskRunInNewTab(task)}
                      >
                        New tab
                      </button>
                    </div>
                  </div>
                ))
              ))}
          </div>
        </aside>
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
                  Change directory
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
            <div className="folder-tabs">
              <button
                className={`folder-tab ${folderPickerTab === 'browse' ? 'active' : ''}`}
                onClick={() => setFolderPickerTab('browse')}
              >
                Browse
              </button>
              <button
                className={`folder-tab ${folderPickerTab === 'favorites' ? 'active' : ''}`}
                onClick={() => setFolderPickerTab('favorites')}
              >
                Favorites
              </button>
              <button
                className={`folder-tab ${folderPickerTab === 'recent' ? 'active' : ''}`}
                onClick={() => setFolderPickerTab('recent')}
              >
                Recent
              </button>
              <button
                className={`folder-tab ${folderPickerTab === 'tools' ? 'active' : ''}`}
                onClick={() => setFolderPickerTab('tools')}
              >
                Tools
              </button>
            </div>
            {folderPickerTab === 'browse' && (
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
            )}
            {folderPickerTab === 'browse' && (
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
            )}
            {folderPickerTab === 'favorites' && (
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
            )}
            {folderPickerTab === 'browse' && (
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
            )}
            {folderPickerTab === 'recent' && (
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
            )}
            {folderPickerTab === 'tools' && (
              <div className="folder-section">
                <div className="folder-section-title">Convenience</div>
                <div className="folder-list">
                  <button
                    className="folder-row"
                    disabled={!folderPickerState?.startFolder}
                    onClick={() => {
                      if (folderPickerState?.startFolder) {
                        applyFolderChange(
                          folderPickerPane.id,
                          folderPickerState.startFolder
                        )
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
            )}
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
                {projectEditorTabs.map((tab) => (
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

                {editorProject && !isWorkspaceV2 && projectEditorTab === 'layout' && (
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
                              {legacyTasks.map((task) => (
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

                {editorProject && !isWorkspaceV2 && projectEditorTab === 'tasks' && (
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
