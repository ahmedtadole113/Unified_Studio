"""Phase 4 (Days 19-22): Docker Architecture, Dockerfiles, Networking, Volumes & Compose."""

from typing import Dict, List
from .common import make_day, qa, scenario, sec, sim

DAYS_19_TO_22: List[Dict] = [
    make_day(
        day=19,
        phase=4,
        title="Docker Architecture, Namespaces, Cgroups & Layers",
        subtitle="dockerd -> containerd -> runc, Linux Isolation Primitives, UnionFS & Container Exit Codes",
        goal="Understand container internals under the hood and diagnose container exits on OrbStack",
        objective=(
            "Demystify containers: see how Docker uses Linux kernel Namespaces (visibility isolation) and Cgroups (CPU/RAM quotas) "
            "instead of virtualizing hardware, and read Copy-on-Write image layers + container exit codes (`0`, `1`, `137`, `143`)."
        ),
        concepts=[
            "Containers share the host Linux kernel (in OrbStack's optimized Linux VM on macOS) — booting in milliseconds vs minutes for guest-OS VMs.",
            "**Namespaces** isolate what a process can *see*: `PID` (own process tree), `NET` (own eth0/IP/ports), `MNT` (rootfs), `UTS` (hostname), `IPC`, `USER`.",
            "**Cgroups (v2)** limit what a process can *consume*: CPU shares/quota (`cpu.max`), memory limits (`memory.max` -> OOMKill on breach), IOPS.",
            "Docker daemon pipeline: `docker CLI` -> `dockerd` -> `containerd` -> `containerd-shim` -> `runc` (OCI runtime spawns container process).",
        ],
        deep_sections=[
            sec(
                "1. VM vs Docker Container & Linux Kernel Building Blocks",
                "Knowing that a container IS just a sandboxed Linux process on the host kernel lets you debug it with `ps`, `ss`, and `docker stats` directly.",
                table={
                    "headers": ["Dimension", "Virtual Machine (VM)", "Docker / OCI Container"],
                    "rows": [
                        ["Isolation Boundary", "Hypervisor + separate Guest OS Kernel", "Host Kernel via Namespaces + Cgroups + Seccomp"],
                        ["Boot Time / Footprint", "30–120s, GBs of RAM/disk", "< 1 second, 10–100s MBs (shared read-only image layers)"],
                        ["Failure Blast Radius", "Stronger hypervisor hardware boundary", "Kernel bug affects host; harden via non-root + seccomp + capabilities drop"],
                    ],
                },
                example="# Quick Exit Code Reference:\nExit 0   -> Clean exit (or backgrounded daemon PID 1 exited)\nExit 1   -> Application unhandled exception / config missing\nExit 127 -> Entrypoint/binary missing inside $PATH\nExit 137 -> SIGKILL (128+9): almost always cgroup OOMKilled!\nExit 143 -> SIGTERM (128+15): graceful stop signal received",
            ),
        ],
        architecture="Docker CLI -> dockerd (/var/run/docker.sock) -> containerd -> runc -> Linux Namespaces + Cgroups + OverlayFS",
        commands=[
            {"cmd": "docker ps --format 'table {{.Names}}\\t{{.Status}}\\t{{.Ports}}'", "explain": "Inspect all 10 running A³P containers on OrbStack", "cwd": "/lab/docker-demo"},
            {"cmd": "docker images --format 'table {{.Repository}}:{{.Tag}}\\t{{.Size}}'", "explain": "List local Docker images and disk footprint", "cwd": "/lab/docker-demo"},
            {"cmd": "docker stats --no-stream --format 'table {{.Name}}\\t{{.CPUPerc}}\\t{{.MemUsage}}\\t{{.MemPerc}}'", "explain": "Snapshot live cgroup CPU and memory utilization across stack", "cwd": "/lab/docker-demo"},
        ],
        production_use_case="Every A³P service runs with pinned cgroup CPU & RAM bounds inside `docker-compose.yml` so Spark/Kafka stay under 8 GB on OrbStack.",
        scenarios=[
            scenario(
                "Spark Worker Container Silenced Mid-Job (`Exited (137)`)",
                "`docker ps -a` shows `aiops_spark_worker Exited (137) 10 seconds ago` during heavy Kafka streaming.",
                "docker inspect aiops_spark_worker --format 'OOMKilled={{.State.OOMKilled}} Exit={{.State.ExitCode}}' && docker logs --tail 25 aiops_spark_worker",
                "JVM heap + PySpark worker off-heap exceeded the container's cgroup memory cap (`mem_limit`), triggering kernel OOMKill (`Exit 137`).",
                "Raise container `memory: 1536M` and explicitly cap `SPARK_EXECUTOR_MEMORY=1g` below cgroup headroom.",
            ),
        ],
        troubleshooting=["Container keeps restarting (`Restarting (1)`) -> check `docker logs --tail 40 <name>` and `docker inspect` `.State.OOMKilled`."],
        interview_qa=[
            qa("Compare a VM vs a Docker container.", "A VM virtualizes physical hardware and boots a full independent guest OS kernel via a hypervisor (heavy GBs, slower boot). A Docker container shares the host OS kernel using Linux Namespaces (isolation) and Cgroups (resource caps), starting in milliseconds.", "basic"),
            qa("Explain what happens under the hood when you run `docker run nginx`.", "CLI calls `dockerd` REST API -> `dockerd` asks `containerd` to pull OCI manifest & unpack read-only OverlayFS layers + RW upperdir -> `runc` creates Linux namespaces, applies cgroup limits, pivots root (`pivot_root`), drops capabilities, and executes Nginx.", "senior"),
        ],
        assignment_items=[
            "Run docker ps, docker images, and docker stats --no-stream on A³P",
            "Explain Linux Namespaces vs Cgroups and VM vs Container",
            "Identify container exit codes 0, 1, 127, 137, and 143",
        ],
        revision=["Namespaces = view isolation; Cgroups = resource limits", "OverlayFS = immutable RO layers + thin RW top", "Exit 137 = OOMKill"],
        interview_sim=[
            sim("What is the exact role of `dockerd`, `containerd`, `containerd-shim`, and `runc`?", ["dockerd = high-level API/build/network", "containerd = image & lifecycle daemon", "shim = decouples container PID 1 from containerd restarts", "runc = OCI low-level namespace/cgroup spawner"]),
            sim("If containers share the host kernel, can you run a Windows container natively on a Linux kernel without virtualization?", ["No — container binaries invoke host OS kernel syscalls directly; must match kernel ABI"]),
            sim("How does Docker's Overlay2 Copy-on-Write filesystem affect a container that writes 5 GB of temp logs inside `/`?", ["Writes go into ephemeral container upperdir; lost on rm, bloats host /var/lib/docker"]),
            sim("How do you see real-time cgroup memory limit vs usage without `docker stats` inside a container?", ["Read /sys/fs/cgroup/memory.max & memory.current (cgroup v2)"]),
            sim("Why is mounting `/var/run/docker.sock` inside an untrusted container equivalent to giving it root on the host?", ["Docker socket lets any caller launch `--privileged -v /:/host` containers"]),
        ],
    ),

    make_day(
        day=20,
        phase=4,
        title="Dockerfiles, Layer Caching, Multi-Stage Builds & Security",
        subtitle="Optimal Layer Ordering, Multi-Stage Slimming, COPY vs ADD, CMD vs ENTRYPOINT & Non-Root USER",
        goal="Build fast-cached, minimal-CVE, non-root production Docker images",
        objective=(
            "Eliminate bloated 1 GB images and broken builds: structure `Dockerfile` layers so dependency caches hit cleanly, "
            "strip compilers using multi-stage builds, understand `COPY` vs `ADD` and `CMD` vs `ENTRYPOINT`, and drop root."
        ),
        concepts=[
            "Docker caches each instruction layer sequentially: if `COPY . .` runs BEFORE `pip install -r requirements.txt`, editing 1 Python line invalidates the entire dependency install cache!",
            "**Multi-stage builds** (`FROM python:3.9 AS builder` -> `COPY --from=builder`) leave compilers (`gcc`, Maven, npm caches) behind, cutting image size & CVEs by 60–90%.",
            "`COPY` copies local files predictably (preferred); `ADD` also fetches remote URLs and auto-unpacks tarballs (unexpected behavior risk).",
            "`ENTRYPOINT` defines the fixed executable (`[\"python3\"]`); `CMD` supplies default overridable arguments (`[\"app.py\"]`). Together: `python3 app.py`.",
        ],
        deep_sections=[
            sec(
                "1. Optimal Production Multi-Stage Python/Go Dockerfile Pattern",
                "Notice how placing `.dockerignore`, copying `requirements.txt` first, running as `appuser`, and using multi-stage slim images gives 2-second rebuilds and clean security scans.",
                example="# Stage 1: Builder\nFROM python:3.11-slim AS builder\nWORKDIR /wheels\nCOPY requirements.txt .\nRUN pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt\n\n# Stage 2: Minimal Runtime\nFROM python:3.11-slim\nRUN useradd -r -u 1001 appuser\nWORKDIR /app\nCOPY --from=builder /wheels /wheels\nRUN pip install --no-cache-dir /wheels/* && rm -rf /wheels\nCOPY --chown=1001:1001 . .\nUSER 1001\nENTRYPOINT [\"uvicorn\", \"agent:app\"]\nCMD [\"--host\", \"0.0.0.0\", \"--port\", \"8000\"]",
            ),
        ],
        architecture="Deps Copy (Cached Layer) -> Multi-Stage Compile -> Minimal Slim/Distroless + Non-Root USER -> Immutable Digest",
        commands=[
            {"cmd": "cat /lab/docker-demo/Dockerfile", "explain": "Inspect the pre-seeded non-root Python Dockerfile in /lab/docker-demo", "cwd": "/lab/docker-demo"},
            {"cmd": "docker build -t sre-practice-app:v1 . && docker history sre-practice-app:v1", "explain": "Build image on OrbStack and inspect individual layer sizes", "cwd": "/lab/docker-demo"},
            {"cmd": "docker run --rm sre-practice-app:v1 id", "explain": "Override default CMD safely to verify container runs as non-root appuser", "cwd": "/lab/docker-demo"},
        ],
        production_use_case="Rebuilding `aiops_agent` during our session took ~2 seconds because `requirements.txt` was copied and cached before `COPY . .`!",
        scenarios=[
            scenario(
                "Image Build Ballooned to 2.4 GB and Accidentally Baked `.git` & `.env` Secrets Inside!",
                "Trivy fails CI with CRITICAL CVEs and a developer finds `.env` inside the container image filesystem.",
                "docker history <image> ; docker run --rm <image> ls -la /app",
                "Missing `.dockerignore` caused `COPY . .` to upload `.git/`, `.venv/`, and `.env` into the Docker build context and bake them permanently into an immutable image layer!",
                "Add `.dockerignore` (`.env`, `.git`, `*.pyc`, `sre_data/`, `.venv/`), switch to multi-stage slim, rotate any exposed secret, and rebuild.",
            ),
        ],
        troubleshooting=["Deleting a file in a later `RUN rm /app/secret` step does NOT remove it from the earlier image layer (`docker history` / `tar` still contains it!)."],
        interview_qa=[
            qa("Difference between `COPY` and `ADD`, and between `CMD` and `ENTRYPOINT`?", "`COPY` only copies local build-context files (explicit, safe). `ADD` additionally downloads URLs and auto-extracts tar archives. `ENTRYPOINT` locks the main binary executable; `CMD` provides default arguments that `docker run <image> <args>` overrides cleanly.", "basic"),
            qa("Why does deleting a temporary credential in a subsequent `RUN rm` Dockerfile instruction NOT protect the image?", "Every `RUN`/`COPY` creates an immutable layer cached in the image manifest. Even if a later layer whiteouts/deletes the file, anyone pulling the image can inspect the earlier layer tarball and recover the secret. Always use `--mount=type=secret` (BuildKit) or multi-stage builds.", "senior"),
        ],
        assignment_items=[
            "Build sre-practice-app:v1 in /lab/docker-demo and inspect docker history",
            "Verify non-root user with docker run --rm sre-practice-app:v1 id",
            "Explain .dockerignore, layer cache ordering, and why multi-stage removes CVEs",
        ],
        revision=["Copy requirements BEFORE code", "Multi-stage strips build compilers", "Always include .dockerignore", "COPY > ADD; non-root USER"],
        interview_sim=[
            sim("A Go/Python build compiles code in `FROM ubuntu:22.04` and produces a 950 MB image with `gcc` and `curl` flagged by Trivy. How do you shrink it under 50 MB cleanly?", ["Multi-stage build (builder -> distroless/alpine/slim)", "Copy compiled binary or wheels only"]),
            sim("Why does `RUN apt-get update` on one line and `RUN apt-get install -y curl` on the next line break future Docker builds?", ["Apt package index cache gets stale in layer 1 when new package is added in layer 2; combine with `&& rm -rf /var/lib/apt/lists/*`"]),
            sim("What happens when someone writes `ENTRYPOINT python app.py` (shell form) vs `ENTRYPOINT [\"python\", \"app.py\"]` (exec form)?", ["Shell form wraps in `/bin/sh -c`, stealing PID 1 and blocking SIGTERM signals"]),
            sim("How does Docker BuildKit `--mount=type=secret` prevent API keys from leaking into image layers during `pip install` from a private registry?", ["Mounts secret tmpfs only during that single RUN step without persisting into any layer"]),
            sim("Why should production Kubernetes manifests pin `:v1.4.0@sha256:...` instead of `:latest`?", ["Mutable tags can silently serve broken/different builds across nodes and break deterministic rollbacks"]),
        ],
    ),

    make_day(
        day=21,
        phase=4,
        title="Docker Networking, Volumes & Stateful Persistence",
        subtitle="Default Bridge vs User-Defined Bridge DNS, Host/Overlay Networks & Volumes vs Bind Mounts",
        goal="Design container-to-container DNS discovery and persistent storage without losing state",
        objective=(
            "Understand why containers on Docker's default `bridge` cannot resolve each other by name whereas Compose user-defined bridges resolve automatically, "
            "compare Overlay networks, and choose Named Volumes vs Bind Mounts vs `tmpfs`."
        ),
        concepts=[
            "Docker's legacy default `bridge` (`docker0`) only routes by raw IP (no embedded DNS). **User-defined bridge** networks (`aiops_platform_default`) run Docker's `127.0.0.11` DNS resolver so `ai_agent` connects directly to `kafka:9092` and `prometheus:9090`.",
            "`host` network disables network namespace isolation for bare-metal throughput; `overlay` (VXLAN) spans multiple Docker Swarm nodes; `none` disables networking.",
            "**Named Volumes** are managed by Docker for durable DB/state persistence (`prometheus_data`); **Bind Mounts** map an exact host directory (`./sre_data:/data`); **tmpfs** stores in-memory ephemeral secrets cleanly.",
        ],
        deep_sections=[
            sec(
                "1. Docker Network Drivers & Storage Options Matrix",
                "Picking the wrong network or volume type causes silent data wipes on `docker compose down` or DNS failures between services.",
                table={
                    "headers": ["Type", "Scope / Lifecycle", "A³P Usage Example"],
                    "rows": [
                        ["User-defined Bridge", "Single host + automatic container-name DNS (`127.0.0.11`)", "`aiops_platform_default` connecting all 10 containers"],
                        ["Host Network", "Shares host network stack directly (no port mapping)", "High-throughput packet capture / node exporters"],
                        ["Overlay Network", "Multi-host encrypted VXLAN encapsulation", "Docker Swarm multi-node clusters"],
                        ["Bind Mount (`./a:/b`)", "Maps exact host code/config path into container", "`./sre_data:/data`, `./grafana/provisioning:...`"],
                        ["Named Volume", "Docker-managed persistent volume surviving `compose down`", "Stateful DB / TSDB unless `-v` is passed!"],
                    ],
                },
            ),
        ],
        architecture="Container eth0 -> User-Defined Bridge (DNS 127.0.0.11) -> Peer Container | Persistent Mount (/data -> ./sre_data)",
        commands=[
            {"cmd": "docker network ls && docker network inspect aiops_platform_default --format '{{range .Containers}}{{.Name}} {{end}}'", "explain": "List Docker networks and inspect containers joined to A³P bridge DNS", "cwd": "/lab"},
            {"cmd": "docker volume ls", "explain": "Inspect Docker-managed persistent volumes on OrbStack", "cwd": "/lab"},
            {"cmd": "docker logs --tail=10 aiops_fluentd", "explain": "Verify Fluentd streaming logs over the shared Docker bridge to Kafka", "cwd": "/lab"},
        ],
        production_use_case="Persisting `sre_platform.db` (`./sre_data:/data`), Prometheus TSDB, and Kafka logs across container rebuilds on OrbStack.",
        scenarios=[
            scenario(
                "Engineer Ran `docker compose down -v` Thinking It Just Restarted Containers — Database Wiped!",
                "After troubleshooting a container bug with `docker compose down -v && docker compose up -d`, all named-volume data disappeared.",
                "docker volume ls && grep -A 3 volumes docker-compose.yml",
                "`-v` (`--volumes`) explicitly deletes all declared **named volumes** alongside containers/networks.",
                "Never pass `-v` in routine restarts (`docker compose up -d --build <svc>`), mount critical data into tracked backups, and snapshot volumes before maintenance.",
            ),
        ],
        troubleshooting=["`ping kafka` fails in manual `docker run` -> attach `--network aiops_platform_default` so embedded DNS resolves `kafka`."],
        interview_qa=[
            qa("Difference between Docker Bridge Network and Overlay Network?", "A Bridge network connects containers on a single host using a virtual Linux bridge + NAT/embedded DNS. An Overlay network encapsulates packets in VXLAN across multiple hosts so containers on separate servers share one virtual L2/L3 network.", "basic"),
            qa("Compare Bind Mounts, Named Volumes, and `tmpfs` mounts.", "Bind mounts map an explicit host filesystem path (ideal for dev/config injection). Named volumes are managed under `/var/lib/docker/volumes` with portable driver support (ideal for databases/prod state). `tmpfs` lives strictly in host RAM and vanishes when stopped (ideal for transient secrets).", "senior"),
        ],
        assignment_items=[
            "Inspect containers attached to aiops_platform_default",
            "Explain why custom bridge networks provide DNS resolution while default bridge does not",
            "Distinguish bind mounts, named volumes, and tmpfs, plus the danger of docker compose down -v",
        ],
        revision=["User-defined bridge = 127.0.0.11 DNS", "Overlay = VXLAN multi-host", "Bind mount vs Named volume vs tmpfs", "Never run compose down -v casually"],
        interview_sim=[
            sim("Container A (`api`) cannot resolve `redis` by hostname when both were started with plain `docker run -d`. Why, and how do you fix it?", ["Default bridge lacks embedded DNS", "Create user-defined network (`docker network create appnet`) and attach both"]),
            sim("Why did editing `./ai_agent/agent.py` locally require `docker compose up -d --build ai_agent`, whereas editing a bind-mounted Grafana JSON only needed a Grafana restart?", ["agent.py is baked via COPY . . at build time; provisioning JSON is a live bind mount"]),
            sim("What is a dangling Docker volume (`docker volume ls -qf dangling=true`) and when is pruning unsafe?", ["Unattached volume left after container rm; contains unbacked DB data if pruned blindly"]),
            sim("How does Docker expose `-p 127.0.0.1:8000:8000` safely vs `-p 8000:8000`?", ["127.0.0.1 restricts host socket to localhost only (safe from LAN exposure), whereas 0.0.0.0 listens on all host interfaces"]),
            sim("When would you choose `tmpfs` mount for `/run/secrets` in a hardened container?", ["Guarantees credentials/certs never touch host disk/swap blocks"]),
        ],
    ),

    make_day(
        day=22,
        phase=4,
        title="Docker Compose Multi-Service Production Stack",
        subtitle="Healthchecks, depends_on service_healthy, Resource Caps & Streaming Dependency Ordering",
        goal="Orchestrate multi-container stacks cleanly with zero startup race conditions",
        objective=(
            "Operate and debug the 10-container A³P Docker Compose topology: understand why `depends_on` without `service_healthy` fails, "
            "how Kafka/Spark/Prometheus/Fluentd coordinate, and how to enforce CPU/memory budgets."
        ),
        concepts=[
            "Plain `depends_on: [kafka]` ONLY waits for the Kafka container process PID 1 to spawn — NOT for port 9092/KRaft broker readiness! Consumers crash in retry loops unless guarded by `condition: service_healthy` + app-level backoff.",
            "Every Compose service should declare `restart: unless-stopped` (or `on-failure`) plus `deploy.resources.limits` (`cpus`, `memory`) so one runaway container never starves the host.",
            "`docker compose up -d --build <service>` rebuilds and recreates ONLY that changed service without interrupting Kafka/Prometheus!",
        ],
        deep_sections=[
            sec(
                "1. How A³P Prevents Startup Race Conditions in `docker-compose.yml`",
                "Look at how `aiops_kafka` runs a functional topic-listing healthcheck every 10s so `aiops_agent` and `spark-submitter` never crash permanently on cold boot.",
                example="kafka:\n  healthcheck:\n    test: [\"CMD\", \"kafka-topics\", \"--bootstrap-server\", \"localhost:9092\", \"--list\"]\n    interval: 10s\n    timeout: 5s\n    retries: 6\nai_agent:\n  depends_on:\n    kafka:\n      condition: service_healthy",
            ),
        ],
        architecture="docker-compose.yml -> Kafka Healthcheck (healthy) -> Fluentd / Spark / DataGen / AI Agent / Practice Lab -> Prom & Grafana",
        commands=[
            {"cmd": "docker inspect --format '{{.Name}} -> {{.State.Health.Status}}' aiops_kafka", "explain": "Verify Kafka functional healthcheck status on OrbStack", "cwd": "/lab"},
            {"cmd": "docker exec aiops_kafka kafka-topics --bootstrap-server kafka:9092 --list", "explain": "List live streaming topics (raw_app_logs, anomalies_topic) inside Kafka", "cwd": "/lab"},
            {"cmd": "docker exec aiops_prometheus wget -qO- http://localhost:9090/-/ready", "explain": "Confirm Prometheus TSDB readiness from inside the container", "cwd": "/lab"},
        ],
        production_use_case="Running the full 10-container Aariz Advance AI platform (A³P) on Mac OrbStack inside 5.5 vCPU and 7.75 GB RAM.",
        scenarios=[
            scenario(
                "Spark Streaming Submitter Dies Immediately on Cold Stack Boot",
                "On cold startup, `spark-submitter` exits with `KafkaException: Failed to construct kafka consumer / UnknownHost` even though `depends_on: kafka` was set.",
                "docker logs --tail 30 aiops_spark_submitter ; docker inspect aiops_kafka --format '{{json .State.Health}}'",
                "`depends_on` without `condition: service_healthy` started `spark-submitter` 1 second after Kafka's container started, 15 seconds BEFORE Kafka broker port 9092 finished initializing KRaft metadata.",
                "Add a real functional `healthcheck` (`kafka-topics --list`) on Kafka + `condition: service_healthy`, AND retry loops inside application consumers.",
            ),
        ],
        troubleshooting=["Container pinned too small (`512M` for Spark Worker running PySpark) causes silent OOMKills -> profile via `docker stats` and cap appropriately (`1536M`)."],
        interview_qa=[
            qa("How do you eliminate startup race conditions between Kafka/DB and app containers in Docker Compose?", "Pair a **functional** `healthcheck` (e.g. `kafka-topics --list` or `pg_isready`, not just `pidof`) with `depends_on: <svc>: condition: service_healthy`, PLUS exponential-backoff retry loops inside application startup code.", "senior"),
            qa("How does `docker compose up -d --build ai_agent` avoid taking down Kafka and Prometheus?", "Compose hashes container configuration/image per service; targeting a single service builds and recreates only `aiops_agent` while leaving healthy unchanged dependency containers untouched.", "basic"),
        ],
        assignment_items=[
            "Verify Kafka healthcheck and list active topics inside aiops_kafka",
            "Check Prometheus readiness endpoint inside aiops_prometheus",
            "Explain condition: service_healthy + application retry loops",
        ],
        revision=["depends_on != readiness without service_healthy", "Use functional healthchecks", "Target single-service rebuilds with compose up -d --build <svc>"],
        interview_sim=[
            sim("In `docker-compose.yml`, you used `curl localhost:8000/health` in a healthcheck, and the container went `unhealthy` even though the app was running. Why?", ["Check if curl/wget is even installed in python-slim! Use python3 -c urllib.request instead"]),
            sim("How does `docker compose` know whether to recreate a container on `compose up -d`?", ["Compares container label hash of config/env/image; recreates only drifted services"]),
            sim("Why should every production Compose/K8s spec define memory limits, yet leave headroom above typical RSS?", ["Prevents noisy-neighbor host OOM while avoiding spurious cgroup OOMKill Exit 137 during burst traffic/GC"]),
            sim("When is Docker Compose appropriate vs migrating to Kubernetes?", ["Single-host dev/edge/local labs (like A³P on OrbStack) = Compose; multi-node HA, rolling zero-downtime, autoscaling, RBAC = Kubernetes"]),
            sim("How can you inspect the exact resolved YAML (after `.env` substitution) that Docker Compose runs?", ["docker compose config"]),
        ],
    ),
]

