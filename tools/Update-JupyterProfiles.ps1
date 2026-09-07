$workspaceRoot = Join-Path (Split-Path $PSScriptRoot -Parent) 'JupyterWorkspace'
$notebookRoot = Join-Path $workspaceRoot 'notebooks'

$tasks = [ordered]@{
    'Jupyter - Open Guide' = [ordered]@{
        cwd = $workspaceRoot
        steps = @([ordered]@{ run = ('Start-Process "{0}\guide.html"' -f $workspaceRoot) })
    }
    'Jupyter - Environment Check' = [ordered]@{
        cwd = $workspaceRoot
        steps = @([ordered]@{
            run = 'python -c "import jupyterlab, numpy, pandas, matplotlib, sympy; print(jupyterlab.__version__)"'
        })
    }
    'Jupyter - Install Environment' = [ordered]@{
        cwd = $workspaceRoot
        steps = @([ordered]@{ run = 'python -m pip install --upgrade -r requirements.txt' })
    }
    'Jupyter - Start Lab' = [ordered]@{
        cwd = $workspaceRoot
        steps = @([ordered]@{
            run = ('python -m jupyter lab --no-browser --ip=127.0.0.1 --port=8889 --ServerApp.root_dir="{0}" --ServerApp.token="" --ServerApp.password=""' -f $workspaceRoot)
        })
    }
    'Jupyter - Open Lab' = [ordered]@{
        cwd = $workspaceRoot
        steps = @([ordered]@{ run = 'Start-Process "http://localhost:8889/lab"' })
    }
    'Jupyter - Open Start Here' = [ordered]@{
        cwd = $notebookRoot
        steps = @([ordered]@{
            run = 'Start-Process "http://localhost:8889/lab/tree/notebooks/00_start_here.ipynb"'
        })
    }
    'Jupyter - Open Data Exploration' = [ordered]@{
        cwd = $notebookRoot
        steps = @([ordered]@{
            run = 'Start-Process "http://localhost:8889/lab/tree/notebooks/01_data_exploration.ipynb"'
        })
    }
    'Jupyter - Open Math3D Vectors' = [ordered]@{
        cwd = $notebookRoot
        steps = @([ordered]@{
            run = 'Start-Process "http://localhost:8889/lab/tree/notebooks/02_math3d_vectors.ipynb"'
        })
    }
    'Jupyter - Open Symbolic Mathematics' = [ordered]@{
        cwd = $notebookRoot
        steps = @([ordered]@{
            run = 'Start-Process "http://localhost:8889/lab/tree/notebooks/03_symbolic_mathematics.ipynb"'
        })
    }
    'Jupyter - List Servers' = [ordered]@{
        cwd = $workspaceRoot
        steps = @([ordered]@{ run = 'python -m jupyter server list' })
    }
    'Jupyter - Stop Lab' = [ordered]@{
        cwd = $workspaceRoot
        steps = @([ordered]@{ run = 'python -m jupyter server stop 8889' })
    }
    'Jupyter - Open Workspace in VS Code' = [ordered]@{
        cwd = $workspaceRoot
        steps = @([ordered]@{ run = 'Start-Process code -ArgumentList "."' })
    }
}

$jupyterProject = [ordered]@{
    id = 'jupyter-studio'
    name = 'Jupyter Studio'
    root = $workspaceRoot
    pinned = $true
    layout = [ordered]@{
        type = 'tabs'
        items = @(
            [ordered]@{
                title = 'Jupyter Lab Server'
                profileId = 'pwsh'
                cwd = $workspaceRoot
                taskId = 'Jupyter - Start Lab'
                autoRun = $false
            },
            [ordered]@{
                title = 'Notebook Workspace'
                profileId = 'pwsh'
                cwd = $notebookRoot
                taskId = 'Jupyter - Environment Check'
                autoRun = $false
            }
        )
    }
    tasks = $tasks
    quickTasks = @(
        'Jupyter - Open Guide',
        'Jupyter - Environment Check',
        'Jupyter - Install Environment',
        'Jupyter - Start Lab',
        'Jupyter - Open Lab',
        'Jupyter - Open Start Here',
        'Jupyter - Open Data Exploration',
        'Jupyter - Open Math3D Vectors',
        'Jupyter - Open Symbolic Mathematics',
        'Jupyter - List Servers',
        'Jupyter - Stop Lab',
        'Jupyter - Open Workspace in VS Code'
    )
}

$repositoryRoot = Split-Path $PSScriptRoot -Parent
$profilePaths = @(
    (Join-Path $repositoryRoot 'BatchLauncher\profiles\desktop-main.json'),
    (Join-Path $repositoryRoot 'BatchLauncher\profiles\desktop-two.json')
)

foreach ($profilePath in $profilePaths) {
    $config = Get-Content -LiteralPath $profilePath -Raw | ConvertFrom-Json
    $otherProjects = @(
        $config.projects |
            Where-Object { $_.id -notmatch '^jupyter' -and $_.name -notmatch '^Jupyter' }
    )
    $config.projects = @($otherProjects) + @([pscustomobject]$jupyterProject)
    $allowedProjectIds = @($config.projects | ForEach-Object { $_.id })
    $config.workspaces = @(
        $config.workspaces |
            Where-Object { $allowedProjectIds -contains $_.projectId }
    )

    $json = $config | ConvertTo-Json -Depth 100
    [System.IO.File]::WriteAllText($profilePath, $json + [Environment]::NewLine)
}
