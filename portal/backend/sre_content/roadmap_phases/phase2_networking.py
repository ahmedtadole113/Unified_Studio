"""Phase 2 (Days 11-15): Networking, TCP/TLS, DNS, Load Balancing & Packet Tracing."""

from typing import Dict, List
from .common import make_day, qa, scenario, sec, sim

DAYS_11_TO_15: List[Dict] = [
    make_day(
        day=11,
        phase=2,
        title="OSI Model, TCP/IP, IP Addressing & CIDR Subnetting",
        subtitle="L3/L4/L7 Boundaries, RFC1918 CIDRs, Subnet Masks & Kernel Routing Tables",
        goal="Map infrastructure failures to OSI layers and calculate CIDR ranges confidently",
        objective=(
            "Stop treating networking as guesswork: cleanly separate Layer 2 (ARP/MAC), Layer 3 (IP/CIDR routing), "
            "Layer 4 (TCP/UDP ports), and Layer 7 (HTTP/DNS/gRPC), and master subnetting for VPCs and Kubernetes clusters."
        ),
        concepts=[
            "OSI 7 layers collapse into TCP/IP 4 layers: Link (L2 MAC/ARP), Internet (L3 IP/ICMP), Transport (L4 TCP/UDP ports), Application (L7 HTTP/DNS/TLS).",
            "CIDR `/N` fixes `N` network bits out of 32: `/24` = `2^(32-24)` = 256 IPs (254 usable), `/23` = 512, `/22` = 1024, `/28` = 16 (AWS reserves 5 IPs per subnet!).",
            "RFC1918 Private ranges: `10.0.0.0/8`, `172.16.0.0/12` (`172.16`–`172.31`), `192.168.0.0/16`.",
        ],
        deep_sections=[
            sec(
                "1. OSI Layer Debugging Map for SREs",
                "Knowing which tool tests which OSI layer prevents wasting 30 minutes debugging HTTP headers when Layer 3 routing is broken.",
                table={
                    "headers": ["Layer", "Protocol / Address", "Debug Tool", "Typical Outage"],
                    "rows": [
                        ["L2 Link", "Ethernet / MAC / ARP", "ip neigh, arp -a", "Wrong VLAN or stale ARP cache"],
                        ["L3 Network", "IPv4/IPv6 / ICMP / Routes", "ip route, ping, traceroute", "Overlapping CIDRs, missing IGW/NAT route"],
                        ["L4 Transport", "TCP / UDP / Ports", "nc -zv, ss -tuln, tcpdump", "Security Group drop, port not listening"],
                        ["L7 Application", "HTTP / DNS / TLS / gRPC", "curl -v, dig, openssl", "502/504, expired cert, NXDOMAIN"],
                    ],
                },
                example="# Example: AWS VPC 10.20.0.0/22 split for multi-AZ EKS\nTotal IPs = 2^(32-22) = 1024 (10.20.0.0 - 10.20.3.255)\nSplit into four /24 subnets (256 IPs each):\n  Public-AZ1:  10.20.0.0/24  | Private-AZ1: 10.20.1.0/24\n  Public-AZ2:  10.20.2.0/24  | Private-AZ2: 10.20.3.0/24",
            ),
        ],
        architecture="L7 HTTP -> L4 TCP (Src/Dst Port) -> L3 IP (CIDR / Route Table) -> L2 Ethernet (MAC/ARP) -> Physical/veth0",
        commands=[
            {"cmd": "ip -4 addr show && ip route show", "explain": "Inspect local CIDR prefix and kernel default route", "cwd": "/lab"},
            {"cmd": "python3 -c \"import ipaddress; n=ipaddress.ip_network('10.20.0.0/22'); print('total:', n.num_addresses, 'usable:', n.num_addresses-2, 'first:', n[1], 'last:', n[-2])\"", "explain": "Compute CIDR host capacity and range cleanly in Python", "cwd": "/lab"},
        ],
        production_use_case="Sizing Kubernetes Pod/Service CIDRs (`10.42.0.0/16`) so they never collide with corporate on-prem VPN or Docker bridge ranges.",
        scenarios=[
            scenario(
                "VPC Peering Breaks Half of Pod Traffic Silently",
                "After peering a new EKS cluster (`172.17.0.0/16`) with an on-prem data center, connections from pods time out intermittently.",
                "ip route && kubectl cluster-info dump | grep -i cidr",
                "Default Docker bridge (`172.17.0.0/16`) or VPC CIDR overlapped with the peered network's CIDR, causing asymmetric local routing.",
                "Plan non-overlapping RFC1918 CIDRs across all VPCs, Docker daemons, and K8s `podCIDR`/`serviceCIDR` ranges from Day 1.",
            ),
        ],
        troubleshooting=["Overlapping VPC/Docker/K8s CIDRs silently blackhole return traffic across VPN/peering."],
        interview_qa=[
            qa("Difference between TCP and UDP?", "TCP provides reliable, ordered byte streams via 3-way handshake, sequence/ACK numbers, retransmissions, and flow/congestion control. UDP is stateless and connectionless with minimal header overhead (DNS, RTP, QUIC/HTTP3).", "basic"),
            qa("How many usable host IPs are in a `/26` subnet in standard Linux vs AWS VPC?", "Total IPs = `2^(32-26) = 64`. Standard networking reserves 2 (network + broadcast = 62 usable). Cloud VPCs like AWS reserve 5 IPs per subnet (`+0` network, `+1` router, `+2` DNS, `+3` future, `+255` broadcast), leaving 59 usable.", "senior"),
        ],
        assignment_items=[
            "Map tools (ping, dig, nc, tcpdump, curl, arp) to OSI layers 2, 3, 4, and 7",
            "Calculate subnet mask and usable IPs for 10.20.0.0/22 and /26",
            "Inspect OrbStack container IP and routing table with ip route",
        ],
        revision=["L2=MAC, L3=IP/Route, L4=Port, L7=HTTP/DNS", "RFC1918: 10/8, 172.16/12, 192.168/16", "Never overlap Pod/VPC/Docker CIDRs"],
        interview_sim=[
            sim("You must design subnets for a 2-AZ production Kubernetes cluster expecting 400 Pods and an external RDS tier inside `10.50.0.0/21`. How do you slice CIDRs?", ["Compute /21 = 2048 IPs", "Carve public /25s for ALBs, private /23s for nodes/pods", "Keep reserve room for IP exhaustion"]),
            sim("Explain what happens to ICMP `ping` when a firewall blocks ICMP even though TCP port 443 works.", ["ICMP is L3 control protocol, separate from L4 TCP", "Always verify service port with nc -zv / curl rather than ping alone"]),
            sim("Why can an EKS cluster suddenly stop launching new Pods even when nodes have 60% free CPU & RAM?", ["VPC subnet IP exhaustion (ENI secondary IPs depleted)", "Watch subnet free IPs metric"]),
            sim("Compare TCP vs UDP for Kubernetes CoreDNS queries on port 53.", ["Small DNS lookups use UDP (low latency)", "Large responses (>512B/EDNS) or DNS-over-TCP fall back to TCP 53"]),
            sim("Walk through how a packet chooses an interface using `ip route` (Longest Prefix Match).", ["More specific mask (/24) beats default route (0.0.0.0/0)", "Next-hop gateway ARP resolution"]),
        ],
    ),

    make_day(
        day=12,
        phase=2,
        title="TCP Handshake, Socket States, Firewalls & NAT",
        subtitle="SYN -> SYN-ACK -> ACK, CLOSE_WAIT vs TIME_WAIT, iptables/SG & SNAT/DNAT",
        goal="Trace TCP connection lifecycle, spot connection leaks (`CLOSE_WAIT`), and isolate firewall drops",
        objective=(
            "Master the TCP 3-way handshake and 4-way teardown (`FIN`), distinguish normal `TIME_WAIT` from application-bug `CLOSE_WAIT`, "
            "and understand how Security Groups, `iptables`/`nftables`, and SNAT/DNAT translate packets."
        ),
        concepts=[
            "TCP 3-way handshake: Client `SYN(seq=x)` -> Server `SYN-ACK(seq=y, ack=x+1)` -> Client `ACK(ack=y+1)` (1 RTT before application bytes flow).",
            "`CLOSE_WAIT` = remote closed connection, local app forgot to call `close()` (HTTP/DB pool leak!). `TIME_WAIT` = normal 60s (`2*MSL`) safety wait after active close.",
            "SNAT rewrites source IP (private pods -> NAT Gateway public IP outbound); DNAT rewrites destination IP:port (LoadBalancer/ClusterIP -> Pod IP).",
        ],
        deep_sections=[
            sec(
                "1. TCP Socket States Cheat Table (`ss -tan`)",
                "Checking `ss -tan state <state>` exposes whether a microservice is dropping packets, leaking sockets, or waiting normally on teardown.",
                table={
                    "headers": ["TCP State", "What It Means", "SRE Action"],
                    "rows": [
                        ["LISTEN", "Server bound and accepting SYNs", "Check `0.0.0.0` vs `127.0.0.1`"],
                        ["SYN_SENT", "SYN sent, awaiting SYN-ACK (hanging)", "Firewall/Security Group DROP or dead host"],
                        ["SYN_RECV", "Half-open inbound handshake", "High count = SYN flood or small `somaxconn` backlog"],
                        ["ESTABLISHED", "Active bidirectional stream", "Healthy active traffic"],
                        ["CLOSE_WAIT", "Peer closed, local app hasn't closed FD!", "Code leak (`urllib`/`requests` unclosed) or hung thread!"],
                        ["TIME_WAIT", "Normal 2*MSL cooldown after active close", "Reuse connections (HTTP keep-alive) if >20k ephemeral ports used"],
                    ],
                },
            ),
        ],
        architecture="Client SYN -> [Security Group / SNAT / DNAT] -> Server SYN-ACK -> Client ACK -> ESTABLISHED -> FIN -> TIME_WAIT",
        commands=[
            {"cmd": "nc -zv kafka 9092 && nc -zv prometheus 9090 && nc -zv spark-master 7077", "explain": "Verify L4 TCP 3-way handshake across Kafka, Prometheus & Spark", "cwd": "/lab"},
            {"cmd": "ss -tan | awk 'NR>1 {print $1}' | sort | uniq -c | sort -nr", "explain": "Summarize active TCP socket states across the container", "cwd": "/lab"},
        ],
        production_use_case="Catching HTTP client leaks (`CLOSE_WAIT` accumulation) in Python/Java services and verifying K8s Service DNAT/conntrack limits.",
        scenarios=[
            scenario(
                "API Runs Out of File Descriptors (`Too many open files`) Every 6 Hours",
                "Service latency climbs, `dmesg` or logs show `OSError: [Errno 24] Too many open files`, and restarting temporarily fixes it.",
                "ss -tan state close-wait | wc -l ; lsof -p <pid> | wc -l",
                "`CLOSE_WAIT` shows 4,200 stuck sockets because an HTTP helper opened sessions without a context manager/`close()` after upstream timeouts.",
                "Always enforce HTTP timeouts + shared `httpx.AsyncClient` / `requests.Session` connection pooling so sockets close cleanly and reuse TCP connections.",
            ),
        ],
        troubleshooting=["`SYN_SENT` hangs -> packet dropped silently by SG/NetworkPolicy. `RST` -> immediate port closed."],
        interview_qa=[
            qa("Explain TCP 3-way handshake and TLS handshake order.", "TCP completes 3-way (`SYN`, `SYN-ACK`, `ACK`) first to create a reliable stream. Only AFTER TCP ACK does TLS send `ClientHello` -> `ServerHello` + cert -> ECDHE key exchange (1 RTT in TLS 1.3).", "basic"),
            qa("What is the difference between `CLOSE_WAIT` and `TIME_WAIT`?", "`CLOSE_WAIT` sits on the passive-close side when the peer sent FIN and our local application still hasn't closed its socket (usually an app bug/resource leak). `TIME_WAIT` sits on the active-close side for `2*MSL` (60s) to absorb stray packets before reusing the 4-tuple.", "senior"),
        ],
        assignment_items=[
            "Test TCP reachability across kafka, prometheus, and spark-master using nc -zv",
            "Group live TCP states via ss -tan + awk/sort/uniq",
            "Explain SNAT vs DNAT in Kubernetes ClusterIP and NAT Gateways",
        ],
        revision=["SYN -> SYN-ACK -> ACK", "CLOSE_WAIT = local app leak", "TIME_WAIT = normal 2*MSL wait", "SNAT outbound, DNAT inbound/ClusterIP"],
        interview_sim=[
            sim("You find 8,000 `CLOSE_WAIT` sockets on your Python FastAPI container (`aiops_agent`). What caused this and how do you prove it is a code leak rather than a network outage?", ["Peer already sent FIN; local app never called close()", "Check lsof -p <pid> FDs", "Fix HTTP client pooling & timeouts"]),
            sim("Why can high-churn microservices exhaust ephemeral ports (`32768-60999`) in `TIME_WAIT`, and what is the proper architectural fix?", ["1,000 short HTTP calls/sec * 60s > 28k ports", "Enable HTTP/1.1 Keep-Alive or HTTP/2 multiplexing", "Don't blindly set tcp_tw_recycle (removed in Linux 4.12!)"]),
            sim("Trace a packet from a private EKS Pod (`10.244.1.8`) calling `https://generativelanguage.googleapis.com` through a NAT Gateway.", ["Pod -> veth -> node iptables/nftables MASQUERADE (SNAT to node IP) -> AWS NAT Gateway (SNAT to Elastic IP) -> Internet"]),
            sim("What is `nf_conntrack` table exhaustion in Linux/Kubernetes and how does it look?", ["Kernel drops new connections silently (dmesg: nf_conntrack: table full, dropping packet)", "Raise conntrack_max or reduce high-churn UDP DNS via NodeLocal DNSCache"]),
            sim("Compare stateful Security Groups vs stateless Network ACLs (NACLs).", ["SG tracks return flow automatically; stateless NACL requires explicit ephemeral outbound/inbound return rules"]),
        ],
    ),

    make_day(
        day=13,
        phase=2,
        title="DNS Resolution, CoreDNS, DHCP & ARP Deep Dive",
        subtitle="Recursive -> Root -> TLD -> Authoritative, /etc/resolv.conf, ndots:5 & ARP",
        goal="Trace end-to-end DNS queries and prevent Kubernetes CoreDNS `ndots:5` latency storms",
        objective=(
            "Follow what really happens when a browser or container resolves a domain (`google.com` or `prometheus`), "
            "understand TTL caching, DHCP lease (DORA), ARP MAC mapping, and Kubernetes `ndots:5` search-domain amplification."
        ),
        concepts=[
            "Resolution order per `/etc/nsswitch.conf`: OS/Browser cache -> `/etc/hosts` -> Stub/Recursive Resolver (`/etc/resolv.conf`) -> Root (`.`) -> TLD (`.com`) -> Authoritative NS.",
            "In Kubernetes, `/etc/resolv.conf` defaults to `options ndots:5` + 3 search domains (`ns.svc.cluster.local`, `svc.cluster.local`, `cluster.local`). Any domain with <5 dots triggers up to 4–5 A+AAAA failed queries BEFORE trying the real external domain!",
            "DHCP assigns IPs via DORA (Discover, Offer, Request, Acknowledge); ARP maps L3 IPv4 -> L2 MAC address on the local subnet.",
        ],
        deep_sections=[
            sec(
                "1. Why `api.gemini.google.com` Triggers 8–10 DNS Queries Inside Kubernetes (`ndots:5`)",
                "Count the dots in `generativelanguage.googleapis.com` -> only **2 dots** (`< 5`)! So glibc appends every cluster search suffix before checking the root domain.",
                example="# /etc/resolv.conf inside Pod:\nnameserver 10.96.0.10\nsearch default.svc.cluster.local svc.cluster.local cluster.local\noptions ndots:5\n\n# Fix in high-QPS Pods: add trailing dot (FQDN) or set dnsConfig: options: [{name: ndots, value: '2'}]",
                sre_example="In OrbStack/Kubernetes, adding NodeLocal DNSCache or lowering `ndots:2` can cut CoreDNS CPU by 60% and eliminate intermittent 5s DNS timeouts!",
            ),
        ],
        architecture="/etc/hosts -> /etc/resolv.conf -> CoreDNS / Docker DNS (127.0.0.11) -> Upstream Recursive -> Root -> TLD -> Auth NS",
        commands=[
            {"cmd": "cat /etc/resolv.conf && cat /etc/hosts", "explain": "Inspect container DNS resolver nameserver IP and static hosts map", "cwd": "/lab"},
            {"cmd": "dig prometheus && dig +short kafka", "explain": "Resolve internal A³P service names via embedded container DNS", "cwd": "/lab"},
            {"cmd": "ip neigh || arp -a", "explain": "Inspect Layer-2 IP-to-MAC ARP cache entries", "cwd": "/lab"},
        ],
        production_use_case="Debugging `Temporary failure in name resolution` inside `ai_agent` or CoreDNS spikes in Kubernetes.",
        scenarios=[
            scenario(
                "Random 5-Second Latency Spikes When Pods Call External Gemini/Payment APIs",
                "99% of requests finish in 120ms, but ~1% jump to 5,120ms (`5s + 120ms`) with no CPU/GC spike on the app.",
                "kubectl get pods -n kube-system -l k8s-app=kube-dns ; cat /etc/resolv.conf ; tcpdump port 53",
                "`ndots:5` multiplied UDP DNS QPS against CoreDNS (sending simultaneous IPv4 A + IPv6 AAAA queries on the same socket, hitting Linux conntrack UDP race -> 5s DNS retry timeout!).",
                "Set `dnsConfig: options: [{name: ndots, value: '2'}, {name: single-request-reopen}]` and deploy NodeLocal DNSCache.",
            ),
        ],
        troubleshooting=["Container resolves hostnames by FQDN only -> check `search` domains and `ndots` in `/etc/resolv.conf`."],
        interview_qa=[
            qa("What happens when you open `google.com` in a browser?", "1) Browser/OS cache + `/etc/hosts` check -> Recursive DNS -> Root -> `.com` TLD -> Authoritative NS returns IP. 2) TCP 3-way handshake on `:443`. 3) TLS 1.3 handshake + X.509 cert verification. 4) HTTP GET `/` -> Reverse Proxy/CDN -> Backend -> Response rendered.", "basic"),
            qa("Explain `ndots:5` in Kubernetes and how it causes 5-second DNS tail latency.", "When a hostname has fewer than 5 dots, glibc tries all cluster `search` paths first (`app.ns.svc.cluster.local`, etc.) with both A and AAAA lookups. That amplifies CoreDNS load and hits Linux `nf_conntrack` UDP source-port races, triggering a 5s DNS timeout before retry.", "senior"),
        ],
        assignment_items=[
            "Inspect /etc/resolv.conf, /etc/hosts, and ip neigh inside /lab",
            "Resolve internal A³P services via dig and check TTL/A records",
            "Explain the full google.com DNS->TCP->TLS->HTTP sequence and ndots:5 mitigation",
        ],
        revision=["hosts -> resolv.conf -> Root -> TLD -> Auth", "K8s ndots:5 multiplies DNS queries", "ARP maps IP -> MAC; DHCP = DORA"],
        interview_sim=[
            sim("A service team says 'DNS is slow — calls to `api.partner.com` occasionally take 5.05 seconds'. How do you verify and fix this on Kubernetes?", ["Check /etc/resolv.conf ndots:5", "tcpdump port 53 / CoreDNS metrics", "Add single-request-reopen, ndots:2, NodeLocal DNSCache"]),
            sim("You update a Route53 DNS record pointing `api.example.com` to a new LoadBalancer, but 30% of clients still hit the old IP 20 minutes later. Why?", ["Check old record TTL (e.g. 3600s) + Java JVM/app DNS caching", "Lower TTL 24h BEFORE planned cutover!"]),
            sim("What is the difference between an `A` record, `CNAME` record, and `SRV` record?", ["A = hostname->IPv4; CNAME = alias->canonical hostname (cannot sit at zone apex); SRV = service host + port priority"]),
            sim("Why did `kubectl exec pod -- dig external.com.` (with a trailing dot) return in 2ms while `dig external.com` took 40ms?", ["Trailing dot marks FQDN, bypassing all /etc/resolv.conf search suffixes"]),
            sim("Explain what happens if CoreDNS pods are all scheduled on 1 crashed node.", ["Cluster-wide internal & external DNS fails instantly; deploy >=2 CoreDNS replicas with podAntiAffinity and PDB"]),
        ],
    ),

    make_day(
        day=14,
        phase=2,
        title="SSL/TLS, HTTPS, Reverse Proxy & Nginx Load Balancing",
        subtitle="TLS 1.3 Certificates, X.509 SANs, Nginx Upstreams, 502 vs 504 & `ab` Load Testing",
        goal="Terminate TLS safely, configure Nginx load balancing, and separate `502` vs `504` failures",
        objective=(
            "Understand asymmetric vs symmetric cryptography in TLS, validate X.509 certificate chains and expiry dates with `openssl`, "
            "tune Nginx reverse proxies (`proxy_read_timeout`, keep-alive), and benchmark backend p99 with `ab`."
        ),
        concepts=[
            "TLS uses asymmetric crypto (RSA/ECDSA cert verification + ECDHE key agreement) during handshake ONLY to agree on a fast symmetric session key (AES-GCM/ChaCha20) for data.",
            "Modern clients validate Subject Alternative Names (**SAN**), NOT just Common Name (CN), plus trust chain back to Root CA and system clock validity.",
            "HTTP `502 Bad Gateway` = proxy failed to get a valid response from upstream (upstream crashed, wrong port, connection reset). `504 Gateway Timeout` = upstream accepted TCP connection but took longer than `proxy_read_timeout`.",
        ],
        deep_sections=[
            sec(
                "1. Nginx Reverse Proxy Anatomy & Common Outage Directives",
                "Reading `nginx.conf` reveals whether client IPs are preserved (`X-Forwarded-For`) and why slow AI/database calls trigger 504 errors at exactly 60.0 seconds (Nginx default `proxy_read_timeout`).",
                example="upstream aiops_backend {\n    least_conn;                  # Route to backend with fewest active requests\n    server ai_agent:8000 max_fails=3 fail_timeout=15s;\n    keepalive 32;                # Reuse TCP connections to upstream!\n}\nserver {\n    listen 443 ssl;\n    location / {\n        proxy_pass http://aiops_backend;\n        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;\n        proxy_read_timeout 60s;  # Slow inference > 60s causes 504!\n    }\n}",
            ),
        ],
        architecture="Client HTTPS -> TLS Termination (Nginx/ALB) -> Upstream Pool (round-robin/least_conn + keepalive) -> App (:8000)",
        commands=[
            {"cmd": "cat /lab/nginx-demo/nginx.conf && nginx -t -c /lab/nginx-demo/nginx.conf", "explain": "Inspect and syntax-validate Nginx reverse proxy configuration", "cwd": "/lab"},
            {"cmd": "openssl s_client -connect k8s.orb.local:26443 </dev/null 2>/dev/null | openssl x509 -noout -subject -issuer -dates || openssl version", "explain": "Inspect live Kubernetes API TLS certificate subject, issuer, and expiration dates", "cwd": "/lab"},
            {"cmd": "ab -n 50 -c 5 http://ai_agent:8000/api/health", "explain": "Run Apache Benchmark concurrency load test against A³P AI Agent", "cwd": "/lab"},
        ],
        production_use_case="Benchmarking A³P throughput with `ab` while watching p99 latency & RPS update live in Grafana and preventing TLS cert-expiry outages.",
        scenarios=[
            scenario(
                "Every Gemini Copilot / Report Request > 60 Seconds Returns `504 Gateway Timeout`",
                "Users clicking heavy report exports see `504` at exactly `60.01s` even though backend server logs show the query finished cleanly at `65s`.",
                "curl -w 'http=%{http_code} total=%{time_total}s\\n' ... ; grep -rn 'timeout' /etc/nginx/",
                "Nginx default `proxy_read_timeout 60s` severed the connection while waiting for the backend response.",
                "Fix the slow backend/make long work async (202 Accepted + poll), or intentionally match proxy timeouts above expected SLO limits (`proxy_read_timeout` + `keepalive`).",
            ),
        ],
        troubleshooting=["`502` immediately after deploy -> check upstream port (`ss -tuln`), crashed backend logs, or missing `upstream` keepalive/`Connection \"\"` header."],
        interview_qa=[
            qa("Difference between `502 Bad Gateway` and `504 Gateway Timeout`?", "`502`: reverse proxy connected or tried connecting to upstream and received TCP RST / invalid HTTP / premature EOF (upstream down/crashed). `504`: TCP connected and request sent, but upstream did not respond within `proxy_read_timeout`.", "basic"),
            qa("Why does TLS use both asymmetric and symmetric encryption?", "Asymmetric cryptography (ECDSA/RSA + ECDHE) solves identity verification and key exchange over an untrusted network without pre-shared secrets, but is CPU-expensive. Once agreed, both sides switch to symmetric encryption (AES-GCM) which is ~1000x faster.", "senior"),
            qa("How do you preserve real client IP behind Nginx / Load Balancers?", "Forward `X-Forwarded-For` / `X-Real-IP` headers (or enable `PROXY` protocol at L4), and configure `set_real_ip_from` in Nginx trusting only the Load Balancer CIDR so attackers cannot spoof `X-Forwarded-For`.", "senior"),
        ],
        assignment_items=[
            "Validate /lab/nginx-demo/nginx.conf with nginx -t",
            "Inspect live TLS certificate dates via openssl s_client + x509",
            "Run ab -n 50 -c 5 against http://ai_agent:8000/api/health and read p50/p95/p99",
            "Explain 502 vs 504 and why X-Forwarded-For must only trust known LB CIDRs",
        ],
        revision=["502 = upstream bad/down; 504 = upstream timeout", "Asymmetric handshake -> Symmetric AES data", "Check openssl x509 -dates before expiry"],
        interview_sim=[
            sim("Your Nginx ingress suddenly returns `502 Bad Gateway` to 100% of users right after a Python deployment, yet the container is still `Running`. Walk through your checks.", ["Check upstream port mismatch (8000 vs 8080)", "ss -tulnp inside container (127.0.0.1 vs 0.0.0.0)", "Check Nginx error.log + Readiness probe"]),
            sim("A TLS certificate on `api.prod.com` expired at midnight causing a SEV-1 outage. How do you verify renewal and prevent this permanently?", ["openssl s_client -servername api.prod.com -connect ... | openssl x509 -noout -dates", "Automate via cert-manager/ACME + Prometheus blackbox_exporter alert (<14 days)"]),
            sim("Compare Nginx `round-robin` vs `least_conn` vs `ip_hash` load balancing.", ["round-robin equal distribution; least_conn best when request durations vary wildly; ip_hash sticky (breaks if clients behind corporate NAT)"]),
            sim("Why did `nginx -s reload` succeed cleanly with zero dropped requests, whereas `systemctl restart nginx` caused brief 502s?", ["reload sends SIGHUP to master: spawns new workers on new config while old workers drain active connections gracefully"]),
            sim("What causes `SSL: certificate verify failed (unable to get local issuer certificate)` in Python/curl?", ["Server sent leaf cert without intermediate CA chain! Fix fullchain.pem"]),
        ],
    ),

    make_day(
        day=15,
        phase=2,
        title="Phase 2 Lab: Packet Tracing & Network Debugging",
        subtitle="tcpdump, Wireshark Filters, traceroute, telnet/nc & curl Per-Hop Timing",
        goal="Capture live L3/L4 packets and prove objectively whether latency is network or application",
        objective=(
            "Use `tcpdump` filters without melting production CPU (`-nn`, port/host BPF filters, `-w capture.pcap`), "
            "spot TCP retransmissions (`[TCP Retransmission]`) and MTU issues, and isolate network vs app time with `curl -w`."
        ),
        concepts=[
            "Always run `tcpdump -i any -nn -c 20 port X`: `-nn` disables slow reverse DNS lookups and service-name translation; `-c` caps packets cleanly.",
            "Write `.pcap` on the server (`tcpdump -w /tmp/out.pcap`) and analyze visually in Wireshark locally (`tcp.analysis.retransmission`, `tls.handshake`, `http.response.code >= 500`).",
            "`traceroute`/`mtr` combine ICMP/UDP probes with incrementing IP TTL (`1, 2, 3...`) to spot hop-level packet loss.",
        ],
        deep_sections=[
            sec(
                "1. Essential `tcpdump` Flags & Wireshark Triage Filters",
                "Never capture unfiltered `eth0` traffic on a 10 Gbps production node — always apply a kernel BPF filter (`host ... and port ...`) and packet count limit.",
                table={
                    "headers": ["Command / Filter", "What It Isolates"],
                    "rows": [
                        ["tcpdump -i any -nn -c 20 port 9092", "First 20 packets to/from Kafka without DNS delay"],
                        ["tcpdump -nn 'tcp[tcpflags] & (tcp-syn|tcp-rst) != 0'", "Capture ONLY handshakes (SYN) and resets (RST) — huge signal!"],
                        ["Wireshark: tcp.analysis.retransmission", "Highlights packet loss / congestion forcing TCP retries"],
                        ["Wireshark: tcp.flags.reset == 1", "Instantly spots abrupt connection resets"],
                    ],
                },
            ),
        ],
        architecture="App Call -> curl -w timing -> traceroute (L3 hops) -> tcpdump BPF (-nn -c N) -> Wireshark Retransmission/RST Check",
        commands=[
            {"cmd": "curl -v http://data_generator:8000/health 2>&1 | head -n 22", "explain": "Trace full HTTP connection, request, and response headers", "cwd": "/lab"},
            {"cmd": "timeout 4 tcpdump -i any -nn -c 6 port 8000 || echo 'Capture finished'", "explain": "Capture 6 live packets on port 8000 inside container network", "cwd": "/lab"},
            {"cmd": "traceroute -m 4 data_generator || tracepath data_generator", "explain": "Trace L3 hop path across OrbStack bridge network", "cwd": "/lab"},
        ],
        production_use_case="Settling cross-team blame during outages ('is it the network or the database?') with packet-level timestamps.",
        scenarios=[
            scenario(
                "App Team Blames 'Network Latency' for Slow Kafka/DB Queries",
                "Developers claim the network between `ai_agent` and `data_generator`/DB has 3-second packet lag.",
                "curl -s -w 'connect=%{time_connect} ttfb=%{time_starttransfer}\\n' -o /dev/null ... && tcpdump -i any -nn -c 20 port 8000",
                "`tcpdump` shows `SYN -> SYN-ACK -> ACK` finishing in `0.2 ms` with zero retransmissions, followed by `3.1 seconds` of silence before the backend transmits its HTTP response.",
                "Present exact packet timestamps proving L3/L4 network RTT is sub-millisecond and pinpoint the bottleneck to backend code/DB query execution.",
            ),
        ],
        troubleshooting=["Forgetting `-nn` in `tcpdump` causes false latency and floods DNS servers with PTR lookups for every packet."],
        interview_qa=[
            qa("How do you prove to an application team that a 5-second timeout is application-side vs network-side?", "Run `curl -w` (`time_connect` vs `time_starttransfer`) and `tcpdump -nn`: if the TCP 3-way handshake completes in <1ms with zero retransmissions, and the backend waits 5s before sending `HTTP 200`, the bottleneck is inside the app/DB.", "senior"),
            qa("Why could `traceroute` show `* * *` at hop 4 while hop 5 and the final destination work fine?", "Intermediate core routers frequently rate-limit or drop ICMP `Time Exceeded` generation on their control plane while still forwarding normal data packets at line rate.", "senior"),
        ],
        assignment_items=[
            "Run curl -v and curl -w against data_generator:8000/health",
            "Capture 6 live packets with tcpdump -nn -c 6 port 8000",
            "Explain 3 Wireshark display filters for diagnosing packet loss and resets",
        ],
        revision=["Always use -nn and -c or -w in tcpdump", "SYN/SYN-ACK fast + slow TTFB = app bottleneck", "Traceroute * * * mid-path is often normal ICMP rate limiting"],
        interview_sim=[
            sim("Large HTTP payloads (`>1500 bytes`) time out across a VPN tunnel while small health checks (`200 bytes`) succeed. What L3 issue is this and how do you test it?", ["MTU / Path MTU Discovery blackhole (ICMP Fragmentation Needed blocked!)", "Test with ping -M do -s 1472"]),
            sim("Capture ONLY TCP SYN and RST packets on port 5432 without DNS lookups.", ["tcpdump -i any -nn 'port 5432 and (tcp[tcpflags] & (tcp-syn|tcp-rst) != 0)'"]),
            sim("What does seeing repeated `[TCP Dup ACK]` and `[TCP Retransmission]` in Wireshark indicate?", ["Packet loss or severe buffer congestion causing sender to retransmit unacknowledged segments"]),
            sim("Why should SREs write `-w /tmp/cap.pcap` and open in Wireshark instead of reading verbose text `-A` on a busy server?", ["Kernel ring buffer drops fewer packets when writing raw binary without formatting stdout"]),
            sim("How does `mtr` improve on plain `traceroute`?", ["Combines continuous ping + traceroute per hop, revealing intermittent packet loss percentage at specific hops"]),
        ],
    ),
]

