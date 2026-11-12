"""Phase 5A (Days 23-26): Kubernetes Control Plane, Workloads, Services, Ingress & Storage."""

from typing import Dict, List
from .common import make_day, qa, scenario, sec, sim

DAYS_23_TO_26: List[Dict] = [
    make_day(
        day=23,
        phase=5,
        title="Kubernetes Architecture: Control Plane & Worker Nodes",
        subtitle="API Server, etcd, Scheduler, Controller Manager, kubelet, kube-proxy & CRI/CNI/CSI",
        goal="Trace every API call and reconciliation loop inside a live Kubernetes cluster",
        objective=(
            "Understand how Kubernetes achieves declarative self-healing via level-triggered reconciliation loops: trace what happens "
            "across `kube-apiserver`, `etcd`, `kube-scheduler`, `kube-controller-manager`, `kubelet`, and `kube-proxy` when you run `kubectl apply`."
        ),
        concepts=[
            "**Control Plane**: `kube-apiserver` (ONLY component touching `etcd`, enforces AuthN/AuthZ/Mutating & Validating Admission), `etcd` (Raft strongly-consistent KV store), `kube-scheduler` (Filter + Score node placement), `kube-controller-manager` (Node, Deployment, ReplicaSet, Endpoints controllers).",
            "**Worker Node**: `kubelet` (watches API Server for assigned Pods and drives CRI runtime), `kube-proxy` (programs iptables/IPVS/eBPF rules for ClusterIP Services), **CNI** (Calico/Cilium/Flannel pod networking).",
            "Kubernetes is **reconciliation-driven**: controllers continuously diff *Desired State* (`spec` in `etcd`) vs *Observed State* (`status` from kubelet) and converge them.",
        ],
        deep_sections=[
            sec(
                "1. Step-by-Step: What Happens When You Run `kubectl apply -f deployment.yaml`?",
                "This is one of the top Senior SRE interview questions. Trace the asynchronous event chain cleanly:",
                bullets=[
                    "1. `kubectl` sends HTTP POST/PATCH Deployment manifest to `kube-apiserver` (TLS + AuthN + RBAC AuthZ + Admission Controllers).",
                    "2. `kube-apiserver` persists the Deployment object into `etcd` (quorum Raft write) and immediately returns `201/200`.",
                    "3. `Deployment Controller` watches Deployment events -> creates/updates a `ReplicaSet` in `etcd`.",
                    "4. `ReplicaSet Controller` sees `desired=3, actual=0` -> creates 3 `Pod` objects in `etcd` with `spec.nodeName` unset (`Pending`).",
                    "5. `kube-scheduler` watches unscheduled Pods -> filters feasible nodes (CPU/RAM/taints/affinity), scores best node, sets `Pod.spec.nodeName`.",
                    "6. Target `kubelet` sees its node assigned -> calls CRI (`containerd`) to pull image, CNI to attach Pod IP, CSI to mount volumes, starts container, and updates `Pod.status`.",
                ],
            ),
        ],
        architecture="kubectl -> API Server -> Admission -> etcd <-> [Deploy/RS Controllers & Scheduler] -> kubelet (CRI/CNI/CSI) -> Running Pod",
        commands=[
            {"cmd": "kubectl cluster-info && kubectl get nodes -o wide", "explain": "Verify live connection to OrbStack Kubernetes control plane", "cwd": "/lab/k8s-demo"},
            {"cmd": "kubectl get pods -n kube-system -o wide", "explain": "Inspect CoreDNS and storage provisioner pods in kube-system", "cwd": "/lab/k8s-demo"},
            {"cmd": "kubectl describe node orbstack | grep -A 10 'Conditions:'", "explain": "Inspect Node Ready, MemoryPressure, DiskPressure, and PIDPressure conditions", "cwd": "/lab/k8s-demo"},
        ],
        production_use_case="OrbStack runs live Kubernetes `v1.36.5+orb1` natively on your Mac so every `kubectl` and `helm` exercise executes against a real API Server.",
        scenarios=[
            scenario(
                "`kubectl get pods` Hangs or Returns `etcdserver: request timed out` Cluster-Wide",
                "Deployments stall, `kubectl` takes 15+ seconds or errors with 504/timeout, yet existing running containers still serve some traffic.",
                "kubectl get --raw='/readyz?verbose' ; check etcd disk fsync latency & API server logs",
                "`etcd` is disk-fsync sensitive — slow EBS/disk I/O or lost Raft quorum (`< 2/3` control plane nodes up) stalls every write/read in `kube-apiserver`.",
                "Existing running pods continue running via kubelet/iptables until etcd quorum & fast NVMe disk IOPS are restored; never lose odd-numbered `etcd` quorum (3 or 5 nodes) and automate `etcdctl snapshot save` backups.",
            ),
        ],
        troubleshooting=["Node shows `NotReady` -> check `kubectl describe node` Conditions (`MemoryPressure`/`DiskPressure`) and `kubelet` logs on node."],
        interview_qa=[
            qa("Explain what each Kubernetes Control Plane component does.", "`kube-apiserver` serves REST API, auth, and admission; `etcd` stores all cluster state consistently; `kube-scheduler` binds Pending pods to nodes; `kube-controller-manager` runs reconciliation loops (Deployment, RS, Node, Job).", "basic"),
            qa("If all Control Plane nodes crash temporarily, do running application Pods immediately stop serving traffic?", "No — existing Pod containers keep running via `containerd` and `kube-proxy` iptables/IPVS rules on worker nodes, though no new Pods can schedule, HPA cannot scale, and dead Pod replacements won't spawn until Control Plane returns.", "senior"),
        ],
        assignment_items=[
            "Verify live OrbStack Kubernetes node status and kube-system pods",
            "Trace the 6-step reconciliation flow from kubectl apply to running container",
            "Inspect Conditions on node orbstack and explain MemoryPressure vs DiskPressure",
        ],
        revision=["API Server = sole etcd gateway", "Controllers = Desired vs Actual loops", "Running workloads survive temporary control-plane outage"],
        interview_sim=[
            sim("Walk through everything that happens in Kubernetes from running `kubectl apply -f deploy.yaml` until traffic reaches the Pod.", ["API Server Auth/Admission -> etcd", "Deployment -> RS -> Pod controllers", "Scheduler nodeName bind", "kubelet CRI/CNI/CSI + Readiness -> Endpoints"]),
            sim("Why must `etcd` clusters run 3 or 5 nodes rather than 2 or 4?", ["Raft consensus requires strict majority quorum (floor(N/2)+1): 3 tolerates 1 failure (quorum 2); 4 ALSO tolerates only 1 failure (quorum 3)!"]),
            sim("Compare `CRI`, `CNI`, and `CSI` interfaces in Kubernetes.", ["CRI = containerd/CRI-O container lifecycle; CNI = Cilium/Calico pod networking; CSI = EBS/GCE/Ceph persistent volumes"]),
            sim("What is the difference between a `MutatingAdmissionWebhook` and a `ValidatingAdmissionWebhook`?", ["Mutating modifies incoming YAML (e.g. injecting Istio sidecar) BEFORE validation; Validating accepts/rejects policy compliance (Kyverno/OPA)"]),
            sim("Where does `kube-proxy` sit on worker nodes and how do Services scale beyond 5,000 services?", ["Watches Service/Endpoints -> updates iptables (O(n)) or IPVS (O(1) hash table) or eBPF (Cilium kube-proxy-less)"]),
        ],
    ),

    make_day(
        day=24,
        phase=5,
        title="Pods, ReplicaSets, Deployments & Health Probes",
        subtitle="Readiness vs Liveness vs Startup Probes, RollingUpdate & Zero-Downtime Rollbacks",
        goal="Ship zero-downtime Kubernetes rolling deployments with properly scoped health probes",
        objective=(
            "Configure `RollingUpdate` (`maxSurge`, `maxUnavailable`), recover instantly with `kubectl rollout undo`, "
            "and avoid the #1 Kubernetes outage: cascading restarts caused by pointing a Liveness probe at downstream dependencies."
        ),
        concepts=[
            "**Readiness Probe**: determines if a Pod can receive Service traffic (adds/removes Pod IP from Service `Endpoints`). Failure does NOT kill the Pod.",
            "**Liveness Probe**: detects deadlocked containers (`kubelet` kills & restarts container!). NEVER check external DBs/Redis in a Liveness probe!",
            "**Startup Probe**: protects slow-starting apps (JVM/ML models loading weights) so Liveness doesn't kill them mid-boot.",
            "`RollingUpdate` replaces old ReplicaSet pods gradually using `maxSurge` (extra pods allowed) and `maxUnavailable` (max offline pods).",
        ],
        deep_sections=[
            sec(
                "1. Probe Comparison & Cascading Outage Anti-Pattern",
                "If your Liveness probe hits `/health/deep` which queries PostgreSQL, and PostgreSQL hiccups for 10 seconds, EVERY pod in your cluster fails Liveness simultaneously and restarts in a thundering herd!",
                table={
                    "headers": ["Probe Type", "Action on Failure", "What It Should Check"],
                    "rows": [
                        ["Startup", "Blocks Liveness/Readiness until first success (or kills after threshold)", "Model/JVM warmup complete"],
                        ["Readiness", "Removes Pod IP from Service Endpoints (0 traffic, pod stays alive)", "App ready + critical local pools ready"],
                        ["Liveness", "Sends SIGTERM/SIGKILL & restarts container", "Deadlock check ONLY (lightweight local loop/process ping)"],
                    ],
                },
                example="# Safe zero-downtime RollingUpdate spec:\nstrategy:\n  type: RollingUpdate\n  rollingUpdate:\n    maxSurge: 1\n    maxUnavailable: 0   # Never drop below 100% desired capacity!",
            ),
        ],
        architecture="Deployment -> ReplicaSet (v1 -> v2) -> Pod + Startup -> Readiness (Endpoints Gate) + Liveness (Self-Heal)",
        commands=[
            {"cmd": "kubectl apply -f /lab/k8s-demo/deployment.yaml && kubectl rollout status deployment/sre-nginx-demo -n sre-practice", "explain": "Deploy sre-nginx-demo into OrbStack K8s and wait for rollout", "cwd": "/lab/k8s-demo"},
            {"cmd": "kubectl get pods,deploy,rs -n sre-practice -o wide", "explain": "Inspect Deployment -> ReplicaSet -> Pod hierarchy", "cwd": "/lab/k8s-demo"},
            {"cmd": "kubectl scale deployment/sre-nginx-demo -n sre-practice --replicas=3 && kubectl get pods -n sre-practice", "explain": "Scale deployment to 3 replicas live and observe scheduling", "cwd": "/lab/k8s-demo"},
            {"cmd": "kubectl rollout history deployment/sre-nginx-demo -n sre-practice", "explain": "View revision history available for instant kubectl rollout undo", "cwd": "/lab/k8s-demo"},
        ],
        production_use_case="Zero-downtime rollouts and instant rollback drills in OrbStack `sre-practice` namespace.",
        scenarios=[
            scenario(
                "Database Blip Causes Entire API Fleet to Enter `CrashLoopBackOff` Simultaneously",
                "PostgreSQL had a 15s primary failover. Instead of recovering cleanly once DB came back, all 40 API pods restarted and dropped 100% of traffic.",
                "kubectl describe pod -l app=api | grep -i liveness ; kubectl get events --sort-by=.lastTimestamp",
                "The API's `livenessProbe` checked `SELECT 1` on PostgreSQL! Every pod failed liveness, got killed by kubelet, and thundering-herd rebooted.",
                "Move downstream dependency checks to **Readiness** only (removing pods from traffic gracefully without killing them), and keep **Liveness** strictly local (`HTTP 200 /livez`).",
            ),
        ],
        troubleshooting=["502s during rolling update -> Pod lacks Readiness probe OR app stops immediately on SIGTERM while kube-proxy still updates iptables (add `preStop: sleep 5`)."],
        interview_qa=[
            qa("Difference between Readiness, Liveness, and Startup probes?", "Readiness failure removes the Pod IP from Service Endpoints (stops routing traffic while keeping the container running). Liveness failure kills and restarts the container. Startup disables both until slow app initialization succeeds once.", "basic"),
            qa("How do you guarantee zero dropped requests during Kubernetes rolling updates?", "Set `maxUnavailable: 0`, define an accurate `readinessProbe`, add a `lifecycle.preStop` `sleep 5` hook (so Endpoint removal propagates across node kube-proxy/ALBs before app closes listening socket), and handle `SIGTERM` gracefully.", "senior"),
        ],
        assignment_items=[
            "Apply /lab/k8s-demo/deployment.yaml, scale to 3 replicas, and inspect RS + Pods",
            "Check rollout history and test kubectl rollout undo",
            "Explain why Liveness probes must never depend on external databases",
        ],
        revision=["Readiness = traffic gate; Liveness = restart", "Never check external DB in Liveness", "preStop sleep 5 + SIGTERM prevents deploy 502s"],
        interview_sim=[
            sim("During every deploy of your Go microservice, Prometheus records ~200 HTTP 502 errors for 3 seconds even with `maxUnavailable: 0`. Why and how do you eliminate them?", ["Endpoint removal & iptables propagation are async relative to SIGTERM", "Add preStop exec sleep 5-10s + graceful HTTP drain"]),
            sim("A Java ML inference service needs 90 seconds to load weights, but your Deployment keeps killing it at 45s in a loop. Which probe fixes this cleanly?", ["startupProbe (failureThreshold: 12, periodSeconds: 10 = 120s boot allowance) before livenessProbe activates"]),
            sim("Compare `maxSurge: 25%, maxUnavailable: 0` vs `maxSurge: 0, maxUnavailable: 25%`.", ["First ensures full capacity before terminating old pods (needs spare cluster headroom); second saves cluster capacity during rollouts"]),
            sim("How does `kubectl rollout undo deployment/api --to-revision=2` work under the hood?", ["Deployment controller scales ReplicaSet revision 2 back up while scaling bad revision 3 down"]),
            sim("What is a `PodDisruptionBudget` (`PDB`) and how does it protect availability during cluster upgrades?", ["Ensures voluntary evictions (node drain/upgrade) maintain minAvailable or maxUnavailable healthy replicas"]),
        ],
    ),

    make_day(
        day=25,
        phase=5,
        title="Services, Endpoints, Ingress, ConfigMaps & Secrets",
        subtitle="ClusterIP/NodePort/LoadBalancer, Empty Endpoints Triage, L7 Ingress & Secret Security",
        goal="Route cluster/external traffic cleanly via Services & Ingress and manage configs securely",
        objective=(
            "Trace Kubernetes Service packet routing (`Service` -> `EndpointSlice` -> `Pod IP`), fix the #1 Service mistake (empty `<none>` Endpoints), "
            "compare ClusterIP/NodePort/LoadBalancer/Ingress, and understand why default Secrets are NOT encrypted."
        ),
        concepts=[
            "**ClusterIP** = virtual internal cluster IP (`service.ns.svc.cluster.local`); **NodePort** = exposes port `30000-32767` on every worker node; **LoadBalancer** = provisions cloud LB forwarding to NodePort/IPs.",
            "**Ingress** (Nginx/ALB/Gateway API) provides L7 HTTP routing (host/path matching + TLS termination) sharing 1 LoadBalancer across many Services.",
            "Services select Pods via `spec.selector` labels -> populated into `Endpoints`/`EndpointSlice`. Empty Endpoints (`<none>`) = selector mismatch OR failing `readinessProbe`!",
            "Kubernetes `Secret` data is **base64-encoded**, NOT encrypted! Enable KMS/etcd encryption at rest and sync from Vault/AWS Secrets Manager via External Secrets Operator.",
        ],
        deep_sections=[
            sec(
                "1. Service Connectivity Debug Flow (`svc` -> `ep` -> `targetPort`)",
                "Never guess why a Service returns `Connection refused` — check the exact 3 fields below in 10 seconds.",
                example="# 1. Check Service selector vs targetPort:\n$ kubectl describe svc sre-nginx-svc -n sre-practice\nSelector:   app=sre-nginx\nPort:       80/TCP -> TargetPort: 80/TCP\nEndpoints:  10.42.0.14:80,10.42.0.15:80   # <-- If <none>, traffic NEVER reaches pods!",
            ),
        ],
        architecture="Client -> Ingress (L7 Host/Path + TLS) -> Service (ClusterIP/NodePort) -> Endpoints -> Pod targetPort",
        commands=[
            {"cmd": "kubectl apply -f /lab/k8s-demo/configmap-secret.yaml && kubectl get svc,ep,cm,secret -n sre-practice", "explain": "Deploy ConfigMap & Secret and verify Service Endpoints in sre-practice", "cwd": "/lab/k8s-demo"},
            {"cmd": "kubectl describe svc sre-nginx-svc -n sre-practice", "explain": "Verify Service selector labels match Pods and Endpoints IPs are populated", "cwd": "/lab/k8s-demo"},
        ],
        production_use_case="Exposing internal microservices cleanly while isolating TLS termination and external secrets governance.",
        scenarios=[
            scenario(
                "New Service Deploys Cleanly (`Pods 3/3 Running`), Yet `curl http://svc` Returns `Connection Refused`",
                "Pods are Running and Ready, `kubectl get svc` shows a valid ClusterIP, yet every caller gets `Connection refused`.",
                "kubectl get endpoints <svc> -n prod ; kubectl get svc <svc> -o yaml ; kubectl get pods --show-labels",
                "`kubectl get endpoints` prints `<none>` because `Service.spec.selector` had `app: checkout-api` while the Pod template had `app: checkout` (OR `targetPort: 8080` instead of container's listening port `8000`)!",
                "Align `Service.spec.selector` with Pod template labels and match `targetPort` to `containerPort` (`ss -tulnp`).",
            ),
        ],
        troubleshooting=["Updating a `ConfigMap`/`Secret` mounted as `envFrom` does NOT update running container environment variables until Pods restart (use Reloader or rollout restart)."],
        interview_qa=[
            qa("ClusterIP vs NodePort vs LoadBalancer vs Ingress?", "ClusterIP is internal cluster-only virtual IP. NodePort opens a static high port (`30000-32767`) across all nodes. LoadBalancer provisions a cloud L4/L7 LB pointing at the Service. Ingress is an L7 HTTP/HTTPS router mapping hostnames/paths to internal Services behind a single LB.", "basic"),
            qa("Why did updating a Kubernetes Secret not change the API key inside already-running Pods?", "Environment variables (`envFrom`/`valueFrom`) are injected strictly at container startup and never hot-reloaded. Volume-mounted Secrets DO eventually sync (~60–90s kubelet sync unless `subPath` was used!), though the app still needs SIGHUP/file watch to reload.", "senior"),
        ],
        assignment_items=[
            "Apply /lab/k8s-demo/configmap-secret.yaml and inspect svc, endpoints, cm, secret",
            "Explain the 2 reasons kubectl get endpoints returns <none>",
            "Explain base64 Secrets risk + why env vars don't hot-reload without Pod restart",
        ],
        revision=["Empty Endpoints = label mismatch or failed readiness", "Secrets = base64 (encrypt etcd + ESO/Vault)", "subPath mounts & env vars do NOT hot-reload"],
        interview_sim=[
            sim("A Service `payments-svc` has `Pods 4/4 Running` yet `kubectl get ep payments-svc` shows `<none>`. List the exact causes.", ["Selector label typo vs Pod metadata.labels", "ReadinessProbe failing (Pod Ready 0/1)", "publishNotReadyAddresses=false (default)"]),
            sim("Why does mounting a ConfigMap with `subPath: config.yaml` block automatic hot-reloading, whereas mounting the directory `/etc/app/` DOES update?", ["subPath bind-mounts a single inode/file snapshot; directory mounts update the kubelet `..data` symlink atomically"]),
            sim("What is a Headless Service (`clusterIP: None`) and why do Kafka/Cassandra/StatefulSets require it?", ["Returns individual Pod IPs as DNS A records so clients connect directly to pod-0, pod-1 instead of load-balancing randomly"]),
            sim("Compare `externalTrafficPolicy: Cluster` vs `Local` on a NodePort/LoadBalancer Service.", ["Cluster SNATs client IP and can hop across nodes; Local preserves real client IP and routes only to pods on that node"]),
            sim("How should teams handle Kubernetes Secrets in GitOps repositories (`ArgoCD`) safely?", ["Never commit raw base64 Secrets to Git! Use SealedSecrets, SOPS, or External Secrets Operator pulling from Vault/AWS Secrets Manager"]),
        ],
    ),

    make_day(
        day=26,
        phase=5,
        title="StatefulSets, DaemonSets, PV, PVC & StorageClasses",
        subtitle="Sticky Pod Identities, Headless DNS, Per-Node Agents & Dynamic Volume Provisioning",
        goal="Run stateful workloads (Kafka/DBs) and node-level observability agents safely on Kubernetes",
        objective=(
            "Know why Deployments break stateful clusters (shared PVCs/random Pod names), use StatefulSets + Headless Services + `volumeClaimTemplates`, "
            "run per-node collectors with DaemonSets, and debug `Pending` PVCs (`WaitForFirstConsumer`)."
        ),
        concepts=[
            "**Deployment** treats Pods as cattle with random hashes sharing 1 PVC template; **StatefulSet** gives deterministic ordinals (`kafka-0`, `kafka-1`), predictable Headless DNS (`kafka-0.kafka-hl.ns.svc`), ordered start/termination, and a dedicated persistent PVC per replica via `volumeClaimTemplates`.",
            "**DaemonSet** ensures 1 Pod runs on every matching Worker Node (Fluentd log shippers, Prometheus `node_exporter`, CNI plugins).",
            "**StorageClass** enables dynamic provisioning when a user submits a **PVC** (`ReadWriteOnce` RWO single-node block vs `ReadWriteMany` RWX shared NFS/EFS).",
        ],
        deep_sections=[
            sec(
                "1. Kubernetes Dynamic Storage Lifecycle & Access Modes",
                "Choosing `ReadWriteOnce` (`RWO`) for a multi-replica Deployment causes pods scheduled on different worker nodes to fail attaching the same block volume (`Multi-Attach error`).",
                table={
                    "headers": ["Access Mode", "Meaning", "Backed By & Typical Usage"],
                    "rows": [
                        ["ReadWriteOnce (RWO)", "Mounted read-write by ONE node at a time", "AWS EBS, GCE PD, OrbStack `local-path` (StatefulSets/DBs)"],
                        ["ReadWriteMany (RWX)", "Mounted read-write across MANY nodes simultaneously", "AWS EFS, NFS, CephFS (shared uploads/ML artifacts)"],
                        ["ReadOnlyMany (ROX)", "Mounted read-only across many nodes", "Shared static model weights / datasets"],
                    ],
                },
            ),
        ],
        architecture="PVC (Claim) -> StorageClass (local-path/ebs-csi) -> PV (Disk) -> StatefulSet Pod (kafka-0 + Headless DNS)",
        commands=[
            {"cmd": "kubectl get storageclass,pv,pvc -A", "explain": "Inspect OrbStack local-path StorageClass and bound PVs/PVCs", "cwd": "/lab/k8s-demo"},
            {"cmd": "kubectl describe sc local-path || kubectl get sc", "explain": "Inspect volumeBindingMode (WaitForFirstConsumer vs Immediate)", "cwd": "/lab/k8s-demo"},
            {"cmd": "kubectl get ds -A", "explain": "Inspect cluster-wide DaemonSets running on nodes", "cwd": "/lab/k8s-demo"},
        ],
        production_use_case="Understanding why production Kafka (KRaft), Prometheus TSDB, and PostgreSQL run as StatefulSets while Fluentd/Node Exporter run as DaemonSets.",
        scenarios=[
            scenario(
                "Scaled Deployment with PVC Fails to Schedule on Node 2 (`Multi-Attach error for volume`)",
                "Pod `web-1` works on Node A, you scale to `replicas: 2`, and `web-2` on Node B gets stuck in `ContainerCreating` with `Multi-Attach error`.",
                "kubectl describe pod web-2 ; kubectl get pvc",
                "A Deployment shares ONE `ReadWriteOnce` (`RWO` EBS) PVC across all replicas, and cloud block storage cannot attach to two different nodes simultaneously.",
                "If pods need independent state (DB/Kafka/Prometheus), convert to a **StatefulSet** with `volumeClaimTemplates` (1 PVC per ordinal); if they must share files across nodes, switch PVC to an **RWX** storage class (EFS/NFS).",
            ),
        ],
        troubleshooting=["PVC says `Pending` with `WaitForFirstConsumer` -> completely normal until a Pod actually references that PVC so scheduler picks the AZ first!"],
        interview_qa=[
            qa("Difference between Deployment, StatefulSet, and DaemonSet?", "Deployments run stateless interchangeable pods. StatefulSets assign stable ordinal names (`-0`, `-1`), Headless DNS, ordered scaling, and individual per-pod PVCs via `volumeClaimTemplates`. DaemonSets run exactly 1 pod per worker node (logging/monitoring/CNI).", "basic"),
            qa("Explain `volumeBindingMode: WaitForFirstConsumer` and why cloud clusters prefer it over `Immediate`.", "Cloud block volumes (EBS) are pinned to a single Availability Zone. `Immediate` might provision the PV in `us-east-1a` while the Pod only fits on a node in `us-east-1b`, making the Pod unschedulable! `WaitForFirstConsumer` delays PV creation until the Scheduler chooses the Pod's node/AZ.", "senior"),
        ],
        assignment_items=[
            "Inspect StorageClasses, PVs, PVCs, and DaemonSets on OrbStack K8s",
            "Explain why RWO PVCs cause Multi-Attach errors on multi-replica Deployments",
            "Explain WaitForFirstConsumer and StatefulSet Headless DNS naming",
        ],
        revision=["Deployment = stateless; StatefulSet = sticky ID+PVC; DaemonSet = 1/node", "RWO = 1 node; RWX = multi-node", "WaitForFirstConsumer prevents AZ mismatch"],
        interview_sim=[
            sim("A StatefulSet pod `db-0` is stuck in `Terminating` because its worker node died cleanly off the network. Why won't Kubernetes automatically reschedule `db-0` on another node?", ["At-most-one semantics prevents split-brain corruption on shared storage; requires explicit node failure confirmation or force-delete ONLY after verifying node is dead"]),
            sim("What `reclaimPolicy` (`Retain` vs `Delete`) should production database StorageClasses use?", ["`Retain` so deleting a PVC by mistake never deletes the underlying EBS/disk volume and data"]),
            sim("Why do DaemonSets bypass the default `kube-scheduler` constraints or use tolerations?", ["Needs to run monitoring/CNI agents even on tainted control-plane or specialized GPU nodes"]),
            sim("How does a client reach `kafka-1` specifically in namespace `prod` via Headless Service `kafka-hl`?", ["kafka-1.kafka-hl.prod.svc.cluster.local"]),
            sim("What causes a PVC to stay `Pending` forever even after a Pod is scheduled?", ["Missing/default StorageClass, insufficient cloud quota, or incompatible accessMode (e.g. requesting RWX on EBS CSI)"]),
        ],
    ),
]

