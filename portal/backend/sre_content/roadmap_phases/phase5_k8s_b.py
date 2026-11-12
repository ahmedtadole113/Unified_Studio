"""Phase 5B (Days 27-29): K8s Resources/HPA, RBAC/NetworkPolicy/Helm & Crash Debugging."""

from typing import Dict, List
from .common import make_day, qa, scenario, sec, sim

DAYS_27_TO_29: List[Dict] = [
    make_day(
        day=27,
        phase=5,
        title="HPA Autoscaling, Resource Requests/Limits & Pod QoS",
        subtitle="Scheduler Requests vs Cgroup Limits, CFS CPU Throttling, OOMKill (137) & HPA Math",
        goal="Size Pod CPU/memory safely, avoid CFS latency throttling, and configure working HPA autoscalers",
        objective=(
            "Master the critical difference between compressible CPU (`CFS throttling` latency spikes) and incompressible Memory (`OOMKill 137`), "
            "understand Pod QoS eviction priority (`Guaranteed` vs `Burstable` vs `BestEffort`), and compute HPA replica scaling."
        ),
        concepts=[
            "`requests` guarantee minimum resources and drive **kube-scheduler** bin-packing + HPA `% utilization` denominators (`actual / request`).",
            "`limits` set hard Linux **cgroup** caps: exceeding `memory` limit triggers instant kernel **OOMKill** (`Exit 137`); exceeding `cpu` limit triggers Linux **CFS quota throttling** (silent p99 latency spikes!).",
            "**QoS Classes**: `Guaranteed` (`req == limit` for CPU & Mem on all containers, evicted LAST), `Burstable` (`req < limit`), `BestEffort` (none set, evicted FIRST under Node Pressure).",
            "HPA formula: `desiredReplicas = ceil(currentReplicas * (currentMetric / targetMetric))` (requires `requests` + `metrics-server`).",
        ],
        deep_sections=[
            sec(
                "1. Pod QoS Classes & Why CPU Limits Can Hurt Latency",
                "Setting `cpu: 500m` limit on a bursty multi-threaded runtime (JVM/Node/Go) means the app burns its 50ms quota inside each 100ms Linux CFS period and gets **frozen for the remaining 50ms** — causing mysterious 100ms–300ms p99 tail latency even when the worker node is 70% idle!",
                table={
                    "headers": ["Resource Exceeded", "Compressible?", "Kernel Behavior & SRE Symptom"],
                    "rows": [
                        ["CPU Limit (`cpu.max`)", "YES", "CFS Throttling (`nr_throttled` climbs) -> sudden p99 latency spikes without crashes"],
                        ["Memory Limit (`memory.max`)", "NO", "OOMKiller sends SIGKILL -> Pod crashes with `OOMKilled` (`Exit Code 137`)"],
                        ["Node Disk / Ephemeral Storage", "NO", "Kubelet `DiskPressure` taint -> `Evicted` Pods starting with `BestEffort`"],
                    ],
                },
                example="# HPA scaling example:\ncurrentReplicas = 2, requests.cpu = 500m, target = 50% (250m avg)\nLive pods average 400m (80% of request):\ndesiredReplicas = ceil(2 * (80 / 50)) = ceil(3.2) = 4 replicas!",
            ),
        ],
        architecture="Metrics Server -> HPA Loop (desired = ceil(cur * metric/target)) -> Scale Deployment | cgroups -> CFS / OOMKill",
        commands=[
            {"cmd": "kubectl describe node orbstack | grep -A 10 'Allocated resources'", "explain": "Inspect cluster CPU/Memory requests and limits allocation", "cwd": "/lab/k8s-demo"},
            {"cmd": "kubectl autoscale deployment sre-nginx-demo -n sre-practice --cpu-percent=60 --min=1 --max=4 --dry-run=client -o yaml", "explain": "Generate HPA manifest via dry-run and inspect scaling thresholds", "cwd": "/lab/k8s-demo"},
        ],
        production_use_case="Tuning Spark/AI Worker CPU & RAM bounds so workloads neither suffer silent CFS throttling nor OOMKill mid-stream.",
        scenarios=[
            scenario(
                "API p99 Latency Jumps From 25ms to 450ms Under Light Node Load (`50%` Free Node CPU!)",
                "Service team insists the cluster isn't busy (`Node CPU 45%`), yet API p99 latency spikes randomly every 100ms.",
                "PromQL: rate(container_cpu_cfs_throttled_periods_total[5m]) / rate(container_cpu_cfs_periods_total[5m])",
                "Pod had an overly tight `limits.cpu: 200m` causing Linux CFS quota pauses whenever worker threads initialized or handled bursts.",
                "Profile real burst CPU usage, set `requests.cpu` accurately for scheduling & HPA, and widen (or carefully remove for Guaranteed/non-noisy-neighbor services) `limits.cpu` while keeping `requests.memory == limits.memory`.",
            ),
        ],
        troubleshooting=["HPA shows `<unknown>/60%` -> either Pods are missing `resources.requests.cpu` OR `metrics-server` is unhealthy."],
        interview_qa=[
            qa("What happens when a Pod exceeds its CPU limit vs its Memory limit?", "CPU is compressible: exceeding CPU limit throttles the container via Linux CFS quotas, degrading latency without killing the Pod. Memory is incompressible: exceeding Memory limit triggers kernel OOMKill (`SIGKILL`, Exit `137`).", "basic"),
            qa("Why does setting `requests.memory == limits.memory` (`Guaranteed` QoS) protect stateful/critical services?", "Pods with `Guaranteed` QoS receive `oom_score_adj = -997` (near immune compared to `BestEffort` at `+1000`) and are the very last Pods kubelet evicts during Node MemoryPressure.", "senior"),
        ],
        assignment_items=[
            "Inspect node Allocated resources on OrbStack K8s",
            "Generate an HPA YAML using --dry-run=client -o yaml and compute scaling math",
            "Explain Guaranteed vs Burstable vs BestEffort QoS and CFS CPU throttling",
        ],
        revision=["Requests = schedule + HPA base", "Limits = CFS throttle (CPU) / OOMKill 137 (Mem)", "Guaranteed = req==limit (evicted last)"],
        interview_sim=[
            sim("A Deployment has `requests.cpu: 500m`, `replicas: 2`, and HPA targets `50%` CPU. Traffic pushes average pod CPU to `600m`. What does HPA scale replicas to?", ["600m / 500m = 120% utilization", "ceil(2 * (120 / 50)) = ceil(4.8) = 5 replicas"]),
            sim("Why do some production Kubernetes teams set `requests.memory == limits.memory`, set `requests.cpu`, and intentionally omit `limits.cpu`?", ["Eliminates random 100ms CFS throttling latency spikes while requests still isolate scheduler guarantees & CPU shares under contention"]),
            sim("HPA shows `Targets: <unknown>/70%` and stops scaling during a flash sale. Name two causes.", ["Pod missing resources.requests.cpu, or metrics-server failing/unreachable"]),
            sim("Why did `kubectl delete pod` not prevent an eviction storm when a node hit `DiskPressure`?", ["Unbounded container stdout logs or /tmp emptyDir filled node ephemeral disk, forcing kubelet to evict BestEffort/Burstable pods"]),
            sim("When is `KEDA` (Event-Driven Autoscaling) better than standard CPU/RAM HPA?", ["Queue-backed consumers (Kafka consumer lag, SQS depth, token rate) where lag climbs before CPU saturates"]),
        ],
    ),

    make_day(
        day=28,
        phase=5,
        title="RBAC, NetworkPolicies & Helm Package Management",
        subtitle="Least-Privilege Roles, ServiceAccounts, Default-Deny Firewalls & Helm Chart Releases",
        goal="Enforce zero-trust K8s access & network segmentation and template releases cleanly with Helm",
        objective=(
            "Implement Kubernetes Segregation of Duties with `Role`/`ClusterRole`/`ServiceAccount`, restrict lateral pod movement via `NetworkPolicy`, "
            "and manage versioned multi-resource releases (`helm lint`, `helm template`, `helm rollback`)."
        ),
        concepts=[
            "**RBAC**: `Role` (namespaced) or `ClusterRole` (cluster-wide / reusable) lists `[apiGroups, resources, verbs]` -> bound to a `ServiceAccount`/User/Group via `RoleBinding`/`ClusterRoleBinding`.",
            "Always verify permissions programmatically with `kubectl auth can-i <verb> <resource> --as=system:serviceaccount:<ns>:<sa>`.",
            "**NetworkPolicy**: Kubernetes Pods accept ALL traffic by default! Adding a `default-deny-all` NetworkPolicy blocks everything except explicitly whitelisted pod selectors/ports/namespaces (requires CNI support like Cilium/Calico).",
            "**Helm** packages K8s YAML templates + `values.yaml` per environment (`dev`/`prod`) and records release revisions for atomic `helm upgrade` & `helm rollback`.",
        ],
        deep_sections=[
            sec(
                "1. Least-Privilege RBAC & Default-Deny NetworkPolicy Blueprint",
                "Never mount the `default` ServiceAccount with `cluster-admin` — scope each app SA strictly to the exact resources and verbs it needs.",
                example="# Default-Deny Ingress + Egress NetworkPolicy (zero-trust baseline):\napiVersion: networking.k8s.io/v1\nkind: NetworkPolicy\nmetadata:\n  name: default-deny-all\nspec:\n  podSelector: {}          # Applies to ALL pods in namespace\n  policyTypes: [Ingress, Egress]  # Remember to allow DNS (UDP/TCP 53) in egress!",
            ),
        ],
        architecture="ServiceAccount -> RoleBinding -> Role (Verbs) | NetworkPolicy (Zero-Trust) | Helm (Chart + values.yaml) -> Release Rev",
        commands=[
            {"cmd": "kubectl auth can-i get pods -n sre-practice && kubectl auth can-i '*' '*' --all-namespaces", "explain": "Test RBAC authorization programmatically via kubectl auth can-i", "cwd": "/lab/helm-demo"},
            {"cmd": "helm lint /lab/helm-demo && helm template sre-demo /lab/helm-demo | head -n 35", "explain": "Lint Helm chart and render final Kubernetes YAML locally", "cwd": "/lab/helm-demo"},
            {"cmd": "helm list -A", "explain": "Inspect installed Helm releases across all namespaces", "cwd": "/lab/helm-demo"},
        ],
        production_use_case="Mapping Security & Risk Segregation-of-Duties controls onto Kubernetes deployments and Helm release audits.",
        scenarios=[
            scenario(
                "Applied `default-deny` NetworkPolicy and Suddenly Every Microservice Fails DNS Lookups!",
                "Right after enabling a strict `NetworkPolicy` blocking Ingress+Egress, pods stop resolving internal `kafka` and external endpoints.",
                "kubectl get netpol -n prod ; kubectl exec pod -- nslookup kubernetes.default",
                "`policyTypes: [Ingress, Egress]` without an Egress exception for **UDP/TCP port 53** to `kube-system` (`CoreDNS`) blocked all DNS queries!",
                "Always include a baseline DNS allow-egress rule (`to: namespaceSelector: kubernetes.io/metadata.name: kube-system`, `ports: [UDP 53, TCP 53]`) with every `Egress` NetworkPolicy.",
            ),
        ],
        troubleshooting=["Helm upgrade hangs or fails with `another operation (install/upgrade/rollback) is in progress` -> inspect `helm history <rel>` and recover safely rather than deleting secrets blindly."],
        interview_qa=[
            qa("Difference between `Role` and `ClusterRole`?", "`Role` grants permissions only inside a single Namespace. `ClusterRole` grants permissions cluster-wide (nodes, PVs, namespaces) OR defines a reusable permission template that a namespaced `RoleBinding` binds locally inside one namespace.", "basic"),
            qa("Why should production Pods set `automountServiceAccountToken: false` unless calling the Kubernetes API?", "Mounting an API token inside every web pod increases blast radius if an RCE vulnerability occurs; Pods serving plain HTTP traffic don't need K8s API credentials.", "senior"),
        ],
        assignment_items=[
            "Test kubectl auth can-i checks on sre-practice",
            "Lint and render /lab/helm-demo using helm lint and helm template",
            "Explain why Egress NetworkPolicies must explicitly permit CoreDNS port 53",
        ],
        revision=["Role (ns) vs ClusterRole (global)", "kubectl auth can-i tests RBAC", "NetworkPolicy Egress needs port 53 DNS allow", "helm lint + template before apply"],
        interview_sim=[
            sim("A developer created a `NetworkPolicy` with `policyTypes: [Ingress]` allowing port 8080 from `frontend`, and asks why their backend pod can still curl the internet.", ["policyTypes omitted `Egress`, so all outbound traffic remains unrestricted until an Egress policy selects the pod"]),
            sim("How does `helm upgrade --install --atomic --timeout 3m` protect CI/CD deployments?", ["Wait for all Deployments/Ready probes within 3m; automatically rolls back on failure (`--atomic`)"]),
            sim("How do you debug why a ServiceAccount `deployer` got `Forbidden: pods is forbidden` in CI?", ["kubectl auth can-i list pods --as=system:serviceaccount:prod:deployer -n prod and inspect RoleBinding subjects"]),
            sim("Compare `helm template` + `kubectl/ArgoCD` vs `helm install`.", ["helm template renders plain YAML so GitOps (ArgoCD) reviews exact diffs without needing Tiller/imperative Helm state"]),
            sim("If two NetworkPolicies both select the same Pod, do they deny or union-allow?", ["Kubernetes NetworkPolicies are additive (union of allowed rules); there is no explicit deny rule"]),
        ],
    ),

    make_day(
        day=29,
        phase=5,
        title="Phase 5 Lab: Debugging CrashLoopBackOff, ImagePull & Pending Pods",
        subtitle="Golden K8s Debug Loop: Events, describe pod, logs --previous & Clean Recovery",
        goal="Triage real failing Kubernetes pods systematically on OrbStack in under 2 minutes",
        objective=(
            "Execute Kubernetes failure debugging live against `/lab/k8s-demo/crashloop-broken.yaml`: decode `CrashLoopBackOff`, "
            "`ImagePullBackOff`, `CreateContainerConfigError`, and `Pending` states using `describe`, `events`, and `logs --previous`."
        ),
        concepts=[
            "`CrashLoopBackOff` is NOT an error itself — it means the container started, crashed (Exit 1/137/127), and kubelet is backing off exponentially (`10s, 20s, 40s... 5m`) before restarting it again.",
            "Golden K8s debug loop: 1) `kubectl get pods` (Status + Restarts) -> 2) `kubectl describe pod` (Events & Last State Exit Code!) -> 3) `kubectl logs <pod> --previous` -> 4) Check ConfigMap/Secret/PVC -> 5) Fix & verify.",
            "`CreateContainerConfigError` = missing referenced `ConfigMap`/`Secret` key (`optional: false`); `Pending` = Scheduler filter failure (CPU/RAM/PVC/taints).",
        ],
        deep_sections=[
            sec(
                "1. Kubernetes Pod Failure Status Decoder",
                "Reading the exact Pod `STATUS` column points immediately to which subsystem failed.",
                table={
                    "headers": ["Pod Status", "Meaning", "First Command"],
                    "rows": [
                        ["Pending", "Scheduler cannot find a matching worker node", "`kubectl describe pod` (read FailedScheduling event!)"],
                        ["ImagePullBackOff", "Wrong tag, registry down, or missing `imagePullSecrets`", "`kubectl describe pod` (check exact registry error)"],
                        ["CreateContainerConfigError", "Missing ConfigMap/Secret name or key before start", "`kubectl describe pod` -> verify `cm`/`secret`"],
                        ["CrashLoopBackOff", "Process inside container keeps exiting (`1`, `137`, `127`)", "`kubectl logs <pod> --previous` + `Last State` Exit Code"],
                        ["Running (0/1 Ready)", "Container alive, but `readinessProbe` is failing", "`kubectl describe pod` -> Readiness probe failed HTTP code"],
                    ],
                },
            ),
        ],
        architecture="kubectl get pods -> [Pending / ImagePull / ConfigErr / CrashLoop] -> describe pod (Events) -> logs --previous -> Fix",
        commands=[
            {"cmd": "kubectl apply -f /lab/k8s-demo/crashloop-broken.yaml && sleep 4 && kubectl get pod crashloop-lab -n sre-practice", "explain": "Deploy intentionally broken Pod to trigger CrashLoopBackOff live", "cwd": "/lab/k8s-demo"},
            {"cmd": "kubectl logs crashloop-lab -n sre-practice --previous 2>/dev/null || kubectl logs crashloop-lab -n sre-practice", "explain": "Capture stderr traceback from the crashed container attempt", "cwd": "/lab/k8s-demo"},
            {"cmd": "kubectl describe pod crashloop-lab -n sre-practice | tail -n 16", "explain": "Inspect Exit Code, Restart Count, and kubelet BackOff events", "cwd": "/lab/k8s-demo"},
            {"cmd": "kubectl delete pod crashloop-lab -n sre-practice --ignore-not-found && kubectl delete -f /lab/k8s-demo/deployment.yaml --ignore-not-found", "explain": "Clean up practice Kubernetes resources cleanly", "cwd": "/lab/k8s-demo"},
        ],
        production_use_case="Rehearsing fast `CrashLoopBackOff` triage on live OrbStack Kubernetes without touching production.",
        scenarios=[
            scenario(
                "Distroless Production Container Keeps Crashing (`No shell /bin/sh` to `kubectl exec` Into!)",
                "A hardened Go/Python distroless Pod crashes in 2s or runs broken without `/bin/sh` or `curl` inside the image.",
                "kubectl logs <pod> --previous ; kubectl debug -it <pod> --image=busybox:1.36 --target=<container>",
                "Production distroless images strip shells/tools to minimize CVEs, so standard `kubectl exec -it <pod> -- sh` fails.",
                "Always read `--previous` logs first; if live inspection is needed, attach an **ephemeral debug container** (`kubectl debug --target=...` sharing PID/Net namespaces) without modifying the Deployment.",
            ),
        ],
        troubleshooting=["`kubectl logs <pod>` prints nothing during crash loop -> always add `--previous` (`-p`) to read the last dead container's stdout/stderr!"],
        interview_qa=[
            qa("How do you troubleshoot a Pod stuck in `CrashLoopBackOff`?", "Run `kubectl describe pod` to inspect `Last State` Exit Code (`1`=app bug, `137`=OOMKill, `127`=missing entrypoint) and Events, then run `kubectl logs <pod> --previous` for the dying traceback, and verify ConfigMap/Secret/volume mounts.", "basic"),
            qa("A Pod shows `Pending` for 10 minutes with `0/6 nodes are available: 3 Insufficient cpu, 3 node(s) had untolerated taint`. How do you diagnose and resolve?", "Check `kubectl describe pod` Events (`FailedScheduling`), verify whether `requests.cpu` was accidentally oversized (e.g. `40` cores typo vs `400m`), check node capacity (`kubectl describe nodes`) or Cluster Autoscaler / Karpenter logs, or add matching `tolerations` if targeting dedicated nodes.", "senior"),
        ],
        assignment_items=[
            "Deploy /lab/k8s-demo/crashloop-broken.yaml and inspect logs --previous + describe events",
            "Identify exact error message ('missing config /etc/app/prod.conf') and Exit Code 1",
            "Delete test pods cleanly leaving sre-practice clean",
        ],
        revision=["describe pod -> Events & Exit Code", "logs --previous captures dead container output", "kubectl debug attaches ephemeral tools to distroless"],
        interview_sim=[
            sim("A newly deployed Pod fails with `CreateContainerConfigError`. What happened and how do you find the missing item in 1 command?", ["kubectl describe pod <name> Events shows exact missing ConfigMap/Secret or key name"]),
            sim("Why does `kubectl logs <pod>` sometimes appear empty even though the app crashed loudly?", ["Current container attempt hasn't flushed/restarted yet; use kubectl logs <pod> --previous"]),
            sim("A Pod is `Running` with `0/1 READY` for 5 minutes without restarting. Why isn't it in `CrashLoopBackOff`?", ["Container process didn't exit, so Liveness (if same or absent) isn't killing it, while ReadinessProbe is failing — traffic is safely withheld"]),
            sim("How does `kubectl debug` help troubleshoot a distroless image without `sh` or `curl`?", ["Launches ephemeral container sharing the target Pod's network/PID namespaces"]),
            sim("A container starts and exits `0` immediately (`Completed`) inside a Deployment, causing CrashLoopBackOff. Why?", ["Main process forked to background (`daemon`) instead of staying foreground, OR Deployment ran a one-off script that belongs in a Job"]),
        ],
    ),
]

