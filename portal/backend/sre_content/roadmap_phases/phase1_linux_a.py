"""Phase 1 (Days 1-5): Linux Fundamentals to Process & Resource Internals."""

from typing import Dict, List
from .common import make_day, qa, scenario, sec, sim

DAYS_1_TO_5: List[Dict] = [
    make_day(
        day=1,
        phase=1,
        title="Linux Fundamentals: Architecture, Filesystem & Essential Commands",
        subtitle="Linux Architecture, Kernel vs User Space, FHS Directories, Paths & Core CLI Mastery",
        goal="Build a strong Linux foundation covering internal command execution, FHS layout, and production log navigation",
        objective=(
            "Today's objective is to understand not only essential Linux commands, but also what happens internally "
            "when you execute them (Shell -> PATH lookup -> fork()/execve() -> Kernel syscalls) and how SREs navigate "
            "Linux filesystems during live production incidents."
        ),
        concepts=[
            "Linux acts as the resource broker between hardware (CPU, RAM, Disk, NIC) and production workloads (Jenkins, Docker, Kubernetes, Prometheus, Kafka).",
            "Linux separates Kernel Space (privileged hardware, memory, scheduling, VFS, syscalls) from User Space (Shell, GNU utilities, app daemons requesting services via openat()/read()/write()).",
            "FHS organizes everything from '/': /etc (configs), /var/log (logs), /proc (kernel/process virtual FS), /sys (hardware/device model), /tmp (scratch), /opt (addons).",
            "Exported environment variables (`export APP_NAME=aiops`) propagate to child processes; `$PATH` tells the shell where to find executables.",
        ],
        deep_sections=[
            sec(
                "1. What is Linux & 5-Layer Linux Architecture",
                "Linux is an open-source, Unix-like operating system built around the Linux kernel. Whenever tools like Jenkins, Docker, Kubernetes, Prometheus, or Kafka run on a server, Linux arbitrates CPU time, RAM pages, disk blocks, and network sockets across five distinct layers.",
                table={
                    "headers": ["Layer", "Responsibility", "Production SRE Example"],
                    "rows": [
                        ["1. Hardware", "Physical CPU cores, RAM DIMMs, NVMe/disk, NIC", "Server hits 100% CPU or disk IOPS saturation"],
                        ["2. Kernel", "Process scheduling, virtual memory, VFS, network stack, cgroups/namespaces", "Docker containers rely on kernel namespaces & cgroups"],
                        ["3. System Libraries", "glibc / libcurl expose C wrappers around raw kernel syscalls", "App calls fopen() -> glibc invokes openat() syscall"],
                        ["4. Shell", "Command interpreter (bash, zsh, sh, fish) parsing args & pipelines", "Reads $PATH, forks child process, executes binary"],
                        ["5. Applications", "User-facing daemons and tools", "Jenkins, Nginx, Prometheus, Spark, aiops_agent"],
                    ],
                },
                sre_example="Suppose Jenkins suddenly pushes host CPU to 100%. As an SRE you inspect which PID consumes CPU (top/ps), whether RAM/swap is thrashing (free -m/vmstat), whether disk I/O blocks workers (iostat), or whether OOM Killer killed builds (dmesg).",
            ),
            sec(
                "2. Kernel Space vs User Space & What Happens When You Run `ls -l`",
                "Normal applications run in unprivileged User Space and cannot touch hardware directly. They invoke system calls (syscalls) to cross safely into Kernel Space.",
                bullets=[
                    "Step 1: You type `ls -l` in Bash and press Enter.",
                    "Step 2: Bash tokenizes the command (`ls`) and argument (`-l`) and searches `$PATH` directories (e.g. `/usr/bin/ls`). (Note: shell built-ins like `cd` or `echo` run directly inside the shell without a child binary.)",
                    "Step 3: Bash calls `fork()`/`clone()` to create a child process, then `execve(\"/usr/bin/ls\", [\"ls\", \"-l\"], envp)` replaces the child image.",
                    "Step 4: `ls` calls glibc wrappers -> kernel syscalls `openat()` + `getdents64()` + `statx()` to read directory inodes and permissions, then `write(1, ...)` prints output to stdout.",
                ],
                example="$ type cd ls\ncd is a shell builtin\nls is /usr/bin/ls\n\n$ echo $PATH\n/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
            ),
            sec(
                "3. Linux Directory Structure (FHS) & Absolute vs Relative Paths",
                "Everything in Linux forms a single tree rooted at `/`. Absolute paths start at `/` (`/var/log/app.log`); relative paths resolve from `$PWD` (`Logs/app.log`). Symbols: `/` root, `.` current dir, `..` parent dir, `~` home dir, `-` previous dir (`cd -`).",
                table={
                    "headers": ["Directory", "Purpose", "SRE Troubleshooting Use Case"],
                    "rows": [
                        ["/", "Top-level root filesystem", "Mount point anchor for the entire OS"],
                        ["/etc", "System and daemon configuration files", "/etc/nginx/nginx.conf, /etc/hosts, /etc/resolv.conf"],
                        ["/var/log", "System and application logs", "Investigate auth.log, syslog, nginx error.log during outages"],
                        ["/var/lib", "Persistent app state & workspaces", "/var/lib/jenkins, /var/lib/docker"],
                        ["/proc & /sys", "Virtual filesystems exposing kernel/process/device state", "/proc/cpuinfo, /proc/meminfo, /proc/<pid>/fd"],
                        ["/tmp", "Sticky-bit temporary scratch directory", "Ephemeral dumps/locks without cluttering app dirs"],
                        ["/opt & /usr", "Third-party packages (/opt) & installed binaries (/usr/bin)", "/opt/sre, /usr/bin/curl"],
                    ],
                },
            ),
            sec(
                "4. Essential Navigation, Reading, Hidden Files & Environment Variables",
                "During incidents, you never load multi-GB logs into an editor. Use streaming readers (`less`, `head`, `tail -f`), check hidden files (`.env`, `.bashrc`, `.ssh`, `.gitconfig`) with `ls -a`, and inspect command paths with `which` / `type` / `whereis`.",
                table={
                    "headers": ["Command / Flag", "Internal Action", "Example"],
                    "rows": [
                        ["ls -ltr", "Sort by modification time, newest at bottom", "Spot most recently written log file fast"],
                        ["ls -lh / ls -a", "Human sizes (KB/MB) & show dot-hidden files (.env)", "Verify .env secrets are never world-readable"],
                        ["mkdir -p a/b/c", "Create nested directories idempotently", "mkdir -p /lab/linux/Projects Logs Scripts"],
                        ["head -n 20 / tail -f", "Read start of file or follow live log appends", "tail -f /lab/linux/Logs/app.log during restart"],
                        ["env / export KEY=val", "Show env vars; export passes variable to child PIDs", "export GEMINI_MODEL=gemini-2.5-flash"],
                    ],
                },
            ),
        ],
        architecture="User Shell (Bash) -> $PATH Lookup -> fork() + execve() -> glibc -> Kernel Syscalls (openat/read/write) -> VFS -> Storage/ProcFS",
        commands=[
            {"cmd": "uname -a && echo \"SHELL=$SHELL PWD=$PWD\" && ls -la /lab/linux", "explain": "Inspect kernel, active shell, working dir, and hidden files in /lab/linux", "cwd": "/lab/linux"},
            {"cmd": "mkdir -p Projects Logs Scripts Backup && touch Projects/day1_notes.txt && ls -lhtr", "explain": "Create standard SRE workspace and sort entries by newest last", "cwd": "/lab/linux"},
            {"cmd": "head -n 3 Logs/app.log && tail -n 3 Logs/app.log", "explain": "Read top and bottom entries of application log without full load", "cwd": "/lab/linux"},
            {"cmd": "cp Logs/app.log Backup/app_backup.log && type cd ls && which python3", "explain": "Copy log to backup and compare shell builtin (cd) vs $PATH executable (ls)", "cwd": "/lab/linux"},
            {"cmd": "export SRE_ENV=orbstack && python3 -c \"import os; print('Child reads SRE_ENV:', os.getenv('SRE_ENV'))\"", "explain": "Prove exported variables propagate to child processes while unexported ones do not", "cwd": "/lab/linux"},
        ],
        production_use_case="In A³P containers (`aiops_agent`, `practice_lab`, `data_generator`), SREs inspect `/proc/meminfo`, `/etc/resolv.conf`, and `/var/log` with `head`/`tail`/`ls -ltr` while keeping `.env` secrets isolated from Git.",
        scenarios=[
            scenario(
                "Jenkins Server Disk-Full Alert at 2:00 AM",
                "Monitoring fires DiskUsage > 95% on the Jenkins controller host; new CI jobs fail with 'No space left on device'.",
                "df -hT && du -sh /var/log/* /var/lib/jenkins/* 2>/dev/null | sort -hr | head -n 10",
                "Unrotated build artifacts in `/var/lib/jenkins/workspace` and verbose logs in `/var/log` filled `/var`.",
                "Never blindly run `rm -rf`. Identify the exact top directories with `du -sh`, archive/truncate old logs (`truncate -s 0` if still held open), and configure logrotate + Jenkins workspace retention.",
            ),
            scenario(
                "App Fails After Restart — Live Dual-Terminal Log Watch",
                "Nginx/API fails healthchecks immediately after a config reload.",
                "Terminal 1: tail -f /lab/linux/Logs/app.log | Terminal 2: nginx -t -c /lab/nginx-demo/nginx.conf",
                "Watching live log appends (`tail -f`) while triggering reload exposes exact startup tracebacks and config syntax errors immediately.",
                "Always validate syntax (`nginx -t`) before reload and stream logs concurrently.",
            ),
        ],
        troubleshooting=[
            "'No such file or directory' -> run `pwd` and check relative vs `/` absolute paths.",
            "Hidden `.env` or `.ssh` missed in `ls` -> always pass `ls -la` when auditing config directories.",
            "Never run `rm -rf` with unquoted or empty variables (`rm -rf $DIR/` expands to `rm -rf /` if `$DIR` is unset!).",
        ],
        interview_qa=[
            qa("What is the difference between Linux and Unix?", "Unix is a family of proprietary/certified OSes originally derived from AT&T Unix (AIX, Solaris, HP-UX). Linux is an open-source POSIX/Unix-like kernel paired with GNU/user-space tooling.", "basic"),
            qa("What is the difference between Shell and Kernel, and between / and /root?", "The Shell (bash/zsh) runs in User Space to parse commands and spawn processes; the Kernel runs in privileged Kernel Space managing CPU, RAM, devices, and syscalls. `/` is the root of the entire filesystem; `/root` is only the root superuser's home directory.", "basic"),
            qa("What happens internally when you execute `ls -l`?", "Bash parses `ls` and `-l`, finds `/usr/bin/ls` via `$PATH`, calls `fork()` to spawn a child, calls `execve()` to load `ls`, which uses `openat()`/`getdents64()`/`statx()` syscalls to read directory entries from the kernel VFS and `write()` to print formatted output.", "senior"),
            qa("A production Linux server becomes very slow. What do you check first?", "Never reboot first (that destroys evidence). Run `uptime`, `top`/`ps`, `free -m`, `df -h`, `vmstat 1 3`, `iostat -xz 1 2` to pinpoint whether CPU run-queue, RAM/swap thrashing, disk I/O wait, or log flood is the bottleneck, then inspect `/var/log`.", "senior"),
        ],
        assignment_items=[
            "Explain the 5 layers of Linux architecture and Kernel Space vs User Space",
            "Create /lab/linux/{Projects,Logs,Scripts,Backup} and inspect with ls -lhtr",
            "Create 3 log entries, copy one to Backup, rename with mv, and inspect head/tail",
            "Verify absolute vs relative paths (/, ., .., ~, -) and hidden files (.env)",
            "Explain internal steps of executing ls -l (fork/execve/syscalls) and exported env vars",
        ],
        revision=["5 layers: HW->Kernel->Libs->Shell->Apps", "fork()+execve()+syscalls", "FHS: /etc /var/log /proc /sys /tmp", "ls -lhtr & tail -f", "export passes vars to child PIDs"],
        interview_sim=[
            sim("A Jenkins Linux build server suddenly becomes very slow and jobs hang. Which Linux commands do you run first, how do you distinguish CPU vs RAM vs Disk I/O, and how do you inspect without restarting?", ["uptime + vmstat 1 3 (r, b, wa, si/so)", "free -m (available vs swap)", "iostat -xz 1 & df -h", "Never reboot before capturing evidence"]),
            sim("Explain step-by-step what happens inside the shell and Linux kernel when you run `ls -l /var/log` vs `cd /var/log`.", ["Built-in vs PATH lookup", "fork()/clone() + execve()", "openat/getdents64/statx syscalls"]),
            sim("Your CI server triggers a Disk-Full alert on `/`. Walk through how you safely locate what is eating disk without breaking running jobs.", ["df -hT & df -i", "du -sh /* | sort -hr", "Avoid blind rm -rf; check lsof +L1"]),
            sim("A developer exports `API_KEY=abc` without `export` in a shell script, and their Python subprocess reads `None`. Why, and how do you protect `.env`?", ["Shell var vs exported envp to child processes", "ls -la hidden files + .gitignore + chmod 600"]),
            sim("What is the difference between `/proc`, `/sys`, `/var/log`, and `/tmp`, and give one real SRE debugging command for each.", ["/proc/meminfo or /proc/<pid>/fd", "/sys/block", "/var/log/*.log with tail -f", "/tmp sticky bit scratch"]),
        ],
    ),

    make_day(
        day=2,
        phase=1,
        title="Linux Permissions, Ownership & Special Bits",
        subtitle="rwx Octals (755/644/600), chmod, chown, umask & SUID/SGID/Sticky Bit",
        goal="Control Linux file/directory access safely and troubleshoot container UID/GID permission outages",
        objective=(
            "Understand how Linux stores permissions inside file inodes, how directory `x` (execute/traverse) differs "
            "from file `x`, how `umask` computes default permissions, and how SUID/SGID/Sticky bits protect multi-user hosts and containers."
        ),
        concepts=[
            "Every inode tracks 3 identity scopes: Owner (u), Group (g), Others (o) with bits r=4 (read), w=2 (write), x=1 (execute/traverse).",
            "For a directory, `r` lets you list filenames (`ls`), `w` lets you create/delete/rename entries (together with `x`), and `x` lets you traverse (`cd`) into it.",
            "`umask` subtracts default permissions at creation time: `022` yields `644` (`rw-r--r--`) for files and `755` (`rwxr-xr-x`) for directories.",
            "Special bits: SUID (`4xxx`) runs binary as file owner (`passwd`); SGID (`2xxx`) inherits parent directory group on new files; Sticky Bit (`1xxx` on `/tmp`) blocks deleting others' files.",
        ],
        deep_sections=[
            sec(
                "1. Symbolic & Octal Permission Math (r=4, w=2, x=1)",
                "Linux checks permissions in strict order: if your effective UID matches the file owner, ONLY owner bits apply; else if your GID matches file group, group bits apply; otherwise other bits apply.",
                table={
                    "headers": ["Octal", "Symbolic", "Typical SRE Usage"],
                    "rows": [
                        ["600", "rw-------", "SSH private keys (~/.ssh/id_rsa) & .env secrets (like A³P .env)"],
                        ["644", "rw-r--r--", "Config files (/etc/nginx/nginx.conf, YAML manifests)"],
                        ["750", "rwxr-x---", "Team-restricted ops scripts & log directories"],
                        ["755", "rwxr-xr-x", "Executables (/usr/bin) & traversable app directories"],
                        ["777", "rwxrwxrwx", "DANGEROUS in prod — anyone can overwrite scripts/configs (security audit fail)"],
                    ],
                },
                example="$ chmod 750 deploy.sh    # u=rwx(7), g=r-x(5), o=---(0)\n$ stat -c '%a %U:%G %n' deploy.sh\n750 root:ops deploy.sh",
            ),
            sec(
                "2. Special Permissions: SUID (4000), SGID (2000), Sticky Bit (1000) & umask",
                "Standard 3-digit octals have a hidden 4th leading digit for special privilege bits.",
                table={
                    "headers": ["Special Bit", "Octal / Display", "Behavior & Production Example"],
                    "rows": [
                        ["SUID", "4755 (-rwsr-xr-x)", "Process runs with file owner's EUID (e.g. /usr/bin/passwd needs root to write /etc/shadow)"],
                        ["SGID (dir)", "2775 (drwxrwsr-x)", "New files created inside inherit directory's group (shared DevOps team folders)"],
                        ["Sticky Bit", "1777 (drwxrwxrwt)", "Anyone can write to /tmp, but only owner/root can unlink their own file"],
                    ],
                },
                sre_example="Why did `spark-submitter` in this A³P OrbStack platform originally fail? Spark's container runs as UID 185 (`spark`) while the Ivy cache defaulted to a non-writable home directory. Fixing ownership/HOME to writable `/tmp/.ivy2` (sticky-bit protected) resolved it cleanly without making the container root!",
            ),
        ],
        architecture="Process (EUID/EGID) -> VFS Inode Check (Special Bits 4/2/1 + Owner/Group/Other) -> Allow/EACCES (Permission Denied)",
        commands=[
            {"cmd": "ls -ld /tmp /lab/linux/Scripts/health_check.sh", "explain": "Verify sticky bit 't' on /tmp (1777) and +x bits on health_check.sh", "cwd": "/lab/linux"},
            {"cmd": "umask && touch /tmp/day2_file && mkdir -p /tmp/day2_dir && ls -ld /tmp/day2_file /tmp/day2_dir", "explain": "Inspect umask 0022 producing 644 files and 755 directories", "cwd": "/lab/linux"},
            {"cmd": "chmod 600 /tmp/day2_file && stat -c '%a %A %U:%G %n' /tmp/day2_file && rm -rf /tmp/day2_file /tmp/day2_dir", "explain": "Set strict 600 permissions like .env secrets, verify via stat, clean up", "cwd": "/lab/linux"},
            {"cmd": "stat -c '%a %U:%G %n' /lab/linux/Scripts/health_check.sh", "explain": "Inspect numeric octal mode and UID:GID ownership", "cwd": "/lab/linux"},
        ],
        production_use_case="Used daily when tightening `.env` files (`chmod 600`), diagnosing Kubernetes `runAsNonRoot` volume mount `Permission denied`, and securing CI runners.",
        scenarios=[
            scenario(
                "Kubernetes Pod Volume Mount Fails with `Permission denied`",
                "A newly hardened non-root microservice (`USER 1001`) crashes on startup trying to write `/data/state.db` on a mounted PV.",
                "kubectl logs pod -n prod; stat -c '%u:%g %a' /data (or inspect Pod securityContext.fsGroup)",
                "Host/PV directory was created as `0:0` (`root:root`, mode `755`), so UID `1001` cannot write.",
                "Set `securityContext: { runAsUser: 1001, fsGroup: 1001 }` in Kubernetes or `chown -R 1001:1001` during image/init setup — never fall back to `chmod 777`.",
            ),
        ],
        troubleshooting=[
            "Script has `chmod +x` (`644` -> `755`) yet still fails -> check parent directory `+x` traverse permission.",
            "`chmod 777` used as a quick fix -> immediate SOC2/security risk; use `chown` + `750` or `fsGroup` instead.",
        ],
        interview_qa=[
            qa("Difference between `chmod` and `chown`?", "`chmod` changes permission mode bits (rwx/SUID/SGID/Sticky) on an inode; `chown` changes user and/or group ownership.", "basic"),
            qa("Explain `755`, `600`, and Sticky Bit.", "`755` = owner rwx (7), group r-x (5), others r-x (5). `600` = owner rw- only (secrets/SSH keys). Sticky bit (`1777` on `/tmp`) prevents users from deleting files owned by other users in a shared directory.", "basic"),
            qa("What happens if a directory has `r` (4) without `x` (1)?", "You can list filenames (`ls`) with `?` metadata errors, but you cannot `cd` into it or open any file inside because kernel path traversal requires execute (`x`) permission on every ancestor directory.", "senior"),
        ],
        assignment_items=[
            "Calculate octal vs symbolic permissions for 755, 750, 644, 600",
            "Verify umask behavior on new files vs directories in /tmp",
            "Inspect sticky bit on /tmp and compare chmod vs chown",
            "Explain why chmod 777 is forbidden in production & how fsGroup fixes container volume perms",
        ],
        revision=["r=4 w=2 x=1", "Dir x = traverse/cd", "SUID=4, SGID=2, Sticky=1 (/tmp)", "600 for secrets, 755 dirs, never 777"],
        interview_sim=[
            sim("A containerized Spark worker running as UID 185 crashes writing to a mounted `/data` volume with `Permission denied`. How do you diagnose and fix it without switching to root or `chmod 777`?", ["stat / ls -ln numeric UID/GID", "chown or Kubernetes fsGroup / runAsUser", "Sticky bit /tmp fallback"]),
            sim("Explain SUID, SGID, and Sticky Bit with one concrete Linux binary or directory example for each.", ["SUID: /usr/bin/passwd (4755)", "SGID on shared dir (2775)", "Sticky bit on /tmp (1777)"]),
            sim("Why can a user with `rw-` permissions on `/app/app.conf` fail to read it if `/app` has mode `744`?", ["Directory x bit required for inode traversal", "Explain r vs x on directories"]),
            sim("A developer checks in an executable script and SSH key (`chmod 644 id_rsa`). What happens on SSH connect and what `umask` prevents world-readable secrets?", ["SSH refuses private key > 600", "umask 077 vs 022"]),
            sim("An attacker drops a binary into `/tmp`. How does sticky bit (`1777`) behave, and why is `/tmp` often mounted `noexec,nosuid` in hardened servers?", ["Sticky bit prevents cross-user unlink", "noexec/nosuid stops payload execution"]),
        ],
    ),

    make_day(
        day=3,
        phase=1,
        title="Linux Users, Groups & Sudo Governance",
        subtitle="/etc/passwd, /etc/shadow, /etc/group, useradd/usermod, PAM & visudo",
        goal="Administer Linux identity files, least-privilege sudoers rules, and non-root service accounts",
        objective=(
            "Learn how Linux authenticates users via `/etc/passwd` + `/etc/shadow` + PAM, separates Authentication from Authorization, "
            "and enforces audited least-privilege elevation via `sudo` rather than direct root access."
        ),
        concepts=[
            "`/etc/passwd` is world-readable (needed to map UID<->username in `ls -l`), storing 7 colon fields: `name:x:UID:GID:comment:home:shell`.",
            "`/etc/shadow` is `root`-only (`640`/`000`) storing salted cryptographic password hashes (`$6$` SHA-512 / `$y$` yescrypt) and expiry aging.",
            "Authentication = proving who you are (SSH key, password, OIDC). Authorization = proving what you are allowed to execute (`sudoers`, K8s RBAC).",
            "Always edit `/etc/sudoers` or `/etc/sudoers.d/*` with `visudo`, which runs a syntax check before saving so a typo never locks out admins.",
        ],
        deep_sections=[
            sec(
                "1. Anatomy of `/etc/passwd`, `/etc/shadow`, and `/etc/group`",
                "Every process runs under a numeric UID and GID stored in the kernel task struct; usernames are strictly a user-space lookup via `/etc/passwd` and `/etc/group`.",
                example="# /etc/passwd format (7 fields):\nappuser:x:1001:1001:Service Account:/home/appuser:/bin/bash\nsystemsvc:x:998:998::/var/lib/svc:/usr/sbin/nologin\n\n# /etc/group format:\ndocker:x:999:ubuntu,ahmed",
                table={
                    "headers": ["Command", "Purpose", "Production Flag Example"],
                    "rows": [
                        ["useradd -r -s /usr/sbin/nologin svc", "Create non-login system service user", "Least-privilege daemon user without shell"],
                        ["usermod -aG docker ahmed", "Append user to supplementary group (-a preserves existing groups!)", "Forgetting `-a` removes all existing groups (incident!)"],
                        ["id / whoami / groups", "Show effective UID, primary GID, and all supplementary groups", "Verify group membership after re-login"],
                        ["visudo -c", "Validate /etc/sudoers and /etc/sudoers.d/* syntax", "Run in CI/Ansible before deploying sudo rules"],
                    ],
                },
            ),
            sec(
                "2. Authentication vs Authorization & Least-Privilege `sudoers`",
                "Giving engineers the root password destroys auditability and fails SOC2/ISO compliance. Scoped `sudoers` entries grant exact commands logged to `/var/log/auth.log`.",
                example="# /etc/sudoers.d/sre-nginx\n%sre ALL=(root) NOPASSWD: /usr/bin/systemctl reload nginx, /usr/sbin/nginx -t",
                sre_example="In our A³P `/lab/docker-demo/Dockerfile`, creating `RUN useradd -m appuser` and `USER appuser` ensures a compromised Python endpoint cannot overwrite `/etc` or install rootkits.",
            ),
        ],
        architecture="SSH/Terminal -> PAM AuthN (/etc/passwd + /etc/shadow / SSH Pubkey) -> sudo AuthZ (/etc/sudoers) -> Audited Syscall",
        commands=[
            {"cmd": "id && whoami && groups", "explain": "Inspect active UID, primary GID, and supplementary groups", "cwd": "/lab"},
            {"cmd": "head -n 8 /etc/passwd", "explain": "Examine UID 0 (root) vs service accounts (<1000) and login shells", "cwd": "/lab"},
            {"cmd": "grep -E 'appuser|root|www-data' /etc/passwd /etc/group || head -n 6 /etc/group", "explain": "Inspect user and group file mappings", "cwd": "/lab"},
            {"cmd": "ls -l /etc/passwd /etc/shadow && grep -n 'USER' /lab/docker-demo/Dockerfile", "explain": "Compare passwd vs shadow security and inspect container non-root USER", "cwd": "/lab"},
        ],
        production_use_case="Enforcing Segregation of Duties across Linux bastions, Jenkins agents, and non-root containers (`appuser`, `spark uid=185`).",
        scenarios=[
            scenario(
                "Admin Runs `usermod -G docker ci_user` and Breaks Production Sudo!",
                "An engineer grants `docker` group access to `ci_user`, and suddenly `ci_user` loses `sudo` access everywhere.",
                "id ci_user && grep ci_user /etc/group",
                "Using `-G` without `-a` (append) overwrote all supplementary groups including `sudo`/`wheel`.",
                "Restore `usermod -aG sudo,docker ci_user` immediately and document `-aG` in team runbooks.",
            ),
        ],
        troubleshooting=[
            "SSH succeeds or fails silently for service user -> check login shell `/usr/sbin/nologin` vs `/bin/bash` in `/etc/passwd`.",
            "Edited `/etc/sudoers` directly with `vi` and made a syntax error -> `sudo` stops working for everyone; always use `visudo`.",
        ],
        interview_qa=[
            qa("Difference between Authentication and Authorization?", "Authentication verifies identity (SSH key, password, MFA). Authorization checks what that authenticated identity is permitted to perform (`sudoers`, Linux file modes, K8s RBAC).", "basic"),
            qa("Why is `/etc/passwd` readable by all users while `/etc/shadow` is not?", "`ls -l` and user-space tools need UID-to-name mapping from `/etc/passwd`. Password hashes moved to `/etc/shadow` (readable only by root/shadow) to block offline cracking.", "senior"),
            qa("What happens if you run `usermod -G opsuser alice` instead of `usermod -aG opsuser alice`?", "Without `-a`, `alice` is removed from every other supplementary group she belonged to (such as `sudo` or `docker`), potentially causing an immediate access outage.", "senior"),
        ],
        assignment_items=[
            "Inspect all 7 fields of /etc/passwd and explain why /etc/shadow is separate",
            "Explain Authentication vs Authorization with Linux sudo and Kubernetes RBAC",
            "Audit Dockerfiles in A³P to confirm non-root user creation",
            "Explain why usermod requires -aG and why visudo protects admins",
        ],
        revision=["passwd (UID map) != shadow (hashes)", "AuthN != AuthZ", "Always usermod -aG", "Edit sudoers via visudo only"],
        interview_sim=[
            sim("An engineer accidentally corrupts `/etc/sudoers` on a cloud VM without root SSH login enabled. How do you prevent this before it happens, and how could you recover in AWS/GCP?", ["visudo -c / drop-in /etc/sudoers.d", "Rescue/serial console or detach root EBS volume", "Configuration management CI check"]),
            sim("Why should containers use `USER appuser` instead of `root`, and what breaks when converting an existing Nginx/Python image to non-root?", ["Privilege escalation blast radius", "Privileged ports < 1024", "Writable /var/log, /tmp, pid files"]),
            sim("Explain what happens internally when you run `sudo systemctl restart nginx`.", ["PAM/timestamp check", "sudoers rule match", "Logs to auth.log/journald", "EUID=0 exec"]),
            sim("A service account has `/usr/sbin/nologin` in `/etc/passwd`. Can it still own processes and cron jobs?", ["Yes, UID exists for daemons", "Blocks interactive login shell only"]),
            sim("After `usermod -aG docker ahmed`, `docker ps` still says `permission denied` in the current terminal. Why?", ["Group list populated at login session creation", "newgrp docker or re-login"]),
        ],
    ),

    make_day(
        day=4,
        phase=1,
        title="Linux Processes, Signals, Zombies & Daemons",
        subtitle="ps, top, kill, SIGTERM vs SIGKILL, Process States (R/S/D/Z) & Graceful Shutdown",
        goal="Inspect Linux process trees, control job priorities, and debug stuck/zombie/daemon workloads",
        objective=(
            "Master how Linux creates and schedules processes (`fork`, `PID`, `PPID`, `nice`), how signals cleanly shut down "
            "or force-kill services (`SIGTERM 15` vs `SIGKILL 9`), and why uninterruptible (`D`) vs zombie (`Z`) states happen in production."
        ),
        concepts=[
            "Every running process has a unique `PID`, parent `PPID`, niceness (`-20` highest priority to `+19` lowest), and kernel scheduling state.",
            "Signals: `SIGHUP (1)` reload config, `SIGINT (2)` Ctrl+C, `SIGTERM (15)` polite shutdown (catchable!), `SIGKILL (9)` kernel immediate termination (uncatchable!).",
            "Zombie (`Z`) processes are dead children whose parent hasn't called `wait()` to read their exit code; `kill -9` on a zombie does NOTHING because it is already dead.",
            "Daemons detach from controlling terminals and run in background (managed by systemd on hosts or container PID 1 inside Docker/K8s).",
        ],
        deep_sections=[
            sec(
                "1. Linux Process States (`R`, `S`, `D`, `T`, `Z`)",
                "Recognizing process state letters in `ps aux` or `top` immediately tells you whether a server is CPU-bound, sleeping, blocked on broken storage, or leaking zombie child entries.",
                table={
                    "headers": ["State", "Meaning", "Production Cause & Action"],
                    "rows": [
                        ["R", "Running / Runnable", "On CPU or waiting in run-queue; high count = CPU saturation"],
                        ["S", "Interruptible Sleep", "Normal idle waiting for socket/timer/event; wakes on signal"],
                        ["D", "Uninterruptible Disk/NFS Sleep", "Kernel I/O wait; CANNOT be killed with `kill -9` — check storage/NFS!"],
                        ["Z", "Zombie (Defunct)", "Dead child awaiting parent `wait()`; check/fix/restart parent PPID"],
                        ["T", "Stopped (SIGSTOP/Ctrl+Z)", "Paused process; resume with `fg`/`bg` or `kill -CONT`"],
                    ],
                },
            ),
            sec(
                "2. `SIGTERM (15)` vs `SIGKILL (9)` & Kubernetes Graceful Shutdown",
                "Using `kill -9` by reflex corrupts in-flight database transactions, drops open HTTP requests (502s), and skips PySpark streaming checkpoints.",
                example="# Graceful shutdown sequence (Kubernetes default: 30s grace period):\n1. Pod removed from Service Endpoints AND kubelet sends SIGTERM (15) to PID 1\n2. App flushes logs, drains keep-alive HTTP connections, checkpoints Kafka offsets\n3. Only if still running after terminationGracePeriodSeconds -> kubelet sends SIGKILL (9)",
                sre_example="Notice in our A³P `docker-compose.yml` or Python apps: if a Dockerfile wraps `CMD python app.py` in `sh -c` without `exec`, `/bin/sh` becomes PID 1 and may swallow `SIGTERM`, forcing a 10–30s wait followed by `SIGKILL`!",
            ),
        ],
        architecture="Parent PID -> fork() -> Child PID -> [R / S / D / Z] -> SIGTERM(15) cleanup -> exit() -> Parent wait() reap",
        commands=[
            {"cmd": "ps aux --sort=-%cpu | head -n 10", "explain": "Inspect top CPU processes with PID, STAT, and command", "cwd": "/lab"},
            {"cmd": "ps -eo pid,ppid,stat,ni,comm | head -n 12", "explain": "Examine parent PPID tree, process state letters (S/R/D/Z), and nice values", "cwd": "/lab"},
            {"cmd": "sleep 30 & jobs -l && pkill -TERM -f 'sleep 30' || true", "explain": "Start background job, inspect job table, and shut down cleanly with SIGTERM", "cwd": "/lab"},
            {"cmd": "nice -n 10 python3 -c \"print('Batch work ran at lower CPU priority nice=10')\"", "explain": "Run low-priority maintenance script without starving latency-critical apps", "cwd": "/lab"},
        ],
        production_use_case="Debugging Kubernetes Pods stuck in `Terminating`, stopping batch backup scripts gently with `nice`/`renice`, and keeping Spark checkpoints clean.",
        scenarios=[
            scenario(
                "Hundreds of `<defunct>` Zombie Processes Filling PID Table (`fork: Resource temporarily unavailable`)",
                "A container running a wrapper entrypoint spawns short-lived Python workers; `ps aux` shows 3,000 `[python3] <defunct>` Z-state processes.",
                "ps -eo pid,ppid,stat,comm | grep 'Z' | head -n 10",
                "PID 1 (often a simple bash script inside the container) does not reap orphaned grandchildren after parents exit (`wait()`).",
                "Notice `kill -9 <zombie_pid>` will not clear zombies. Restart/fix the parent PPID or run containers with `--init` / `tini` so PID 1 reaps children automatically.",
            ),
        ],
        troubleshooting=[
            "Running `kill -9` on a `D`-state process does nothing -> investigate stalled NFS mount, hung block disk, or kernel driver.",
            "Running `kill <pid>` defaults to `SIGTERM (15)`, NOT `SIGKILL (9)`.",
        ],
        interview_qa=[
            qa("Difference between `SIGTERM` and `SIGKILL`?", "`SIGTERM` (15) requests graceful termination and can be caught by the process to close DB pools and flush buffers. `SIGKILL` (9) is intercepted directly by the kernel, cannot be caught/ignored, and kills immediately.", "basic"),
            qa("What is a Zombie process and how do you remove one?", "A Zombie (`Z`) is a terminated process whose exit status has not yet been collected (`wait()`) by its parent. You cannot kill an already-dead zombie with `kill -9`; you must fix or signal/restart its parent (`PPID`).", "senior"),
            qa("Why do `docker stop` or `kubectl delete pod` sometimes hang for 10–30 seconds before dying?", "Usually the container runs a shell script as PID 1 without `exec` or signal forwarding (`tini`), so `SIGTERM` isn't forwarded to the child server process, forcing Docker/Kubelet to wait for the grace timeout and send `SIGKILL` (exit 137).", "senior"),
        ],
        assignment_items=[
            "Inspect process states (R, S, D, Z) and parent-child PPID relationships with ps -eo",
            "Launch a background job, inspect via jobs/ps, pause/resume or stop via SIGTERM",
            "Use nice -n 10 to lower priority of a batch job",
            "Explain why kill -9 fails on Zombie (Z) and Uninterruptible (D) processes",
        ],
        revision=["SIGTERM (15) != SIGKILL (9)", "Z = dead awaiting parent wait()", "D = uninterruptible I/O (not killable)", "Containers need exec/tini at PID 1"],
        interview_sim=[
            sim("A critical payment container takes a full 30 seconds to terminate on every Kubernetes rolling update, causing intermittent 502s. Why, and how do you fix it?", ["PID 1 shell swallowing SIGTERM", "Use exec in entrypoint or tini", "preStop hook sleep before SIGTERM while Endpoints drain"]),
            sim("You find 500 `Z` (defunct) processes on a host. A junior engineer runs `kill -9` on their PIDs and asks why they are still there. Explain.", ["Zombie is already terminated", "Parent PPID never called wait()", "Inspect PPID via ps -eo pid,ppid,stat"]),
            sim("Fifty processes are stuck in `D` state and load average is 65 while CPU idle is 95%. What is happening?", ["Uninterruptible I/O sleep (NFS/disk hang)", "Check dmesg, iostat -xz, mount options (soft/hard)"]),
            sim("When would you intentionally use `nice` / `renice` in production?", ["Log compression / backup / rsync batch jobs", "Protect latency-critical web/DB processes"]),
            sim("What is the difference between exit code 137 and exit code 143 in Linux/Docker?", ["128 + 9 = 137 (SIGKILL / OOMKill)", "128 + 15 = 143 (SIGTERM graceful)"]),
        ],
    ),

    make_day(
        day=5,
        phase=1,
        title="CPU, Memory, Load Average, Swap & OOM Killer",
        subtitle="uptime, free -m, vmstat, iostat, sar, lscpu & Kernel OOM Score",
        goal="Distinguish CPU saturation, RAM exhaustion, swap thrashing, and I/O wait accurately",
        objective=(
            "Interpret Linux performance counters without misreading cached RAM as 'full memory' or high load average as always meaning 100% CPU, "
            "and know how the Linux OOM Killer chooses victims (`oom_score`, Exit 137)."
        ),
        concepts=[
            "Load Average (1m, 5m, 15m) measures average processes either runnable on CPU (`R`) OR waiting in uninterruptible disk/NFS I/O (`D`). Compare against `nproc`!",
            "`free -m`: Linux aggressively uses unused RAM as Page Cache (`buff/cache`) and immediately reclaims it when apps need memory — ALWAYS check `available`, not `free`!",
            "`vmstat 1`: watch `r` (CPU run queue), `b` (blocked I/O processes), `si/so` (swap in/out thrashing!), and `wa` (% CPU waiting on disk I/O).",
            "When RAM + Swap exhaust (or a container hits its cgroup `memory.max`), the Linux kernel OOM Killer terminates the highest `oom_score` process with `SIGKILL` (Exit `137`).",
        ],
        deep_sections=[
            sec(
                "1. Decoding `free -m`, Page Cache & `available` RAM",
                "Junior engineers panic seeing `free = 120 MB` on a 16 GB host when `buff/cache` is `10 GB` and `available` is `10.1 GB`. Page cache accelerates disk reads and is instantly evictable.",
                example="              total        used        free      shared  buff/cache   available\nMem:          16000        4800         200         150       11000       10800\nSwap:          2048           0        2048\n# Reality: Only ~30% used! 10.8 GB is truly available for applications.",
            ),
            sec(
                "2. Decoding `vmstat 1` & Load Average Patterns",
                "High load average does NOT always mean CPU exhaustion — comparing `load`, `%us`, `%wa`, and `si/so` separates three completely different outages.",
                table={
                    "headers": ["Pattern (4-vCPU host)", "vmstat / top Signal", "True Root Cause"],
                    "rows": [
                        ["Load 14.0, %us=98%, %wa=0%", "vmstat r=14, si=0, so=0", "True CPU saturation (hot loop / GC / unindexed regex)"],
                        ["Load 18.0, %us=5%, %wa=72%", "vmstat b=16, iostat await>100ms", "Disk / EBS / NFS I/O bottleneck blocking processes in D state"],
                        ["Load 22.0, si=4096, so=8192", "available ~ 0, kswapd0 100% CPU", "Memory exhaustion + Swap thrashing (right before OOMKill)"],
                    ],
                },
                sre_example="In A³P Prometheus alerts, `HighMemorySaturation` triggers when `app_memory_usage_mb > 800`, well before OrbStack's container cgroup OOMKills the service with Exit `137`.",
            ),
        ],
        architecture="App Memory Alloc -> Page Cache Reclaim -> Swap (si/so) -> cgroup / Host OOM Killer (oom_score) -> SIGKILL (137)",
        commands=[
            {"cmd": "uptime && nproc && lscpu | grep -E 'Architecture|CPU\\(s\\)|Model name'", "explain": "Check 1m/5m/15m load averages against allocated vCPU count", "cwd": "/lab"},
            {"cmd": "free -m", "explain": "Compare 'free' vs 'buff/cache' vs truly 'available' memory", "cwd": "/lab"},
            {"cmd": "vmstat 1 3", "explain": "Read run-queue (r), blocked I/O (b), swap (si/so), user/sys/wait CPU", "cwd": "/lab"},
            {"cmd": "iostat -xz 1 2", "explain": "Measure disk read/write await latency and %util saturation", "cwd": "/lab"},
        ],
        production_use_case="Triaging `cpu_spike` and `memory_leak` chaos drills in A³P and sizing Spark Worker memory caps (`1536M`) safely on OrbStack.",
        scenarios=[
            scenario(
                "Container Keeps Restarting Silently with `Exit Code 137` (Host Still Has 4 GB Free RAM)",
                "A Spark/Java worker pod restarts mid-batch; `free -m` on the host shows plenty of memory.",
                "docker inspect <container> --format '{{.State.OOMKilled}} {{.State.ExitCode}}' ; dmesg -T | grep -i oom",
                "Container hit its **cgroup memory limit** (`1536M` / Pod `resources.limits.memory`), triggering a cgroup-scoped OOMKill even though the host VM had spare RAM.",
                "Profile heap/off-heap usage (set `-Xmx` / Spark executor overhead <= 75% of cgroup limit) and raise memory limit safely instead of leaving `limits` unbounded.",
            ),
        ],
        troubleshooting=[
            "Never alert on `MemFree` — always alert on `MemAvailable` (< 15%).",
            "On Kubernetes nodes, swap is usually disabled so memory exhaustion triggers OOMKill immediately rather than minutes of swap thrashing.",
        ],
        interview_qa=[
            qa("How do you interpret Load Average on a 4-CPU vs 16-CPU machine?", "Load average includes both runnable CPU tasks AND uninterruptible I/O (`D`) tasks. Load `8.0` is 200% overloaded on 4 vCPUs, but only 50% utilized on 16 vCPUs.", "basic"),
            qa("Why is `available` memory in `free -m` more accurate than `free`?", "`free` excludes reclaimable page cache (`buff/cache`) that Linux uses for filesystem speedup and can instantly hand back to apps; `available` estimates total memory allocatable without swapping.", "senior"),
            qa("How does the Linux OOM Killer decide which process to kill, and how can you protect a critical DB?", "Kernel computes `oom_score` (mainly % of RAM/swap used, adjusted by `oom_score_adj` from `-1000` to `+1000`) and sends `SIGKILL` to the highest scorer. Critical daemons or K8s `Guaranteed` pods get lower/negative `oom_score_adj`.", "senior"),
        ],
        assignment_items=[
            "Compare uptime load average against nproc on /lab",
            "Read free -m and explain the difference between free, buff/cache, and available",
            "Run vmstat 1 3 and iostat -xz 1 2 and identify r, b, si/so, wa, and await",
            "Explain how cgroup OOMKill (Exit 137) differs from host-wide OOM",
        ],
        revision=["Load = R + D tasks vs nproc", "Check 'available' in free -m", "si/so != 0 = swap thrashing", "Exit 137 = OOMKilled"],
        interview_sim=[
            sim("A 4-vCPU database server has a 1-minute load average of 20.0, yet `top` shows 92% idle CPU (`id`) and 4% user (`us`). What is happening and how do you confirm it?", ["Check %wa in top/vmstat and b column", "Run iostat -xz 1 for await / %util", "Check dmesg / hung NFS/disk"]),
            sim("Your Kubernetes Python AI worker died with Exit Code 137. Application logs show no errors right before dying. Explain why and how you prove OOMKill.", ["kubectl describe pod -> Reason: OOMKilled", "cgroup limit vs host RAM", "dmesg oom-killer + memory profiling"]),
            sim("An engineer pages you because `free -m` shows only 90 MB `free` on a 32 GB Prometheus server. Do you need to scale RAM?", ["Explain Linux Page Cache / buff/cache", "Check 'available' column", "Prometheus mmap TSDB heavily caches"]),
            sim("How does `oom_score_adj` relate to Kubernetes Pod QoS classes (`Guaranteed`, `Burstable`, `BestEffort`)?", ["Guaranteed -> -997", "BestEffort -> +1000 (evicted/killed first)", "Burstable -> proportional"]),
            sim("What is the danger of heavy swap (`si/so`) for latency-sensitive APIs compared to failing fast?", ["Disk swap is ~100,000x slower than RAM", "Causes extreme p99 latency spikes & cascading retries"]),
        ],
    ),
]

