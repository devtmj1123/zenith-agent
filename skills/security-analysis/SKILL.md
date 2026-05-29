---
name: security-analysis
description: Use when analyzing malware, assessing vulnerabilities, reviewing security configurations, threat modeling, or conducting any defensive security research
---

# Security Analysis

## Tools

`search` — CVE databases, threat intelligence, security advisories
`scrape` — extract vulnerability details, exploit analysis, patch notes
`fetch` — retrieve security resources, configuration files
`run_command` — run security tools (nmap, hash analysis, file inspection)
`code_exec` — static analysis, pattern matching, deobfuscation
`read_file` — examine suspicious files, logs, configurations

## Methodology

### Threat Modeling
- Identify assets: what needs protection?
- Identify threats: who wants to attack and how?
- Map attack surface: network, application, physical, social.
- Prioritize by likelihood × impact.
- Document in STRIDE format: Spoofing, Tampering, Repudiation, Information disclosure, DoS, Elevation of privilege.

### Vulnerability Assessment
- Search CVE databases for known vulnerabilities in target software.
- Check NVD, Exploit-DB, vendor security advisories.
- Classify by CVSS score: Critical (9+), High (7-8.9), Medium (4-6.9), Low (<4).
- Verify if vulnerability is exploitable in the specific environment.
- Check if patches exist and are applied.

### Malware Analysis (Static)
- Compute hashes: MD5, SHA-256 for identification.
- Search VirusTotal, MalwareBazaar for known signatures.
- Extract strings: URLs, IPs, registry keys, mutex names.
- Check file headers, sections, imports for anomalies.
- Identify packers or obfuscation techniques.

### Malware Analysis (Dynamic — Sandbox Only)
- Only in isolated sandbox environments.
- Monitor: file system changes, registry modifications, network connections.
- Capture IOCs: C2 servers, domains, file drops.
- Document behavior timeline.

### Log Analysis
- Parse logs for anomalies: failed logins, unusual IPs, privilege escalation.
- Correlate events across multiple log sources.
- Identify timeline of compromise.
- Extract IOCs for threat hunting.

## Scope

- Defensive security only — find vulnerabilities to fix them.
- Never create exploits for unauthorized use.
- Never assist with attacks on systems without explicit written permission.
- Report findings responsibly with remediation guidance.

## Output Format

- Executive summary: what, impact, urgency.
- Technical details: vulnerability description, reproduction steps, evidence.
- Remediation: specific fix, workarounds if patch unavailable.
- References: CVE IDs, vendor advisories, relevant research.
