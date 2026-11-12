FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    bash coreutils findutils grep gawk sed procps sysstat util-linux \
    tar gzip bzip2 zip unzip cron sudo sqlite3 python3 python3-pip \
    python3-yaml python3-requests bc jq tree less file strace \
    iproute2 net-tools iputils-ping traceroute dnsutils curl wget \
    netcat-openbsd lsof tcpdump nginx apache2-utils openssh-client \
    openssl git ca-certificates gnupg ansible docker.io \
    && rm -rf /var/lib/apt/lists/*

# Install kubectl, helm, and terraform matching container architecture (arm64 / amd64)
RUN ARCH=$(dpkg --print-architecture) \
    && curl -fsSL -o /usr/local/bin/kubectl "https://dl.k8s.io/release/v1.31.2/bin/linux/${ARCH}/kubectl" \
    && chmod +x /usr/local/bin/kubectl \
    && curl -fsSL "https://get.helm.sh/helm-v3.16.2-linux-${ARCH}.tar.gz" -o /tmp/helm.tgz \
    && tar -xzf /tmp/helm.tgz -C /tmp \
    && mv "/tmp/linux-${ARCH}/helm" /usr/local/bin/helm \
    && rm -rf /tmp/helm.tgz "/tmp/linux-${ARCH}" \
    && curl -fsSL "https://releases.hashicorp.com/terraform/1.9.8/terraform_1.9.8_linux_${ARCH}.zip" -o /tmp/tf.zip \
    && unzip -q /tmp/tf.zip -d /usr/local/bin \
    && rm -f /tmp/tf.zip

# Pre-seed local Terraform provider cache so terraform init/plan/apply works instantly offline
RUN mkdir -p /opt/tf-seed && cd /opt/tf-seed \
    && printf 'terraform {\n  required_providers {\n    local = {\n      source = "hashicorp/local"\n      version = "~> 2.5"\n    }\n    null = {\n      source = "hashicorp/null"\n      version = "~> 3.2"\n    }\n  }\n}\n' > main.tf \
    && terraform init -no-color || true

WORKDIR /lab
COPY entrypoint.sh /opt/entrypoint.sh
COPY lab_server.py /opt/lab_server.py
RUN chmod +x /opt/entrypoint.sh

EXPOSE 8090
ENTRYPOINT ["/opt/entrypoint.sh"]

