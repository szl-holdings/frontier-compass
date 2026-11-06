# Security Policy

## Trust Tier

**Trust Tier 1** — SZL Holdings is committed to coordinated, responsible disclosure for all SZL Holdings repositories.

## Reporting a Vulnerability

Please report security vulnerabilities to: **security@szlholdings.com**

E-mail is the only channel for this repository. It is private, so GitHub private vulnerability reporting
(security advisories) is not available for it.

Please include:

- A clear description of the issue and its potential impact.
- Steps to reproduce, including any proof-of-concept code, requests, or payloads.
- The affected version, commit SHA, or environment.
- Your name and contact details for follow-up and credit (optional).

## Disclosure Process

We commit to:
- Acknowledging your report within **72 hours**
- Providing an initial assessment within **7 days**
- Disclosing the resolution within **90 days** of report (industry-standard coordinated-disclosure window)

We ask that you give us a reasonable opportunity to investigate and patch before public disclosure. We do not pursue legal action against good-faith security research.

## Supported Versions

| Version | Supported |
|---------|-----------|
| Current main | ✅ |

This repository has no tagged releases yet. Add a row here when the first one is cut.

## Scope

In scope (what this repository contains):

- `tools/compass/szl_frontier_compass.py`, a stdlib-only CLI that fetches and parses untrusted content: pages on
  a-11-oy.com and a11oy.net, the links found on them, the GitHub and Hugging Face APIs, and DNS-over-HTTPS
  answers (cloudflare-dns.com, dns.google).
- Token handling. `GITHUB_TOKEN` / `GH_TOKEN` and `HF_TOKEN` are read from the environment and added to
  api.github.com and huggingface.co `/api/` requests. Token-shaped strings are redacted from fetch errors, findings,
  receipts and issue bodies.
- The opt-in write paths. `--file-issues` refuses to run without `SZL_COMPASS_CONFIRM=FILE_WORK_ORDERS` and a token,
  files at most 50 issues and neutralises @-mentions. `--receipts` appends to a local receipt file.
- `.github/workflows/`. Both workflows set top-level `permissions: contents: read`. Only the CodeQL job adds
  `security-events: write`, to upload its results. The compass workflow checks out with
  `persist-credentials: false`. Also in scope: the hash-locked test dependencies
  (`requirements/frontier-observer-tests.lock`, installed with `--require-hashes`).

Out of scope:

- Issues in the surfaces the compass audits (the two sites, other `szl-holdings` repositories, the `SZLHOLDINGS`
  Hugging Face org). Report those under the org policy linked below.
- Third-party dependencies (please report upstream).
- Social engineering, physical attacks, or denial-of-service against shared infrastructure.
- Findings that require physical access to a user's device.

## Evidence boundary

Compass results are `UNSIGNED_HONEST`: a hash-chained receipt root over the findings, not a signature and not a
DSSE envelope (see `tools/compass/README.md`). A compass report is an observation, not an attestation.

Canonical org policy: https://github.com/szl-holdings/.github/blob/main/SECURITY.md
This file applies that policy to `szl-holdings/frontier-compass`.

## Hall of Thanks

Researchers who responsibly disclose vulnerabilities will be acknowledged here.
