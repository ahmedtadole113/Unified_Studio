"""Phase 1 (Days 6-10): Storage, Linux Networking, Bash Scripting, Systemd & Troubleshooting."""

from typing import Dict, List
from .common import make_day, qa, scenario, sec, sim

DAYS_6_TO_10: List[Dict] = [
    make_day(
        day=6,
        phase=1,
        title="Linux Storage, Inodes, Filesystems, LVM & RAID",
        subtitle="mount/umount, df -h vs df -i (Inodes), du -sh, lsof +L1, ext4 vs xfs & LVM",
        goal="Inspect storage capacity, inode exhaustion, deleted-but-open files, and filesystem trade-offs",
        objective=(
            "Understand how Linux separates directory names from inodes and data blocks, why 'No space left on device' happens "
            "even at 50% disk capacity (`df -i` inode exhaustion or unlinked open FDs via `lsof +L1`), and when to choose ext4 vs XFS + LVM."
        ),
        concepts=[
            "Every file has one inode storing UID/GID, permissions, timestamps, link count, and pointers to data blocks — the filename itself lives in the parent directory entry.",
            "`df -h` reads mounted superblock capacity; `du -sh` walks directory trees. When `df` >> `du`, a running daemon still holds an unlinked (deleted) file handle (`lsof +L1`).",
            "`ext4` supports shrinking offline and growing online; `xfs` excels at massive files/parallel throughput and supports online grow only (cannot shrink!).",
            "LVM adds Physical Volume (PV) -> Volume Group (VG) -> Logical Volume (LV) flexibility so filesystems grow online without re-partitioning.",
        ],
        deep_sections=[
            sec(
                "1. Inodes, Hard Links, Soft Links & Deleted-Open Files (`lsof +L1`)",
                "Removing a file (`rm app.log`) only unlinks the directory pointer and decrements the inode link count. If Nginx or Java still holds that file descriptor open, the kernel keeps all disk blocks allocated until the process closes the FD or restarts.",
                table={
                    "headers": ["Case", "df -h", "df -i", "Root Cause & Fix"],
                    "rows": [
                        ["Log explosion", "100% Used", "15% Used", "Huge files (`du -sh * | sort -hr`) -> truncate/archive"],
                        ["Millions of tiny cache/session files", "42% Used", "100% IUse%", "Inode exhaustion (`df -i`) -> delete tiny temp files"],
                        ["Someone ran `rm big.log` while service running", "99% Used", "20% Used (`du` shows 40%)", "Deleted open file (`lsof +L1`) -> `truncate -s 0 /proc/<pid>/fd/<n>` or reload"],
                    ],
                },
                example="# Classic 'rm didn't free space' fix without killing PID:\n$ lsof +L1 | grep deleted\njava  1421 app  4w  REG 252,1 48G 10485 /var/log/app.log (deleted)\n$ : > /proc/1421/fd/4   # Zeroes open FD safely!",
            ),
            sec(
                "2. Block Storage Stack: Disk -> LVM -> Filesystem (`ext4` vs `xfs`)",
                "Production cloud disks (EBS/PD) sit behind block devices (`/dev/nvme0n1` or `/dev/vda`), optionally pooled via LVM or RAID before formatting with `mkfs.ext4` or `mkfs.xfs`.",
                table={
                    "headers": ["Filesystem / Layer", "Key Trait", "SRE Production Consideration"],
                    "rows": [
                        ["ext4", "General-purpose Linux default; online grow + offline shrink", "Safe default for OS root and medium mixed workloads"],
                        ["xfs", "64-bit high-throughput parallel I/O; online grow ONLY", "Great for Kafka logs/databases; cannot shrink later"],
                        ["LVM (PV -> VG -> LV)", "Pool multiple disks, online `lvextend -r`", "Zero-downtime volume expansion on VMs"],
                        ["RAID 1 / 10 / 5", "Mirror (1/10) vs Parity (5)", "Databases use RAID 10 for write IOPS + redundancy"],
                    ],
                },
            ),
        ],
        architecture="Block Device (/dev/vda) -> Partition/LVM (PV->VG->LV) -> ext4/xfs Superblock -> Mountpoint -> Directory -> Inode -> Data Blocks",
        commands=[
            {"cmd": "df -hT && df -i | head -n 8", "explain": "Check filesystem space (GB) AND inode exhaustion (%IUse)", "cwd": "/lab"},
            {"cmd": "du -sh /lab/* | sort -hr", "explain": "Rank directory sizes under /lab to find top disk consumers", "cwd": "/lab"},
            {"cmd": "stat /lab/linux/file1.txt", "explain": "Inspect inode number, link count, block allocation, and timestamps", "cwd": "/lab"},
            {"cmd": "mount | head -n 10", "explain": "Inspect active mounted filesystems, mount options (rw/ro/noexec), and types", "cwd": "/lab"},
        ],
        production_use_case="Preventing Kafka (`kafka_data`) and Prometheus TSDB outages caused by full disks, inode exhaustion, or orphaned Docker `overlay2` layers.",
        scenarios=[
            scenario(
                "Disk Full Alert After SRE Already Deleted the 30 GB Log File",
                "Prometheus alerts `NodeDiskRunningFull` (98%). An engineer deleted `/var/log/api.log`, yet `df -h` still reports 98% used!",
                "df -h /var/log && du -sh /var/log && lsof +L1 /var/log",
                "`api_server` still holds an open file descriptor to the unlinked `(deleted)` inode, preventing the kernel from reclaiming data blocks.",
                "Never use `rm` on an actively written giant log! Zero it via `truncate -s 0 <file>` (or `: > /proc/<pid>/fd/<fd>`) or reload the service to reopen a fresh log file (`logrotate copytruncate`).",
            ),
        ],
        troubleshooting=[
            "`No space left on device` when `df -h` shows 50% free -> immediately run `df -i` to check inode exhaustion.",
            "`Read-only file system` in dmesg -> kernel remounted disk `ro` due to storage/hardware errors; check `dmesg -T`.",
        ],
        interview_qa=[
            qa("What is an inode?", "An index node metadata structure storing file size, owner, permissions, timestamps, link count, and pointers to data blocks — everything except the filename and payload.", "basic"),
            qa("Difference between ext4 and xfs?", "XFS handles massive files and parallel multi-threaded I/O well and supports online growth (cannot shrink). ext4 supports both online growth and offline shrinking (`resize2fs`) and is a common OS default.", "basic"),
            qa("Why can `df -h` show 100% full when `du -sh /*` only totals 40%?", "A running process still holds an open file descriptor to a file that was deleted (`rm`). Because the link count > 0 in open FDs, the kernel hasn't freed those blocks. Find it via `lsof +L1`.", "senior"),
        ],
        assignment_items=[
            "Run df -hT and df -i and explain space vs inode exhaustion",
            "Find largest folders in /lab using du -sh | sort -hr",
            "Inspect an inode via stat and trace hard link vs soft link behavior",
            "Explain how to reclaim disk from a deleted-but-open file safely",
        ],
        revision=["df -h (blocks) + df -i (inodes)", "Inode holds metadata, dir holds name", "Deleted open FD = lsof +L1", "XFS cannot shrink; ext4 can offline"],
        interview_sim=[
            sim("A host reports 'No space left on device' while `df -h` shows 45 GB free (only 40% used). What is happening and how do you fix it?", ["Check df -i (100% IUse%)", "Locate directory with millions of tiny files (find /tmp /var/spool)", "Batch delete with find -delete"]),
            sim("Someone ran `rm -f /var/log/app.log` to free 50 GB, but `df -h` didn't drop by 1 MB. Walk through exact recovery steps without rebooting.", ["Explain open FD keeping inode blocks alive", "lsof +L1 or ls -l /proc/*/fd", "Truncate /proc/<pid>/fd/<n> or graceful reload"]),
            sim("Compare hard links vs symbolic links when you delete the original target file.", ["Hard link shares same inode (data stays until link count=0)", "Symlink becomes dangling broken pointer"]),
            sim("Why can you shrink an `ext4` volume offline, whereas `xfs` cannot shrink?", ["XFS metadata allocation architecture", "Must backup, recreate smaller XFS LV, and restore"]),
            sim("On an AWS/GCP Linux node, what is the sequence of commands to expand an attached 100 GB EBS/disk to 200 GB online?", ["Cloud resize volume -> lsblk / growpart", "pvresize -> lvextend -l +100%FREE", "resize2fs (ext4) or xfs_growfs (xfs)"]),
        ],
    ),

    make_day(
        day=7,
        phase=1,
        title="Linux Networking Utilities & Socket Inspection",
        subtitle="ip addr/route, ss vs netstat, curl timing vs wget, dig/nslookup & nc",
        goal="Inspect Linux interfaces, kernel routing, listening sockets, DNS records, and HTTP latency",
        objective=(
            "Replace legacy `ifconfig`/`netstat` with modern `ip` and `ss`, verify DNS over container bridges, "
            "and use `curl -w` timing + `nc` to isolate local bind bugs (`127.0.0.1` vs `0.0.0.0`) from firewall drops."
        ),
        concepts=[
            "`ss` queries kernel netlink socket tables directly (microseconds even with 100k sockets), replacing deprecated `/proc/net`-parsing `netstat`.",
            "Binding to `127.0.0.1:8000` accepts ONLY loopback traffic from inside the same container/host; binding to `0.0.0.0:8000` accepts traffic from external containers/LoadBalancers.",
            "`curl` supports HTTP verbs, headers, JSON payloads, and detailed per-phase timing (`-w`); `wget` focuses on recursive/resumable file downloads.",
            "`dig +short` / `dig +trace` exposes exact DNS A/CNAME records, TTLs, and upstream resolver latency.",
        ],
        deep_sections=[
            sec(
                "1. Socket & Connectivity Troubleshooting Triad (`ss`, `nc`, `curl -w`)",
                "When Service A cannot reach Service B on port 8000, checking these three layers in order isolates whether B is dead, bound to loopback only, blocked by firewall, or failing TLS.",
                table={
                    "headers": ["Test Result", "Kernel / Network Signal", "Immediate Fix"],
                    "rows": [
                        ["Connection refused (<1ms)", "Kernel sent TCP RST — nothing listening on IP:port", "Start service OR fix `127.0.0.1` -> `0.0.0.0` bind (`ss -tuln`)"],
                        ["Connection timed out (hanging)", "SYN sent, zero SYN-ACK/RST returned", "Security Group / NetworkPolicy / iptables DROP or wrong route"],
                        ["Could not resolve host", "DNS query failed against /etc/resolv.conf", "Check CoreDNS / Docker DNS / hostname typo"],
                    ],
                },
                example="$ ss -tulnp | grep 8000\ntcp  LISTEN 0  2048  0.0.0.0:8000  0.0.0.0:*  users:((\"uvicorn\",pid=1,fd=7))\n# Good: 0.0.0.0 accepts remote Docker/K8s traffic. 127.0.0.1 would block peers!",
            ),
        ],
        architecture="App Socket -> ss -tulnp (0.0.0.0 vs 127.0.0.1) -> ip route -> /etc/resolv.conf DNS -> nc/curl Peer Probe",
        commands=[
            {"cmd": "ip -br a && ip route", "explain": "Inspect container interfaces and kernel routing table", "cwd": "/lab"},
            {"cmd": "ss -tulnp", "explain": "List all listening TCP/UDP sockets and owning PIDs", "cwd": "/lab"},
            {"cmd": "dig +short kafka prometheus ai_agent", "explain": "Verify Docker Compose DNS resolution across the A³P stack", "cwd": "/lab"},
            {"cmd": "curl -sS -w 'http=%{http_code} dns=%{time_namelookup}s connect=%{time_connect}s ttfb=%{time_starttransfer}s total=%{time_total}s\\n' -o /dev/null http://ai_agent:8000/api/health", "explain": "Measure DNS, TCP connect, TTFB, and total HTTP latency to A³P AI Agent", "cwd": "/lab"},
        ],
        production_use_case="Validating `kafka:9092`, `prometheus:9090`, and `ai_agent:8000` reachability inside A³P and debugging `127.0.0.1` localhost bind mistakes in containers.",
        scenarios=[
            scenario(
                "Flask/Uvicorn Container Works via `curl localhost:8000` Inside Pod, Returns Connection Refused from Service!",
                "Healthcheck fails externally (`Connection refused`), yet running `curl localhost:8000` inside `docker exec` returns 200 OK.",
                "ss -tulnp | grep 8000",
                "`ss` reveals `127.0.0.1:8000` instead of `0.0.0.0:8000` — inside a container network namespace, loopback is unreachable from Docker bridge / Kubernetes Service endpoints.",
                "Start server bound to `0.0.0.0` (e.g. `uvicorn agent:app --host 0.0.0.0 --port 8000`) while keeping host port mapping bound safely to `127.0.0.1:8000:8000` in Compose if desired.",
            ),
        ],
        troubleshooting=[
            "`dig` shows NXDOMAIN inside container -> check `/etc/resolv.conf` (`127.0.0.11` in Docker, `10.96.0.10` in K8s).",
            "Mixing `ss` `-l` (listening) and `-a` (all including ESTABLISHED/TIME_WAIT) -> check `ss -s` for overall socket summary.",
        ],
        interview_qa=[
            qa("Difference between `ss` and `netstat`?", "`ss` reads netlink sockets directly from kernel space (fast even at 100k+ connections); `netstat` is legacy (`net-tools`) and parses `/proc/net` slowly.", "basic"),
            qa("Difference between `curl` and `wget`?", "`curl` is a versatile multi-protocol client (HTTP POST/PUT, custom headers, `-w` timing, stdout by default); `wget` is a HTTP/FTP downloader built for recursive mirroring and background retries.", "basic"),
            qa("How do `Connection refused` vs `Connection timed out` differ at the TCP packet level?", "`Connection refused` means the target host/firewall answered immediately with a TCP `RST` (no process listening on that port). `Connection timed out` means `SYN` packets received neither `SYN-ACK` nor `RST` (silent firewall drop or blackhole route).", "senior"),
        ],
        assignment_items=[
            "Inspect interfaces and default gateway via ip -br a and ip route",
            "Verify listening socket bindings (0.0.0.0 vs 127.0.0.1) using ss -tulnp",
            "Resolve internal A³P services with dig +short",
            "Measure DNS vs TCP connect vs TTFB timing using curl -w",
        ],
        revision=["ss -tulnp > netstat", "0.0.0.0 listens externally; 127.0.0.1 loopback only", "RST = refused, silent drop = timeout", "curl -w separates network vs app latency"],
        interview_sim=[
            sim("A service responds `200 OK` to `curl 127.0.0.1:8080` from inside the host, but Kubernetes LoadBalancer / peer containers get `Connection refused`. What is the exact cause and command to prove it?", ["ss -tulnp showing 127.0.0.1:8080", "Rebind server to 0.0.0.0:8080"]),
            sim("Compare `curl -w` timings: `time_namelookup=0.002s`, `time_connect=0.004s`, `time_starttransfer=4.85s`. Is this a DNS, network, or application/DB latency issue?", ["DNS + TCP 3-way handshake finished in 4ms", "4.84s TTFB is inside backend app/DB processing"]),
            sim("How do `ip link`, `ip addr`, and `ip route` replace `ifconfig` and `route`?", ["iproute2 modern netlink suite", "Check multiple IPs/namespaces/policy routing"]),
            sim("When running `ss -tan state time-wait`, you see 15,000 `TIME_WAIT` sockets on an API gateway. Why does `TIME_WAIT` exist and how do you reduce it?", ["2*MSL waits for delayed packets on closed TCP tuple", "Enable HTTP keep-alive / connection pooling upstream"]),
            sim("Explain what `dig +trace example.com` does compared to `cat /etc/hosts`.", ["Iterative trace Root -> TLD -> Authoritative NS", "/etc/hosts local static override checked per /etc/nsswitch.conf"]),
        ],
    ),

    make_day(
        day=8,
        phase=1,
        title="Bash Shell Scripting, Cron & Toil Automation",
        subtitle="Strict Mode (set -euo pipefail), Loops, Functions, \"$@\" vs \"$*\", Exit Codes & Cron",
        goal="Author production-safe Bash automation that fails fast, logs clearly, and eliminates SRE toil",
        objective=(
            "Write defensive Bash scripts suitable for production cron/CI pipelines: understand `set -euo pipefail`, exit codes (`$?`), "
            "argument quoting (`\"$@\"` vs `\"$*\"`), and classic cron outage traps (`PATH`, overlapping runs via `flock`)."
        ),
        concepts=[
            "`set -euo pipefail`: `-e` exits immediately on non-zero return, `-u` aborts on unset variables (prevents `rm -rf /$UNSET`), `-o pipefail` propagates failures inside `cmd1 | cmd2`.",
            "`\"$@\"` expands each positional argument as an intact quoted word (`\"a b\" \"c\"`); `\"$*\"` merges all arguments into one string joined by `$IFS`.",
            "Exit code `0` = success; `1-255` = error (`$?` inspects previous exit status; `trap cleanup EXIT` guarantees temp-file cleanup).",
            "Cron runs in a minimal non-interactive environment (`PATH=/usr/bin:/bin`, no `.bashrc`) — always set explicit `PATH`, redirect output, and wrap long jobs with `flock` to prevent stampedes.",
        ],
        deep_sections=[
            sec(
                "1. Why `set -euo pipefail` Prevents Production Disasters",
                "Default Bash silently ignores unset variables and pipeline failures: `tar czf /backup.tgz /data | gzip` masks a `tar` error because `gzip` returns 0. Production SRE scripts must fail loudly.",
                example="#!/usr/bin/env bash\nset -euo pipefail\ntrap 'echo \"Failed at line $LINENO\" >&2' ERR\n\ncheck_url() {\n  local url=\"$1\"\n  curl -fsS --max-time 3 \"$url\" >/dev/null\n}\nfor svc in \"$@\"; do check_url \"$svc\"; done",
            ),
            sec(
                "2. `\"$@\"` vs `\"$*\"` & Crontab Safety Checklist",
                "Quoting differences break scripts whenever filenames or commit messages contain spaces.",
                table={
                    "headers": ["Syntax", "Given args: `\"prod logs\" \"day 8\"`", "Result"],
                    "rows": [
                        ["for x in \"$@\"", "2 iterations", "`x='prod logs'`, `x='day 8'` (SAFE!)"],
                        ["for x in \"$*\"", "1 iteration", "`x='prod logs day 8'` (broken word merge)"],
                        ["for x in $@ (unquoted!)", "4 iterations", "`prod`, `logs`, `day`, `8` (word-splitting bug)"],
                    ],
                },
            ),
        ],
        architecture="Cron/CI Trigger (flock + PATH) -> #!/usr/bin/env bash (set -euo pipefail) -> Function Loop ($@) -> Exit Code ($?)",
        commands=[
            {"cmd": "cat /lab/linux/Scripts/health_check.sh", "explain": "Inspect the A³P Practice Lab health-check Bash script", "cwd": "/lab/linux"},
            {"cmd": "bash /lab/linux/Scripts/health_check.sh", "explain": "Run live multi-service HTTP probe loop across data_generator, Prometheus & ai_agent", "cwd": "/lab/linux"},
            {"cmd": "bash -c 'set -euo pipefail; demo() { for a in \"$@\"; do echo \"[$a]\"; done; }; demo \"nginx error\" \"db timeout\"'", "explain": "Verify \"$@\" preserves quoted multi-word arguments", "cwd": "/lab/linux"},
            {"cmd": "bash -c 'false | true; echo \"no_pipefail=$?\"; set -o pipefail; false | true || echo \"with_pipefail=$?\"'", "explain": "Demonstrate how pipefail catches hidden left-side pipeline errors", "cwd": "/lab/linux"},
        ],
        production_use_case="Replacing manual curl/restart toil with idempotent scripts tracked in the A³P Toil Automation ledger.",
        scenarios=[
            scenario(
                "Script Works Manually in Terminal, Fails Silently Every Night in Cron",
                "An engineer runs `/opt/scripts/k8s_backup.sh` manually and it succeeds; scheduled at `02:00` in `crontab`, it produces empty backups.",
                "grep CRON /var/log/syslog ; env -i /bin/sh -c '/opt/scripts/k8s_backup.sh'",
                "Cron sets minimal `PATH=/usr/bin:/bin` (missing `/usr/local/bin/kubectl` or `aws`), doesn't source `~/.bashrc` env vars, and had no `2>&1` logging.",
                "Declare explicit `PATH=...` at top of script/crontab, use `set -euo pipefail`, log stdout+stderr with timestamps, and wrap with `flock -n /tmp/backup.lock`.",
            ),
        ],
        troubleshooting=[
            "`if [ $VAR = \"ok\" ]` fails with `unary operator expected` when `$VAR` is empty -> always double-quote `[[ \"$VAR\" == \"ok\" ]]`.",
            "Two overlapping hourly cron jobs corrupt output -> protect with `flock -n /var/lock/job.lock`.",
        ],
        interview_qa=[
            qa("Difference between `\"$@\"` and `\"$*\"`?", "When double-quoted, `\"$@\"` preserves each positional argument as an independent word (`N` args stay `N` items); `\"$*\"` joins all arguments into one single string using the first character of `IFS`.", "basic"),
            qa("What are Linux exit codes and what do 0, 1, 126, 127, 137, 143 mean?", "8-bit status values (`0-255`) returned by processes (`$?`): `0`=success, `1`=general error, `126`=not executable/perm denied, `127`=command not found, `137`=`128+9` SIGKILL/OOM, `143`=`128+15` SIGTERM.", "basic"),
            qa("Why does a backup script run fine interactively yet fail in `crontab`?", "Cron runs with minimal `PATH`, no interactive `.bashrc` exports, different working directory (`$HOME`), and `%` characters in crontab lines require escaping (`\\%`) because `%` means newline/stdin in cron.", "senior"),
        ],
        assignment_items=[
            "Read and execute /lab/linux/Scripts/health_check.sh",
            "Write a script with set -euo pipefail and trap cleanup",
            "Demonstrate \"$@\" vs \"$*\" and pipefail behavior",
            "List 4 reasons scripts break in cron vs interactive shells",
        ],
        revision=["set -euo pipefail", "\"$@\" preserves quoted args", "127=not found, 137=SIGKILL, 143=SIGTERM", "Cron: explicit PATH + flock"],
        interview_sim=[
            sim("In `backup.sh`, `pg_dump prod | gzip > /backups/db.sql.gz` exited 0 even though `pg_dump` failed with authentication error, causing empty backups for a week. Why?", ["Without set -o pipefail, pipeline returns exit code of last command (gzip=0)", "Always set -euo pipefail + verify non-empty artifact size"]),
            sim("How do you prevent a 5-minute cron job from overlapping itself if one run stalls for 12 minutes?", ["flock -n /var/lock/myjob.lock /path/to/script.sh", "Add timeout wrapper + alert on lock contention"]),
            sim("Why is `rm -rf $BUILD_DIR/*` dangerous without `set -u` or `${BUILD_DIR:?}`?", ["If BUILD_DIR is unset/empty, command expands to rm -rf /*", "Use set -u and parameter expansion ${BUILD_DIR:?missing}"]),
            sim("Explain `local`, `export`, and `$?` inside a Bash function.", ["local scopes variable to function", "export shares with child processes", "$? captures immediate previous command exit status"]),
            sim("When should SREs stop writing Bash and switch to Python/Go?", [">100 lines, complex JSON/API parsing, retries/concurrency, structured testing needs"]),
        ],
    ),

    make_day(
        day=9,
        phase=1,
        title="Systemd, Unit Files, Journalctl & Service Lifecycle",
        subtitle="[Unit]/[Service]/[Install], systemctl vs service, journalctl & Container PID 1",
        goal="Design resilient systemd units, debug boot/restart failures with journalctl, and map to container PID 1",
        objective=(
            "Understand how systemd acts as PID 1 on Linux VMs/nodes (`kubelet`, `containerd`, `nginx`, `prometheus`), "
            "how `[Unit]` ordering, `ExecStartPre` guards, and `Restart=on-failure` work, and how `journalctl` filters structured logs."
        ),
        concepts=[
            "Systemd is PID 1 on modern Linux distributions, replacing sequential SysVinit scripts with dependency-driven parallel startup and per-service cgroup isolation.",
            "A `.service` unit has 3 sections: `[Unit]` (`After=network-online.target`, `Requires=`/`Wants=`), `[Service]` (`User=`, `ExecStartPre=`, `ExecStart=`, `Restart=on-failure`, `LimitNOFILE=`), `[Install]` (`WantedBy=multi-user.target`).",
            "`journalctl` reads binary indexed logs from `systemd-journald`: filter by unit (`-u nginx`), boot (`-b -1` for previous crash boot!), priority (`-p err`), or window (`--since '10 min ago'`).",
            "Containers typically skip systemd and run the single daemon directly at PID 1 (`uvicorn`, `nginx -g 'daemon off;'`), while the underlying OrbStack VM/K8s nodes run systemd!",
        ],
        deep_sections=[
            sec(
                "1. Anatomy of a Production Systemd Unit File",
                "Putting `ExecStartPre` validation inside a systemd unit prevents a broken config reload from taking down a healthy daemon.",
                example="[Unit]\nDescription=Aariz Advance AI platform Nginx Proxy\nAfter=network-online.target\nWants=network-online.target\n\n[Service]\nType=simple\nUser=www-data\nExecStartPre=/usr/sbin/nginx -t\nExecStart=/usr/sbin/nginx -g 'daemon off;'\nExecReload=/bin/kill -s HUP $MAINPID\nRestart=on-failure\nRestartSec=5s\nLimitNOFILE=65536\n\n[Install]\nWantedBy=multi-user.target",
                sre_example="Remember `StartLimitBurst=5` / `StartLimitIntervalSec=10`: if a misconfigured daemon crashes 5 times within 10s, systemd stops restarting and puts the unit in `failed` state until you fix the config and run `systemctl reset-failed`.",
            ),
        ],
        architecture="PID 1 systemd -> [Unit] After/Wants -> ExecStartPre (syntax check) -> ExecStart -> cgroup slice -> journald",
        commands=[
            {"cmd": "ps -p 1 -o pid,ppid,comm,args", "explain": "Inspect PID 1 inside this container (entrypoint vs VM systemd)", "cwd": "/lab"},
            {"cmd": "nginx -t -c /lab/nginx-demo/nginx.conf", "explain": "Simulate systemd ExecStartPre config syntax check before reload", "cwd": "/lab"},
            {"cmd": "cat /lab/nginx-demo/nginx.conf", "explain": "Inspect reverse proxy config managed by daemon lifecycle", "cwd": "/lab"},
        ],
        production_use_case="Managing `kubelet`, `dockerd`/`containerd`, `node_exporter`, and `nginx` on cloud VMs, and validating configs before reload.",
        scenarios=[
            scenario(
                "Kubelet Fails Every Reboot After Kernel Upgrade (`Too many open files` / Cgroup Swap Error)",
                "A Kubernetes worker node shows `NotReady` in `kubectl get nodes`; SSHing onto the node shows `systemctl is-active kubelet` -> `activating (auto-restart)`.",
                "systemctl status kubelet --no-pager ; journalctl -u kubelet -n 50 --no-pager ; journalctl -b -1 -p err",
                "`journalctl -u kubelet` reveals `running with swap on is not supported` or low `LimitNOFILE`, and editing `/etc/systemd/system/kubelet.service.d/10-kubeadm.conf` wasn't followed by `systemctl daemon-reload`.",
                "Run `systemctl daemon-reload && systemctl restart kubelet`, verify with `journalctl -u kubelet -f`, and persist `swapoff -a` / limits in Ansible/cloud-init.",
            ),
        ],
        troubleshooting=[
            "Edited a `.service` file and `systemctl restart` didn't pick it up -> forgot `systemctl daemon-reload`!",
            "`journalctl` logs from before crash missing -> enable `Storage=persistent` in `/etc/systemd/journald.conf`.",
        ],
        interview_qa=[
            qa("Difference between `service` and `systemctl`?", "`service` is a legacy SysVinit wrapper script; `systemctl` is the native systemd CLI managing parallel dependency units, cgroups, journal integration, and socket activation.", "basic"),
            qa("What happens when you change a `.service` file vs a daemon's own config file?", "Changing a daemon config (`nginx.conf`) only requires `systemctl reload/restart nginx` (and config check). Changing a `.service` unit file requires `systemctl daemon-reload` so systemd re-parses the unit definition first.", "senior"),
            qa("How do you inspect logs from a server that unexpectedly rebooted 5 minutes ago?", "Run `journalctl -b -1 -p err` (`-b -1` shows the previous boot's journal logs, provided persistent `/var/log/journal` is enabled).", "senior"),
        ],
        assignment_items=[
            "Explain [Unit], [Service], and [Install] sections with ExecStartPre and Restart=on-failure",
            "Distinguish systemctl daemon-reload vs reload vs restart",
            "Filter logs mentally/practically using journalctl -u, --since, -p err, and -b -1",
            "Explain why Docker containers run the app binary at PID 1 instead of systemd",
        ],
        revision=["daemon-reload after unit edits", "ExecStartPre validates config safely", "journalctl -b -1 checks prior crash", "Containers run app directly as PID 1"],
        interview_sim=[
            sim("You edit `/etc/systemd/system/prometheus.service` to add `--storage.tsdb.retention.time=30d`, run `systemctl restart prometheus`, and Prometheus still uses 15d retention. Why?", ["Forgot systemctl daemon-reload", "Systemd warns 'unit file changed on disk'"]),
            sim("What is the difference between `Requires=` and `Wants=` in a systemd `[Unit]` section?", ["Requires fails/stops the unit if dependency fails", "Wants starts dependency best-effort without tearing down main unit"]),
            sim("How can a runaway journald log fill `/var/log` and how do you cap it safely?", ["Set SystemMaxUse=500M in /etc/systemd/journald.conf", "journalctl --vacuum-size=200M"]),
            sim("Why did `nginx` container exit immediately (`Exited (0)`) when you ran `CMD [\"nginx\"]` in a Dockerfile?", ["Default nginx forks daemon into background; PID 1 exits so container stops", "Use `daemon off;`"]),
            sim("Explain `Restart=always` vs `Restart=on-failure` and `StartLimitBurst`.", ["always restarts even on exit 0; on-failure only on non-zero/signal", "StartLimitBurst caps crash loops"]),
        ],
    ),

    make_day(
        day=10,
        phase=1,
        title="Phase 1 Capstone: Linux Production Troubleshooting",
        subtitle="USE Method Triage: CPU 100%, Memory Leak, Disk/Inode Full, I/O Wait & Permissions",
        goal="Execute a disciplined, evidence-first Linux incident triage sequence without guessing or rebooting blindly",
        objective=(
            "Combine Days 1–9 into Brendan Gregg's **USE Method** (Utilization, Saturation, Errors across CPU, Memory, Disk, Network) "
            "plus log extraction (`grep`/`awk`/`sed`) and live chaos triage inside Aariz Advance AI platform (A³P)."
        ),
        concepts=[
            "USE Method checks **Utilization** (% busy), **Saturation** (queue length / wait), and **Errors** (drops/OOM/hardware errs) for every resource: CPU, Memory, Disk, Network.",
            "Golden 60-second Linux triage sequence: 1) `uptime` -> 2) `dmesg -T | tail` -> 3) `vmstat 1` -> 4) `mpstat -P ALL 1` -> 5) `pidstat 1` / `ps --sort` -> 6) `iostat -xz 1` -> 7) `free -m` -> 8) `ss -s`.",
            "Never restart or reboot BEFORE capturing `/var/log`, `ps`, `free`, `ss`, and `df` evidence — otherwise the root cause vanishes and the incident repeats.",
        ],
        deep_sections=[
            sec(
                "1. 60-Second Incident Triage Playbook (Which Tool Isolates What)",
                "During an active SEV-1 alert, running commands randomly wastes critical minutes. Follow this deterministic elimination tree:",
                table={
                    "headers": ["Symptom Reported", "First 2 Commands", "Key Clue to Confirm Root Cause"],
                    "rows": [
                        ["Server slow + CPU 100%", "uptime && ps aux --sort=-%cpu | head", "Single runaway PID (`%us=99%`) vs kernel (`%sy`) vs hypervisor steal (`%st`)"],
                        ["Server slow + Low CPU", "vmstat 1 3 && iostat -xz 1 2", "High `%wa` + `await > 50ms` + `D` state PIDs -> Disk/NFS bottleneck"],
                        ["Random worker crashes", "free -m && dmesg -T | grep -i oom", "Exit code `137`, low `available`, `oom-killer` logs"],
                        ["Writes failing / app read-only", "df -hT && df -i && lsof +L1", "`100%` disk, `100% IUse%`, or deleted open file handle"],
                    ],
                },
            ),
        ],
        architecture="Alert -> Capture Evidence (uptime/free/df/vmstat/ps/ss) -> Isolate Resource (CPU/RAM/Disk/Net) -> Mitigate -> Postmortem",
        commands=[
            {"cmd": "uptime && free -m && df -h /lab && df -i /lab && ps aux --sort=-%mem | head -n 6", "explain": "Run one-shot SRE Linux triage bundle on /lab", "cwd": "/lab"},
            {"cmd": "grep -i 'ERROR' /lab/linux/Logs/app.log | awk '{print $1, $3, $5}'", "explain": "Filter ERROR events and extract timestamp, service, and latency via awk", "cwd": "/lab"},
            {"cmd": "ss -tulnp && ls -ld /tmp /lab/linux/Scripts/health_check.sh", "explain": "Audit open listening ports and critical file permissions", "cwd": "/lab"},
        ],
        production_use_case="Triggers cleanly alongside A³P Chaos Lab scenarios (`cpu_spike`, `memory_leak`, `db_timeout`) while Grafana & Prometheus track live saturation.",
        scenarios=[
            scenario(
                "Multi-Symptom Production Outage: High Latency, Intermittent 502s & Failing Cron Jobs",
                "Users report slow checkouts (`p99 > 2s`), Nginx logs upstream timeouts, and nightly cleanup cron didn't write output.",
                "uptime && free -m && df -h && df -i && vmstat 1 3 && ss -s",
                "Diagnosing systematically proves root cause (e.g., disk full halting DB WAL writes + `D`-state blocking app workers) rather than blindly restarting Nginx.",
                "Capture logs and process snapshots first, clear/expand bottleneck safely, verify metrics recover in A³P, and publish a blameless postmortem.",
            ),
        ],
        troubleshooting=[
            "Restarting a service immediately erases memory dumps, open socket tables (`ss`), and ephemeral `/tmp` locks — always capture telemetry first.",
        ],
        interview_qa=[
            qa("A server is very slow yet `top` shows CPU usage under 10%. Walk through your investigation.", "Check Load Average vs `nproc`, look at `%wa` (I/O wait) and `vmstat` `b`/`si`/`so` columns, run `iostat -xz 1` for disk saturation/await, check `df -h`/`df -i`, and check `ss -s`/packet drops + downstream DB lock latency.", "senior"),
            qa("What are the top 5 commands you run in the first 60 seconds on an unfamiliar degraded Linux host?", "`uptime`, `dmesg -T | tail`, `free -m`, `vmstat 1 3`, and `df -hT` (followed by `ps aux --sort=-%cpu/-%mem` and `iostat -xz 1`).", "senior"),
        ],
        assignment_items=[
            "Run the one-shot Linux triage bundle in /lab and explain every column",
            "Inject cpu_spike in Chaos Lab and watch live Prometheus CPU metrics react",
            "Parse /lab/linux/Logs/app.log using grep + awk to isolate slow/error requests",
            "Explain Brendan Gregg's USE method across CPU, RAM, Disk, and Network",
        ],
        revision=["USE = Utilization, Saturation, Errors", "Capture evidence BEFORE restart", "Low CPU + slow box = I/O, swap, net, or lock"],
        interview_sim=[
            sim("Walk through the exact 60-second USE-method checklist when paged for 'checkout-api host sluggish, p99 latency 4.5s'.", ["uptime (load vs nproc)", "vmstat 1 (r, b, si/so, wa)", "free -m (available)", "iostat -xz & df -h/i", "ss -s & app/dmesg logs"]),
            sim("How does CPU Steal (`%st` in `top`) happen on cloud VMs and what is the only fix?", ["Hypervisor noisy neighbor throttling vCPU", "Migrate/recreate instance on another host or dedicated CPU tier"]),
            sim("You discover 30 GB of deleted open logs holding `/var` at 100%. Why shouldn't you kill -9 the Java service immediately?", ["kill -9 drops in-flight transactions & corrupts state", "Use : > /proc/<pid>/fd/<n> or graceful drain + reload"]),
            sim("What awk pipeline extracts top 5 error endpoints from an access log?", ["grep ' 50[0-9] ' access.log | awk '{print $7}' | sort | uniq -c | sort -nr | head -5"]),
            sim("Connect Linux cgroups/namespaces to Docker/Kubernetes container outages.", ["Namespaces isolate view (PID/NET/MNT)", "Cgroups enforce CPU throttling (CFS) and OOMKill (137)"]),
        ],
    ),
]

