# Project manifest example

See the [version 1 guide](../../docs/project-manifests.md) for the schema and migration steps.

Open **Projects → Manage → Import manifest…** and choose `devshell.project.json` in this folder. DevShell previews the project and validation issues before saving it to the active profile. Import does not run tasks, clone repositories, or start services.

The manifest uses `version: 1` and a `project` object. `root` is relative to the manifest folder. Repository paths, task working directories, and service working directories are relative to the project root. Paths must stay inside their parent folder. Task references in `quickTasks`, dependencies, and repository actions must name tasks in this project.

Machine-specific settings, such as the workspace root, tool locations, Python environments, and terminal profiles, stay in the local DevShell profile. After import, edit those settings in DevShell if the project needs them. The example task requires PowerShell 7 only when you explicitly run it.
