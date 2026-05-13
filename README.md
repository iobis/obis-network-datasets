# obis-network-datasets

## Overview

[![Watch the overview video](https://img.youtube.com/vi/4U1mjvCpC6s/maxresdefault.jpg)](https://www.youtube.com/watch?v=4U1mjvCpC6s)

## What is this repository?

As reported at the 10th meeting of the IODE Steering Group for OBIS (SG-OBIS-10) [Document link, see Section 3.1, pgs 39–40](https://oceanexpert.org/document/30481), OBIS and GBIF both host large volumes of marine biodiversity data. However, this overlap can lead to duplication and confusion for users.

To address this, the OBIS Secretariat created this repository to track marine datasets that are **tagged in GBIF as part of the OBIS network** but are **not yet available in OBIS**. Each dataset is represented as a GitHub issue so that OBIS nodes can review and endorse them.

## History

In November 2021, GBIF released **IPT version 2.5.2**, which introduced the ability for publishers to link datasets to networks such as OBIS. Datasets marked with the OBIS network tag automatically appear on the [OBIS network page in GBIF](https://www.gbif.org/network/2b7c7b4f-4d4f-40d3-94de-c28b6fa054a6). However, not all of these datasets were flowing into OBIS.

To close this gap, the OBIS Secretariat developed a Python package that uses the GBIF API to detect "missing" datasets and create GitHub issues for nodes to review.

## Workflow

- Each dataset appears here as an issue.
- OBIS nodes are expected to:
  - Monitor these issues.
  - Endorse appropriate datasets.
  - Coordinate with publishers to resolve any quality concerns.
- Once endorsed, the OBIS Secretariat harvests the dataset directly from the source IPT and lists it on the endorsing node's OBIS page.

This process ensures that:
- The **same, best-quality "master copy"** of each dataset flows to both GBIF and OBIS.
- **Duplicate records are avoided**.
- OBIS is **recognized within GBIF as the global marine biodiversity network**.

All OBIS node managers and data managers are encouraged to **watch this repository** and stay engaged in reviewing and endorsing new datasets.

## Assignments

GitHub accounts per OBIS node used to assign datasets:

- AntOBIS: @ymgan
- IndOBIS: @johnny3125
- Caribbean OBIS: @diodon, @cperaltab
- OBIS Japan: @hosonot
- EurOBIS: @cyrilrader
- OBIS Australia: @obisau
- OBIS Deepsea: @haniehsaeedi
- AfrOBIS: @TRasehlomi
- OBIS China: @ZhaocuiMeng
- OBIS Canada: @cornthwaitem
- OBIS Ecuador: @vechocho, @gbif-ec
- OBIS UK: @dblear
- Ocean Tracking Network: @jdpye
- OBIS Brazil: @ClaraBaringoFonseca

To view all open issues **not currently assigned to a node**, use [this filter](https://github.com/iobis/obis-network-datasets/issues?q=is%3Aissue%20state%3Aopen%20no%3Aassignee%20label%3Adataset%20-label%3A%22node%3A%20OBIS%20China%22%20-label%3A%22node%3A%20OBIS%20SEAMAP%22%20-label%3A%22node%3A%20OBIS%20Colombia%22%20-label%3A%22node%3A%20OBIS%20Malaysia%22%20-label%3A%22node%3A%20OBIS%20Deep%20Sea%22%20-label%3A%22node%3A%20OBIS%20Brazil%22%20-label%3A%22node%3A%20OBIS%20Argentina%22%20-label%3A%22node%3A%20OBIS%20Australia%22%20-label%3A%22node%3A%20ESP%20OBIS%22%20-label%3A%22node%3A%20OBIS%20Black%20Sea%22%20-label%3A%22node%3A%20Caribbean%20OBIS%22%20-label%3A%22node%3A%20AfroOBIS%22%20-label%3A%22node%3A%20EurOBIS%22%20-label%3A%22node%3A%20OBIS%20CPPS%22%20-label%3A%22node%3A%20OBIS%20Ecuador%22%20-label%3A%22node%3A%20OBIS%20Norway%22%20-label%3A%22node%3A%20OBIS%20UK%22%20-label%3A%22node%3A%20OBIS%20USA%22%20-label%3A%22node%3A%20SWP%20OBIS%22%20-label%3A%22node%3A%20PEGO-OBIS%22%20-label%3A%22node%3A%20OBIS%20Canada%22).

## Issue checker

A GitHub Action that runs weekly to check whether datasets in open issues already exist in OBIS.

**What it does:**
- Scans open issues for dataset titles and URLs
- Queries the OBIS API for an exact title match
- Compares source URLs between the issue and OBIS
- If the issue's URLs don't match OBIS but the issue references a GBIF dataset, cross-checks the GBIF identifiers (DOI, DwC-A endpoint) against the OBIS source URLs

**Results:**
- **Exact match (title + URL)**: Adds "In OBIS" label, comments with OBIS link, and closes the issue
- **Title match only**: Adds a warning comment showing URL mismatch (issue stays open)
- **No match**: No action taken

**Schedule:** Runs automatically every Sunday at midnight UTC, or can be triggered manually via the Actions tab.

## Running the tools

This repository ships as a Python package with two entry points: the **producer**, which creates new issues for GBIF datasets that aren't in OBIS, and the **issue checker**, which closes issues for datasets that have since been published to OBIS.

### Setup

Create a `.env` file with a `GITHUB_TOKEN` environment variable (a GitHub personal access token with `repo` scope). Install the package:

```bash
pip install -e .
```

### Producer

Creates new issues for GBIF-tagged OBIS-network datasets that aren't yet in OBIS:

```bash
python -m obisnd
```

### Issue checker

Walks open issues and closes any that are now in OBIS. Supports `--dry-run` to log intended actions without making changes:

```bash
python -m obisnd.issue_checker --dry-run
```

Other options: `--issue-range START END`, `--issues N N N`, `--repo owner/name`. When run as a GitHub Action, the token is provided automatically.