"""Phase 3 (Days 16-18): Git Internals, History Surgery, Conflicts & Release Tagging."""

from typing import Dict, List
from .common import make_day, qa, scenario, sec, sim

DAYS_16_TO_18: List[Dict] = [
    make_day(
        day=16,
        phase=3,
        title="Git Internals, Commits, Branching & Remotes",
        subtitle="Blobs, Trees, Commits, Staging Index, Branches, fetch vs pull & Bare Remotes",
        goal="Understand Git's content-addressed object store and manage branches/remotes safely",
        objective=(
            "Stop treating Git as magic: understand the three trees (Working Directory, Staging Index, Repository `.git/objects`), "
            "why branches are just 41-byte pointers to commit hashes, and how `fetch` differs safely from `pull`."
        ),
        concepts=[
            "Git stores 4 object types under `.git/objects`: **Blob** (file content), **Tree** (directory listing), **Commit** (snapshot pointer + parent + author + message), and **Annotated Tag**.",
            "Three states: Working Tree (`git diff`) -> Staging Index (`git add`, `git diff --staged`) -> Commit History (`git commit`).",
            "`git fetch` downloads remote commits/refs into `origin/*` WITHOUT touching your working tree; `git pull` = `fetch` + `merge` (or `--rebase`).",
        ],
        deep_sections=[
            sec(
                "1. Git Three Trees & Why Branching Takes Milliseconds",
                "A branch in Git is simply a file inside `.git/refs/heads/<name>` holding a 40-char commit SHA. Creating a branch never copies files — it writes 41 bytes!",
                table={
                    "headers": ["Area", "Inspected With", "What Moves Data Forward"],
                    "rows": [
                        ["Working Directory", "git status / git diff", "Edit files locally"],
                        ["Staging Index", "git diff --staged", "`git add <file>` snapshots blob to index"],
                        ["Local HEAD / Branch", "git log --oneline --graph", "`git commit` writes Tree + Commit object"],
                        ["Remote Tracking (`origin/main`)", "git fetch origin", "`git push` / `git fetch` syncs bare remote"],
                    ],
                },
                example="# Inspect live Git internals in /lab/git-demo:\n$ cat .git/HEAD            # ref: refs/heads/main\n$ git cat-file -t HEAD     # commit\n$ git cat-file -p HEAD     # shows tree hash, parent, author, message",
            ),
        ],
        architecture="Working Tree -> git add -> Staging Index -> git commit -> Branch Ref -> git push -> Bare Remote (/lab/git-remote/demo.git)",
        commands=[
            {"cmd": "git status && git log --oneline --graph --decorate --all", "explain": "Inspect repository branch graph and tracking state in /lab/git-demo", "cwd": "/lab/git-demo"},
            {"cmd": "git remote -v && git branch -a && cat .git/HEAD", "explain": "Inspect remote bare origin URL, branches, and HEAD ref pointer", "cwd": "/lab/git-demo"},
            {"cmd": "git show --stat HEAD && git cat-file -p HEAD", "explain": "Inspect raw Git commit object (tree, parent, author, diff stat)", "cwd": "/lab/git-demo"},
        ],
        production_use_case="Every alert rule, Grafana dashboard, and Terraform file in A³P is Git-versioned so `origin/main` serves as the immutable source of truth.",
        scenarios=[
            scenario(
                "Engineer Committed Directly in `Detached HEAD` State and Lost Work",
                "After checking out a release tag (`git checkout v1.4.0`), an engineer commits 3 hotfixes, switches back to `main`, and complains their commits disappeared.",
                "git reflog -n 10 ; git branch hotfix-recovered <lost-sha>",
                "Checking out a tag or raw SHA puts `HEAD` directly on a commit instead of a branch ref; leaving leaves the commits orphaned (reachable only via reflog for ~90 days).",
                "Create a branch at the orphaned SHA (`git switch -c recovery <sha>`) or run `git switch -c my-branch` BEFORE committing whenever in Detached HEAD.",
            ),
        ],
        troubleshooting=["`git pull` fails with divergent branches -> configure `git pull --rebase` or inspect `git log HEAD..origin/main` via `git fetch` first."],
        interview_qa=[
            qa("What is the difference between `git fetch` and `git pull`?", "`git fetch` updates remote-tracking refs (`origin/*`) read-only so you can review `git diff main origin/main` safely. `git pull` runs `git fetch` followed immediately by `git merge` (or `rebase`), mutating your current branch.", "basic"),
            qa("What is a Detached HEAD and how do you rescue commits made in it?", "Detached HEAD means `.git/HEAD` points directly to a commit SHA rather than `refs/heads/<branch>`. Rescue commits by creating a branch right away (`git switch -c rescued`) or looking up the SHA in `git reflog`.", "senior"),
        ],
        assignment_items=[
            "Inspect .git/HEAD and git cat-file -p HEAD inside /lab/git-demo",
            "Create a feature branch, commit a file change, and push to local bare remote",
            "Explain git fetch vs git pull and why Detached HEAD loses unreferenced commits",
        ],
        revision=["Blob -> Tree -> Commit", "Branch = 41-byte SHA pointer", "fetch = safe preview; pull = fetch+merge"],
        interview_sim=[
            sim("You ran `git checkout v1.4.0`, made 2 hotfix commits, then checked out `main`. How do you recover those 2 commits?", ["git reflog to find the commit SHA", "git switch -c hotfix-v1.4.1 <sha>"]),
            sim("Explain what happens internally in `.git/objects` when you add 1 line to a file and run `git add` + `git commit`.", ["New compressed Blob object created", "Index updated", "New Tree(s) + Commit object referencing parent commit"]),
            sim("Why should SRE pipelines use `git fetch && git diff` or `git checkout` rather than blindly running `git pull` on production config nodes?", ["Prevent unreviewed auto-merge conflicts or dirty working trees in prod"]),
            sim("What is a bare repository (like `/lab/git-remote/demo.git`)?", ["Contains only .git object/ref database without a checked-out working tree; acts as shared central remote"]),
            sim("How does `.gitignore` interact with a file like `.env` that was ALREADY committed earlier?", [".gitignore only ignores untracked files! Must run git rm --cached .env and rotate secret"]),
        ],
    ),

    make_day(
        day=17,
        phase=3,
        title="Merge vs Rebase, Cherry-Pick, Reset vs Revert & Reflog",
        subtitle="Safe Production Rollbacks (revert), History Cleanup (rebase), Stash & Reflog Rescue",
        goal="Rewind mistakes safely on shared branches without breaking teammates' Git history",
        objective=(
            "Know the golden rule of `rebase` (never rebase pushed/shared `main`), choose `git revert` over `reset` for production hotfix rollbacks, "
            "`cherry-pick` critical fixes onto release branches, and recover from `reset --hard` via `git reflog`."
        ),
        concepts=[
            "`git merge` creates a 2-parent merge commit preserving exact parallel history; `git rebase` replays commits onto a new base for a clean linear log (changes commit SHAs!).",
            "`git revert <sha>` creates a brand-new inverse commit (append-only, safe for shared `main`!). `git reset` (`--soft`, `--mixed`, `--hard`) rewrites branch pointers backward (local unpublished work only!).",
            "`git cherry-pick <sha>` copies a single commit from one branch onto another (e.g. backporting a hotfix to `release/v1.4`).",
            "`git reflog` tracks every local `HEAD` transition — saving you even after `git reset --hard`.",
        ],
        deep_sections=[
            sec(
                "1. `git reset` Modes vs `git revert`",
                "Knowing which of the three Git trees each flag touches prevents accidental data loss during stressful incident rollbacks.",
                table={
                    "headers": ["Command", "Moves Branch HEAD?", "Updates Index?", "Overwrites Working Files?", "Safe on Shared `main`?"],
                    "rows": [
                        ["git reset --soft HEAD~1", "Yes", "No (stays staged)", "No", "No (rewrites SHA)"],
                        ["git reset --mixed HEAD~1", "Yes", "Yes (unstaged)", "No", "No (rewrites SHA)"],
                        ["git reset --hard HEAD~1", "Yes", "Yes", "YES (wipes local changes!)", "NO (destructive!)"],
                        ["git revert <sha>", "Advances forward!", "Commits inverse diff", "Updates safely forward", "YES (audit-safe!)"],
                    ],
                },
            ),
        ],
        architecture="Local WIP -> git stash / reset | Prod Rollback -> git revert (forward SHA) | Hotfix Backport -> git cherry-pick",
        commands=[
            {"cmd": "git checkout -b practice/stash-demo && echo '# temp' >> README.md && git stash && git status && git stash pop", "explain": "Practice stashing dirty working tree changes and popping them back", "cwd": "/lab/git-demo"},
            {"cmd": "git reflog -n 8", "explain": "Inspect reflog recovery points for every local HEAD change", "cwd": "/lab/git-demo"},
            {"cmd": "git checkout main && git branch -D practice/stash-demo || true", "explain": "Return cleanly to main and remove temporary branch", "cwd": "/lab/git-demo"},
        ],
        production_use_case="Rolling back bad Terraform/Prometheus/Helm commits on `main` via `git revert` during SEV-1 incidents while preserving full SOC2 audit history.",
        scenarios=[
            scenario(
                "Bad Alert Config Merged to `main` Triggers 5,000 PagerDuty Pages",
                "Commit `8f2c11a` lowered an alert threshold 100x too low on `main`; 12 engineers already pulled `main`.",
                "git log -n 3 --oneline ; git revert --no-edit 8f2c11a ; git push origin main",
                "Running `git reset --hard HEAD~1 && git push --force` would rewrite shared history and fail on protected `main`.",
                "`git revert 8f2c11a` creates a clean forward undo commit, triggers ArgoCD/CI immediately, and keeps full blame/audit trail.",
            ),
        ],
        troubleshooting=["Pushing a rebased private PR branch -> use `git push --force-with-lease` (never bare `--force`, which overwrites teammates' commits)."],
        interview_qa=[
            qa("Merge vs Rebase, and Reset vs Revert?", "`merge` joins branches with a merge commit keeping true history; `rebase` replays commits linearly with new SHAs (never rebase shared branches). `reset` rewinds branch pointers locally; `revert` adds a new inverse commit safely for shared/prod branches.", "basic"),
            qa("You ran `git reset --hard HEAD~3` by mistake on an unpushed branch. How do you get your 3 commits back?", "Run `git reflog` to find the commit SHA right before the `reset`, then run `git reset --hard <old-sha>` (or `git switch -c backup <old-sha>`).", "senior"),
        ],
        assignment_items=[
            "Compare --soft, --mixed, and --hard reset modes",
            "Practice git stash and git stash pop in /lab/git-demo",
            "Inspect git reflog and explain why git revert is mandatory for shared main rollbacks",
        ],
        revision=["Never rebase shared main", "git revert = safe prod rollback", "--force-with-lease > --force", "reflog saves reset --hard mistakes"],
        interview_sim=[
            sim("A critical bug fix was just merged to `main` (`abc1234`), and you must apply ONLY that fix to `release/v2.1` without merging 40 unfinished `main` features. How?", ["git switch release/v2.1 && git cherry-pick abc1234", "Explain -x flag to record source SHA"]),
            sim("Why is `git push --force-with-lease` vastly safer than `git push --force`?", ["Fails safely if remote tracking ref moved unexpectedly since your last fetch"]),
            sim("Explain what `git bisect` does when production latency regressed sometime in the last 128 commits.", ["Binary search across commit history (~7 steps for 128 commits) marking good/bad until exact offending commit found"]),
            sim("Compare `git stash` vs creating a quick `wip/` branch.", ["Stash is temporary local stack (not synced to remote); WIP branch is backed up on remote/reflog"]),
            sim("When you revert a merge commit (`git revert -m 1 <merge_sha>`), why is `-m 1` required and what gotcha happens if you later re-merge that same branch?", ["Specify mainline parent 1; later re-merge requires reverting the revert first"]),
        ],
    ),

    make_day(
        day=18,
        phase=3,
        title="Merge Conflicts, Release Tags, Git Flow & CI Hooks",
        subtitle="Resolving Conflict Markers, Annotated Tags, Squash Merge & GitHub Actions CI",
        goal="Resolve merge conflicts deterministically, tag immutable releases, and wire CI triggers",
        objective=(
            "Read and resolve Git conflict markers without deleting teammates' fixes, understand Lightweight vs Annotated Tags, "
            "compare Merge / Squash Merge / Rebase PR strategies, and connect Git tags to CI/CD Admission Gates."
        ),
        concepts=[
            "Conflict markers: `<<<<<<< HEAD` (our current branch) through `=======` (divider) to `>>>>>>> incoming` (merged branch). Resolve, remove markers, `git add`, `git commit`.",
            "Annotated tags (`git tag -a v1.4.0 -m '...'`) store tagger identity, timestamp, and GPG signature; CI/CD systems trigger production releases ONLY on annotated semantic tags.",
            "Squash Merge condenses noisy PR commits (`wip`, `fix typo`) into 1 clean commit on `main`, though granular feature commits leave `main`.",
        ],
        deep_sections=[
            sec(
                "1. Git Flow vs Trunk-Based Development & PR Merge Strategies",
                "High-velocity SRE teams favor Trunk-Based Development (short-lived feature branches merged daily into `main` + feature flags) over long-lived Git Flow branches that cause painful merge conflicts.",
                table={
                    "headers": ["Strategy", "Result on `main`", "Best Used For"],
                    "rows": [
                        ["Create Merge Commit", "Preserves all PR commits + 2-parent merge node", "Full branch history auditability"],
                        ["Squash and Merge", "1 clean commit per PR on `main`", "Clean readable `main` log & easy 1-commit `git revert`"],
                        ["Rebase and Merge", "Linear history without merge commits", "Small clean PRs without merge bubbles"],
                    ],
                },
            ),
        ],
        architecture="Feature Branch -> PR + GitHub Actions CI (Lint/Test/Trivy) -> Squash Merge -> Annotated Tag (v1.4.0) -> Release Admission",
        commands=[
            {"cmd": "git tag -l && git log --oneline -n 5", "explain": "Inspect semantic release tags and recent commits in /lab/git-demo", "cwd": "/lab/git-demo"},
            {"cmd": "git tag -a v1.0.0-practice -m 'SRE Lab Release' -f && git tag -n", "explain": "Create and inspect an annotated release tag", "cwd": "/lab/git-demo"},
            {"cmd": "git diff main feature/slo-alert", "explain": "Review exact diff between main and feature/slo-alert before merging", "cwd": "/lab/git-demo"},
        ],
        production_use_case="Tying Git release tags (`v1.4.0-rc1`) directly to the A³P Release Admission Gate & Segregation-of-Duties sign-off.",
        scenarios=[
            scenario(
                "Engineer Accidentally Commits `.env` / API Key to `feature/gemini` and Pushes!",
                "Secret scanning alerts that `GEMINI_API_KEY` was pushed in commit `99aa11b`. Simply committing a deletion in the next commit leaves the key visible in Git history!",
                "1) REVOKE & ROTATE key immediately! 2) Run git-filter-repo --path .env --invert-paths && force-push + add .env to .gitignore",
                "Deleting a file in a new commit does not remove its Blob object from prior commit trees.",
                "Assume any pushed secret is compromised forever: **rotate first**, purge history with `git filter-repo` second, and enforce pre-commit/CI secret scanning + `.gitignore`.",
            ),
        ],
        troubleshooting=["`git rebase` conflicts repeat per commit -> consider `git merge` or `git rerere` (`reuse recorded resolution`)."],
        interview_qa=[
            qa("What is a Squash Merge and when do teams prefer it?", "Squash merge collapses all commits from a feature PR into one single commit on `main`. It keeps `main` tidy and lets SREs revert an entire feature with a single `git revert`, at the cost of losing per-WIP commit granularity.", "basic"),
            qa("A developer accidentally pushed a cloud secret key to GitHub 10 minutes ago. Walk through your incident response.", "First: immediately revoke/rotate the leaked key (it's already potentially scraped). Second: audit cloud/API logs for unauthorized usage. Third: scrub history using `git filter-repo` + force-push, and add `.gitignore` + pre-commit/GitHub secret scanning gates.", "senior"),
        ],
        assignment_items=[
            "Diff feature/slo-alert against main and create an annotated tag in /lab/git-demo",
            "Explain conflict markers (<<<<<<<, =======, >>>>>>>) and resolution steps",
            "Articulate exact incident steps when a secret is pushed to Git",
        ],
        revision=["Annotated tags > lightweight tags", "Squash merge = 1 revertable PR commit", "Leaked secret -> ROTATE FIRST, then git-filter-repo"],
        interview_sim=[
            sim("Why should you NEVER just commit `rm .env` as a fix after pushing an API key to a GitHub repo?", ["Blob remains permanently in Git commit history/reflogs/clones", "Rotate/revoke credential immediately + git-filter-repo"]),
            sim("Compare Trunk-Based Development vs Git Flow (`develop`, `release/*`, `hotfix/*`) for microservices CI/CD.", ["Trunk-based lowers merge conflict pain and fits continuous delivery + feature flags; Git Flow fits strict scheduled mobile/enterprise versioned releases"]),
            sim("How does `git tag -a v1.4.0` differ from `git tag v1.4.0`?", ["Annotated creates a full Git object with tagger, date, message, GPG support; lightweight is just a bare ref pointer"]),
            sim("Mid-conflict, you decide to abort and return cleanly to how things were before `git merge`. What command?", ["git merge --abort (or git rebase --abort)"]),
            sim("How can GitHub branch protection rules enforce Segregation of Duties?", ["Require PR + >=1 SRE/Security CODEOWNERS approval + passing status checks + no force-push on main"]),
        ],
    ),
]

