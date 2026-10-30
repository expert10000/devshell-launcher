# DevShell project manifests (version 1)

A repository can include `devshell.project.json` at its root. In DevShell, choose **Projects → Manage → Import folder…** and select that repository, or choose **Import manifest…** and select the file. Review the preview, then select **Import project**. Import copies the resolved project into the active profile; it does not execute commands, clone repositories, or start services. The source manifest remains unchanged.

The [JSON Schema](../schemas/devshell.project.v1.schema.json) describes the version 1 fields. The [hello project](../examples/hello-project/devshell.project.json) is a small working example.

## Paths and machine settings

`project.root` is relative to the manifest's folder and defaults to `.`. Repository paths, task `cwd`, service `cwd`, and layout item `cwd` are relative to the project root. Output, PDF, dependency, and Python requirements paths are relative to their repository. DevShell rejects absolute paths, `${...}` variables in these paths, and paths that escape their parent folder. The profile receives the resolved local paths when you import.

Keep machine-specific paths in the profile: workspace root, executable locations, Python environments, and the Jupyter Python executable. Do not put credentials, tokens, or personal paths in a shared manifest. URL user information is rejected; URLs with query strings or fragments produce a warning because they may contain tokens.

The importer checks duplicate project and repository IDs, task references, dependency cycles, supported service kinds, and layout references. Unknown manifest fields are errors. A missing project folder is a warning, so a manifest can describe a repository that still needs cloning.

## Moving a project out of an existing profile

1. Copy one object from `projects` in the profile JSON into a new file shaped as `{ "version": 1, "project": { ... } }` in the repository root.
2. Change its `root` to `.` and change repository `path` and each task/service/layout `cwd` to paths relative to that root. Keep output, PDF, and dependency paths relative to their repository.
3. Remove `pythonEnvironment`, repository `pythonEnvironment`, and `service.python`. Remove local tool paths, credentials, and machine-only variables. Keep portable task names, commands, repository URLs, and service settings.
4. Import the manifest into a different profile and use **Setup / Fix** or profile editing for that machine's environment. Check the preview before confirming.

Version 1 import is a copy. Later edits to the source manifest do not change an imported profile automatically; import again under a new project ID or edit the profile explicitly.
