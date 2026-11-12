"""Phase 7 (Days 34-36): Terraform HCL, State/Drift Management & Ansible Idempotency."""

from typing import Dict, List
from .common import make_day, qa, scenario, sec, sim

DAYS_34_TO_36: List[Dict] = [
    make_day(
        day=34,
        phase=7,
        title="Terraform Fundamentals: HCL, Providers, DAG & Plan/Apply",
        subtitle="Providers, Resources, Data Sources, Variables, Outputs & Execution Graph",
        goal="Write and execute clean Terraform configurations (`init`, `validate`, `plan`, `apply`)",
        objective=(
            "Understand how Terraform builds a parallel dependency DAG from HCL declarations, reads `data` sources vs manages `resource` blocks, "
            "and safely previews creations (`+`), in-place updates (`~`), and dangerous replacements (`-/+`) before touching infrastructure."
        ),
        concepts=[
            "Terraform is **declarative IaC**: you declare desired end-state HCL (`main.tf`, `variables.tf`, `outputs.tf`), and Terraform builds a **DAG (Directed Acyclic Graph)** to parallelize independent resources cleanly.",
            "`resource` creates/owns/destroys infrastructure; `data` reads existing read-only external info (e.g., latest AMI ID or existing VPC).",
            "Plan symbols: **`+`** create, **`-`** destroy, **`~`** update in-place (safe), **`-/+`** **destroy and recreate** (OUTAGE RISK on databases/clusters!).",
        ],
        deep_sections=[
            sec(
                "1. Reading `terraform plan` Symbols Before Approving Production Applies",
                "Always read every single line of `terraform plan` — one unnoticed `forces replacement` (`-/+`) on an RDS subnet group or EKS node group deletes live infrastructure!",
                example="# Safe in-place change (~) vs Destructive replace (-/+):\n  ~ update in-place:  tags = { Env = \"prod\" }\n  -/+ destroy & replace: engine_version = \"14\" -> \"15\" # forces replacement!\n\n# Standard CI workflow:\nterraform fmt -check -recursive && terraform validate && terraform plan -out=tfplan",
            ),
        ],
        architecture="*.tf (HCL) -> terraform init (Providers) -> validate -> plan (Graph vs State) -> apply -> terraform.tfstate",
        commands=[
            {"cmd": "terraform version && ls -la /lab/terraform-lab", "explain": "Verify Terraform binary and pre-seeded /lab/terraform-lab files", "cwd": "/lab/terraform-lab"},
            {"cmd": "terraform fmt -check && terraform validate", "explain": "Verify HCL formatting and static type/reference validity", "cwd": "/lab/terraform-lab"},
            {"cmd": "terraform plan -no-color", "explain": "Preview Terraform execution DAG and diff against local state", "cwd": "/lab/terraform-lab"},
            {"cmd": "terraform apply -auto-approve -no-color && cat generated_service.json", "explain": "Apply Terraform configuration locally and inspect generated manifest", "cwd": "/lab/terraform-lab"},
        ],
        production_use_case="Running real, zero-cloud-cost Terraform execution plans and applies locally in `/lab/terraform-lab`.",
        scenarios=[
            scenario(
                "Developer Blindly Runs `terraform apply -auto-approve` — Production Database Deleted!",
                "An engineer changed `availability_zone` on an RDS block and skipped reviewing `terraform plan`.",
                "Always require `terraform plan -out=tfplan` in PR comments + `prevent_destroy = true` lifecycle guard",
                "Changing an immutable attribute forces `-/+ destroy and recreate`, which deletes and rebuilds the resource immediately.",
                "Protect critical stateful resources with `lifecycle { prevent_destroy = true }` and gate production applies on manual PR plan review.",
            ),
        ],
        troubleshooting=["`Error: Provider requirements cannot be satisfied` -> run `terraform init` (in `/lab/terraform-lab`, providers are pre-cached in `/opt/tf-seed`)."],
        interview_qa=[
            qa("What does `terraform plan` actually do under the hood?", "1) Refreshes current real infrastructure state via provider APIs (unless `-refresh=false`). 2) Compares refreshed `tfstate` against desired `.tf` HCL. 3) Builds a topological dependency DAG showing exact `+`, `~`, `-`, or `-/+` operations without changing infrastructure.", "basic"),
            qa("Explain `create_before_destroy` vs `prevent_destroy` lifecycle meta-arguments.", "`prevent_destroy = true` makes Terraform abort any plan that would destroy a stateful resource (RDS/S3). `create_before_destroy = true` provisions the replacement instance/SG first and switches references BEFORE deleting the old one, preventing downtime on replacements.", "senior"),
        ],
        assignment_items=[
            "Run fmt, validate, plan, and apply in /lab/terraform-lab",
            "Re-run plan with -var='slo_target=99.95' to observe in-place ~ diff",
            "Explain +, ~, -, and -/+ plan markers plus lifecycle guards",
        ],
        revision=["fmt -> validate -> plan -> apply", "Watch carefully for -/+ replacement!", "lifecycle { prevent_destroy = true } for DBs"],
        interview_sim=[
            sim("In a Terraform plan output you see `# module.db.aws_db_instance.main must be replaced (-/+)`. How do you stop this from happening automatically in CI?", ["lifecycle { prevent_destroy = true }", "Manual PR plan approval gate before apply"]),
            sim("Compare `count` vs `for_each` when provisioning 3 subnets or IAM users, and why `count` causes outages when removing index 1.", ["`count` indexes by array position [0,1,2] so deleting item 1 shifts item 2->1 and forces destroy/recreate! `for_each` keys by map/set key cleanly"]),
            sim("What is the difference between a `variable` default, `.tfvars`, and `-var` CLI precedence?", ["Env TF_VAR < terraform.tfvars < *.auto.tfvars < -var / -var-file CLI flag"]),
            sim("How does Terraform order creation when Resource B references `aws_vpc.main.id` without an explicit `depends_on`?", ["Implicit dependency detection in HCL builds the DAG automatically"]),
            sim("Why should Terraform CI save `terraform plan -out=tfplan` and run `terraform apply tfplan`?", ["Guarantees exact reviewed diff is executed rather than drifting between PR review and apply"]),
        ],
    ),

    make_day(
        day=35,
        phase=7,
        title="Terraform State, Locking, Drift Detection & Import",
        subtitle="tfstate Mapping, Remote S3 + Lockfile Backends, Out-of-Band Drift & Recovery",
        goal="Detect real manual infrastructure drift, protect remote state with locking, and import resources cleanly",
        objective=(
            "Simulate real infrastructure drift inside `/lab/terraform-lab` and heal it with Terraform, understand why remote state "
            "MUST be encrypted and locked, and learn safe `terraform import` / `removed` / `state mv` operations."
        ),
        concepts=[
            "`terraform.tfstate` maps HCL resource addresses (`local_file.service_manifest`) to real-world IDs and attributes — NEVER commit `tfstate` to Git (contains plaintext secrets/passwords!).",
            "Store state in a **Remote Backend** (S3 + `use_lockfile = true`/DynamoDB, GCS, Terraform Cloud) with **encryption at rest**, versioning, and **state locking** so two engineers never corrupt state concurrently.",
            "Out-of-band console edits create **Drift**: the next `terraform plan` detects the exact mismatch and reconciles it cleanly.",
            "Modern Terraform (`>= 1.5`) supports declarative `import { to = ... id = ... }` and `moved { from = ... to = ... }` blocks reviewed safely in `plan`!",
        ],
        deep_sections=[
            sec(
                "1. Safe State Operations (`state mv`, `import`, `-replace`)",
                "Never hand-edit raw JSON in `terraform.tfstate` — use dedicated CLI commands or declarative blocks so serial numbers and dependency lineages stay valid.",
                table={
                    "headers": ["Need", "Modern Safe Command / Block", "Replaces Legacy Habit"],
                    "rows": [
                        ["Force replace 1 broken VM", "terraform apply -replace='aws_instance.web'", "Replaces deprecated `terraform taint`"],
                        ["Refactor resource into module", "`moved { from = ... to = ... }` block", "Safer & PR-reviewable vs `terraform state mv`"],
                        ["Adopt existing manual resource", "`import { to = ... id = ... }` block", "Generates config + tracks cleanly in PR"],
                        ["Drop from Terraform without deleting", "terraform state rm <addr> (or `removed` block)", "Keeps live resource running while freeing state"],
                    ],
                },
            ),
        ],
        architecture="Live Resource (Manual Edit Drift) <--refresh-- terraform plan (Detects Diff) --apply--> Reconciled State + Lock",
        commands=[
            {"cmd": "terraform state list && terraform output", "explain": "Inspect resources tracked in /lab/terraform-lab state and outputs", "cwd": "/lab/terraform-lab"},
            {"cmd": "echo '{\"drifted\":true}' > generated_service.json && terraform plan -no-color", "explain": "Simulate out-of-band manual drift and watch Terraform detect exact diff", "cwd": "/lab/terraform-lab"},
            {"cmd": "terraform apply -auto-approve -no-color && cat generated_service.json", "explain": "Reconcile live drift back to Git/HCL desired state", "cwd": "/lab/terraform-lab"},
        ],
        production_use_case="Hands-on IaC drift detection & automated remediation matching A³P's environment integrity controls.",
        scenarios=[
            scenario(
                "Emergency Console Fix Left Security Group Port `22` Open to `0.0.0.0/0`!",
                "An engineer opened SSH `0.0.0.0/0` directly in AWS Console during an outage and forgot to close it.",
                "Scheduled nightly CI job: `terraform plan -detailed-exitcode` (Exit `2` alerts Slack/A³P immediately on drift!)",
                "Console changes bypass Git/PR review and leave security holes invisible until the next Terraform apply.",
                "Run automated read-only `terraform plan -detailed-exitcode` drift checks nightly (`exit 2 = drift detected`) and reconcile or PR-codify immediately.",
            ),
        ],
        troubleshooting=["`Error acquiring the state lock` -> check WHO is actively running `apply` in CI before ever touching `terraform force-unlock`!"],
        interview_qa=[
            qa("How do you protect `terraform.tfstate` in a multi-engineer team?", "Use a remote backend (S3 with SSE-KMS encryption + bucket versioning + state locking via `use_lockfile`/DynamoDB, or Terraform Cloud) with strict IAM least privilege — never store `tfstate` locally or in Git because it holds secrets in plaintext.", "senior"),
            qa("How do you detect and handle out-of-band console drift cleanly?", "Run scheduled read-only `terraform plan -detailed-exitcode` (`exit 2` = drift alert). Never blindly run `apply` first — check why the manual emergency change happened, either codify it in HCL via PR or run `apply` to revert unauthorized drift.", "senior"),
        ],
        assignment_items=[
            "Inject manual drift on generated_service.json and observe terraform plan catch it",
            "Reconcile drift back via terraform apply",
            "Explain -replace vs taint, moved blocks, and remote state locking",
        ],
        revision=["Never commit tfstate (contains secrets!)", "S3/GCS backend + encryption + locking", "plan -detailed-exitcode (2 = drift!)"],
        interview_sim=[
            sim("Two engineers run `terraform apply` at the exact same second without remote state locking. What happens?", ["Last writer overwrites tfstate blindly -> orphaned/duplicate cloud resources and corrupted state IDs"]),
            sim("You renamed a resource inside `main.tf` from `aws_s3_bucket.logs` to `aws_s3_bucket.app_logs` and `terraform plan` wants to DESTROY your production bucket and recreate it! How do you refactor with zero destruction?", ["Add a `moved { from = aws_s3_bucket.logs to = aws_s3_bucket.app_logs }` block (or terraform state mv)"]),
            sim("An engineer ran `terraform force-unlock <ID>` while a CI runner was halfway through applying a 20-minute EKS upgrade. Why was that catastrophic?", ["Allowed concurrent apply modifying cluster state mid-flight -> lock conflict & broken state"]),
            sim("How do you bring an existing manually created S3 bucket under Terraform management without recreating it?", ["Use Terraform import block (`import { to = ... id = ... }`) + `terraform plan -generate-config-out=...`"]),
            sim("Compare `terraform state rm` vs `terraform destroy`.", ["state rm stops tracking the resource in tfstate while leaving live cloud resource running; destroy deletes the live cloud resource"]),
        ],
    ),

    make_day(
        day=36,
        phase=7,
        title="Terraform Modules & Ansible Configuration Management",
        subtitle="Reusable Terraform Modules vs Agentless Ansible Playbooks, Inventories & Idempotency",
        goal="Combine Terraform (provisioning) and Ansible (OS/app configuration) with strict idempotency",
        objective=(
            "Know exactly when to use Terraform vs Ansible, structure reusable Terraform modules cleanly, "
            "and write idempotent Ansible playbooks (`--syntax-check`, `--check`, `changed=0` on second run)."
        ),
        concepts=[
            "**Terraform** = declarative, stateful infrastructure provisioning (VPCs, EKS, RDS, DNS, IAM) via API + `tfstate`. **Ansible** = agentless SSH/WinRM configuration management (packages, `sysctl`, `sshd`, files, service restarts).",
            "**Idempotency** means running a playbook 1 time or 50 times yields the identical end state (`changed=0` on repeat runs!). Built-in Ansible modules (`apt`, `copy`, `template`, `systemd`) are idempotent; raw `shell:`/`command:` break idempotency unless guarded with `creates:` or `changed_when:`.",
            "Always run `--syntax-check` and `--check --diff` (dry-run) before applying Ansible changes across a production fleet.",
        ],
        deep_sections=[
            sec(
                "1. Terraform vs Ansible — Clean Responsibility Boundary",
                "Trying to configure `/etc/nginx/nginx.conf` inside Terraform `remote-exec` provisioners or trying to manage VPC routing tables in Ansible creates brittle pipelines. Pair them cleanly!",
                table={
                    "headers": ["Task", "Best Tool", "Why"],
                    "rows": [
                        ["Create VPC, subnets, EKS, RDS, S3", "Terraform", "Dependency DAG + `tfstate` lifecycle tracking"],
                        ["Patch 200 VMs, configure `sysctl`/`nginx`, harden SSH", "Ansible", "Agentless SSH idempotent modules + Jinja2 templates"],
                        ["Deploy containers onto Kubernetes", "Helm + GitOps (ArgoCD)", "Native K8s reconciliation loops"],
                    ],
                },
            ),
        ],
        architecture="Terraform (Provision VMs/Network) -> Inventory -> Ansible (--syntax-check -> --check -> Apply) -> Idempotent Host (changed=0)",
        commands=[
            {"cmd": "ansible all -i /lab/ansible-lab/inventory.ini -m ping", "explain": "Verify Ansible inventory connectivity locally", "cwd": "/lab/ansible-lab"},
            {"cmd": "ansible-playbook -i /lab/ansible-lab/inventory.ini /lab/ansible-lab/playbook.yml --syntax-check", "explain": "Validate Ansible playbook YAML & task syntax", "cwd": "/lab/ansible-lab"},
            {"cmd": "ansible-playbook -i /lab/ansible-lab/inventory.ini /lab/ansible-lab/playbook.yml && cat /lab/ansible-lab/output/status.txt", "explain": "Run Ansible playbook locally and inspect generated status file", "cwd": "/lab/ansible-lab"},
            {"cmd": "ansible-playbook -i /lab/ansible-lab/inventory.ini /lab/ansible-lab/playbook.yml | tail -n 5", "explain": "Re-run playbook immediately and observe changed=0 idempotency!", "cwd": "/lab/ansible-lab"},
        ],
        production_use_case="Maintaining zero configuration drift on Linux nodes and automating repetitive OS hardening out of manual toil.",
        scenarios=[
            scenario(
                "Ansible Playbook Restarts Production Nginx on EVERY Run Even When Nothing Changed!",
                "Running an hourly configuration-compliance playbook causes brief traffic blips across 40 web nodes.",
                "cat playbook.yml ; look for unconditional `systemd: name=nginx state=restarted` vs `handlers`",
                "The task restarted Nginx unconditionally instead of using an Ansible **`notify` handler** triggered only when `nginx.conf` actually changes!",
                "Move service restarts into `handlers:` triggered via `notify: Reload Nginx`, run `nginx -t` first via `validate: 'nginx -t -c %s'` in the `template` module, and use `state: reloaded`.",
            ),
        ],
        troubleshooting=["Ansible hangs asking SSH password -> verify SSH key auth / `ansible_ssh_private_key_file` and `--become` sudo permissions."],
        interview_qa=[
            qa("Terraform vs Ansible — when do you use each?", "Terraform provisions and tracks lifecycle state (`tfstate`) of cloud infrastructure (VPC, subnets, managed DBs, clusters). Ansible configures software, OS packages, files, and patches inside servers agentlessly over SSH using idempotent modules.", "basic"),
            qa("What is idempotency in Ansible and what breaks it?", "Idempotency guarantees repeating an operation produces zero unintended side effects or restarts (`changed=0` when already compliant). Using `shell:`/`command:` modules without `creates:`/`removes:`/`changed_when:` or restarting services unconditionally instead of `notify` handlers breaks idempotency.", "senior"),
        ],
        assignment_items=[
            "Run /lab/ansible-lab/playbook.yml twice and confirm changed=0 on second run",
            "Explain how Ansible handlers + template validate prevent unnecessary service restarts",
            "Design a Terraform module structure (main.tf, variables.tf, outputs.tf, versions.tf)",
        ],
        revision=["Terraform = infra lifecycle; Ansible = OS/config", "Idempotency: 2nd run changed=0", "Use notify handlers + template validate"],
        interview_sim=[
            sim("In Ansible, how do you validate an updated `nginx.conf` Jinja2 template BEFORE replacing the live file and reloading Nginx?", ["template: src=... dest=/etc/nginx/nginx.conf validate='nginx -t -c %s' notify: Reload Nginx"]),
            sim("How do you version and pin Terraform modules across `dev` and `prod` environments so a module refactor doesn't break `prod`?", ["Versioned module Git tags (`?ref=v2.1.0`) or Terraform Registry semver constraints + separate state files/workspaces per env"]),
            sim("Compare Terraform Workspaces vs separate directory-per-environment (`envs/dev`, `envs/prod`) for production isolation.", ["Separate env directories allow divergent configs, distinct backend IAM buckets, and safer blast-radius isolation than shared workspace state"]),
            sim("How does `ansible-vault` protect secrets stored inside Ansible `group_vars`?", ["AES-256 encrypts YAML files/vars at rest; decrypted dynamically in memory via `--vault-id` at runtime"]),
            sim("What is Dynamic Inventory in Ansible?", ["Plugin querying AWS EC2/GCP tags live via API so new autoscaled VMs are targeted automatically without editing static INI files"]),
        ],
    ),
]

