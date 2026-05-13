#!/usr/bin/env python3
"""
Check open GitHub issues against the OBIS database and label/close matches.

This script iterates over open issues in a GitHub repository (default:
iobis/obis-network-datasets), searches the OBIS API for each issue's title,
and takes action based on the result:

  - Full match (title AND a source URL match): adds a comment pointing to
    the OBIS dataset, applies the "In OBIS" label, and closes the issue.
  - Title-only match (URLs do not match): adds a warning comment listing
    both sets of URLs, but leaves the issue open and unlabeled.
  - No title match: logs the result and moves on.

Environment variables:
    GITHUB_TOKEN  (required) GitHub personal access token with repo scope.

Usage:
    export GITHUB_TOKEN=ghp_xxx

    # Live run against the default repo
    python check_title_against_obis.py

    # Safe test run that logs intended actions but makes no changes
    python check_title_against_obis.py --dry-run

    # Restrict to a specific issue-number range (inclusive)
    python check_title_against_obis.py --issue-range 100 150

    # Run against a different repository
    python check_title_against_obis.py --repo someorg/somerepo

Dependencies:
    pip install requests PyGithub
"""

import argparse
import os
import re
import sys
import time
import traceback

import requests
from github import Auth, Github


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def parse_args():
    """Parse command-line arguments.

    Returns:
        argparse.Namespace with attributes: repo, dry_run, issue_range, sleep.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Check open GitHub issues against the OBIS database and "
            "label/close matches."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--repo",
        default="iobis/obis-network-datasets",
        help="GitHub repository in 'owner/name' form.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Log intended actions without making any changes to GitHub. "
            "Can also be enabled by setting the DRY_RUN environment "
            "variable to 'true'."
        ),
    )
    parser.add_argument(
        "--issue-range",
        nargs=2,
        type=int,
        metavar=("START", "END"),
        default=None,
        help="Only check issues whose numbers fall in [START, END] inclusive.",
    )
    parser.add_argument(
        "--issues",
        nargs="+",
        type=int,
        metavar="N",
        default=None,
        help=(
            "Only check the listed issue numbers (space-separated). "
            "Mutually exclusive with --issue-range."
        ),
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=1.0,
        help="Seconds to sleep between issues for rate limiting.",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# URL extraction and matching
# ---------------------------------------------------------------------------

def extract_urls_from_issue(issue_body):
    """Extract all URLs (and GBIF dataset URLs from bare UUIDs) from an issue body.

    Args:
        issue_body: The raw text of a GitHub issue body. May be None or empty.

    Returns:
        A deduplicated list of URL strings. Any UUIDs found in the body are
        also returned as constructed GBIF dataset URLs of the form
        'https://www.gbif.org/dataset/<uuid>'.
    """
    if not issue_body:
        return []

    # Find all URLs in the issue body
    url_pattern = r'https?://[^\s<>"\')]+|www\.[^\s<>"\')]+'
    urls = re.findall(url_pattern, issue_body)

    # Also extract UUIDs that might be GBIF dataset IDs
    uuids = re.findall(UUID_PATTERN, issue_body, re.IGNORECASE)

    # Add GBIF dataset URLs for found UUIDs
    for uuid in uuids:
        urls.append(f"https://www.gbif.org/dataset/{uuid}")

    return list(set(urls))


def check_url_match_simple(issue_urls, obis_urls):
    """Check whether any issue URL matches any OBIS URL (ignoring http vs https).

    Args:
        issue_urls: List of URLs extracted from the GitHub issue.
        obis_urls: List of URLs reported by OBIS for the candidate dataset.

    Returns:
        True if at least one normalized issue URL appears in the normalized
        OBIS URL list; False otherwise.
    """
    if not obis_urls:
        return False

    def normalize_url(url):
        url = url.strip()
        if url.startswith('https://'):
            url = url.replace('https://', 'http://', 1)
        return url

    normalized_issue_urls = [normalize_url(u) for u in issue_urls]
    normalized_obis_urls = [normalize_url(u) for u in obis_urls]

    for issue_url in normalized_issue_urls:
        if issue_url in normalized_obis_urls:
            return True

    return False


# ---------------------------------------------------------------------------
# GBIF lookup
# ---------------------------------------------------------------------------

# Reused by both URL extraction and GBIF UUID extraction.
UUID_PATTERN = r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'


def extract_gbif_uuid(issue_body):
    """Extract the GBIF dataset UUID from an issue body, if one is present.

    Looks for the first UUID associated with a gbif.org URL. If no
    gbif-qualified UUID is found, falls back to the first bare UUID in
    the body (issues created by the GitHub Actions bot include a 'GBIF:'
    line whose UUID is the only one present).

    Args:
        issue_body: Raw text of a GitHub issue body. May be None or empty.

    Returns:
        The UUID string if found, otherwise None.
    """
    if not issue_body:
        return None

    # Prefer a UUID that appears in a gbif.org URL.
    gbif_url_match = re.search(
        r'gbif\.org/dataset/(' + UUID_PATTERN + r')',
        issue_body,
        re.IGNORECASE,
    )
    if gbif_url_match:
        return gbif_url_match.group(1).lower()

    # Fall back to the first bare UUID in the body.
    bare = re.search(UUID_PATTERN, issue_body, re.IGNORECASE)
    if bare:
        return bare.group(0).lower()

    return None


def get_gbif_dwc_archive_urls(gbif_uuid):
    """Fetch DWC_ARCHIVE endpoint URLs for a GBIF dataset.

    Args:
        gbif_uuid: GBIF dataset UUID (string).

    Returns:
        A 2-tuple (urls, status):
            urls (list[str]): DWC_ARCHIVE endpoint URLs from the GBIF
                dataset record. Empty list if none are registered.
            status (str): One of 'ok', 'no_dwc_archive', 'not_found', 'error'.
                Provided so the caller can distinguish "GBIF says this
                dataset has no DWC_ARCHIVE endpoint" (a genuine data gap)
                from "we couldn't reach GBIF" (a transient failure).
    """
    if not gbif_uuid:
        return [], 'error'

    api_url = f"https://api.gbif.org/v1/dataset/{gbif_uuid}"
    try:
        response = requests.get(api_url, timeout=10)
        if response.status_code == 404:
            return [], 'not_found'
        response.raise_for_status()
        data = response.json()

        endpoints = data.get('endpoints') or []
        dwc_urls = [
            ep.get('url')
            for ep in endpoints
            if ep.get('type') == 'DWC_ARCHIVE' and ep.get('url')
        ]

        if not dwc_urls:
            return [], 'no_dwc_archive'
        return dwc_urls, 'ok'

    except Exception as e:
        print(f"  Error fetching GBIF dataset {gbif_uuid}: {e}")
        return [], 'error'


# ---------------------------------------------------------------------------
# OBIS lookup
# ---------------------------------------------------------------------------

def search_obis_dataset(dataset_title, issue_urls):
    """Search OBIS for a dataset by exact title match and verify its URLs.

    Performs a case-insensitive exact title match against the OBIS
    /dataset/search2 endpoint, then compares the matched dataset's source
    URLs against URLs extracted from the issue.

    Args:
        dataset_title: The dataset title to search for. Must be a non-empty
            string; otherwise the function returns an error tuple.
        issue_urls: List of URLs extracted from the GitHub issue body,
            used to verify that the OBIS hit refers to the same source.

    Returns:
        A 4-tuple (title_match, url_match, dataset_url, obis_urls):
            title_match (bool or None): True if an exact title match was
                found in OBIS, False if no match, None on error.
            url_match (bool): True if any issue URL matches an OBIS URL.
            dataset_url (str or None): obis.org URL for the matched dataset.
            obis_urls (list[str]): Source URLs reported by OBIS for the
                matched dataset (drawn from 'url', 'feed', and 'archive'
                fields of the search result).
    """
    if not dataset_title or not isinstance(dataset_title, str):
        print(f"  ERROR: Invalid dataset_title: {type(dataset_title)}")
        return None, None, None, []

    url = "https://api.obis.org/dataset/search2"
    params = {'q': dataset_title, 'size': 20}

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        if data and 'results' in data:
            for result in data['results']:
                result_title = result.get('title')
                if not result_title or not isinstance(result_title, str):
                    continue

                # Case-insensitive exact title match
                if result_title.strip().lower() == dataset_title.strip().lower():
                    dataset_id = result.get('id')
                    if dataset_id:
                        dataset_url = f"https://obis.org/dataset/{dataset_id}"

                        obis_urls = []
                        for field in ('url', 'feed', 'archive'):
                            value = result.get(field)
                            if value and isinstance(value, str):
                                obis_urls.append(value)

                        url_match = check_url_match_simple(issue_urls, obis_urls)
                        return True, url_match, dataset_url, obis_urls

        return False, False, None, []

    except Exception as e:
        print(f"  Error searching OBIS: {e}")
        traceback.print_exc()
        return None, None, None, []


# ---------------------------------------------------------------------------
# Per-issue handling
# ---------------------------------------------------------------------------

def handle_full_match(issue, dataset_url, dry_run):
    """Comment, label, and close an issue that fully matches an OBIS dataset.

    Args:
        issue: A PyGithub Issue object.
        dataset_url: The obis.org URL pointing to the matched dataset.
        dry_run: If True, log intended actions without modifying GitHub.
    """
    if dry_run:
        print(f"\n[DRY RUN] Would add comment:")
        print(f"  'Dataset is published to OBIS: {dataset_url}'")
        print(f"[DRY RUN] Would add label: 'In OBIS'")
        print(f"[DRY RUN] Would close issue")
        return

    existing_comments = [
        c for c in issue.get_comments()
        if 'Dataset is published to OBIS:' in c.body
    ]

    if not existing_comments:
        issue.create_comment(f"Dataset is published to OBIS: {dataset_url}")
        print(f"\n✓ Added comment")
    else:
        print(f"\nℹ Already commented")

    issue.add_to_labels("In OBIS")
    print(f"✓ Added 'In OBIS' label")

    issue.edit(state='closed')
    print(f"✓ Closed issue")


def handle_title_only_match(issue, dataset_url, issue_urls, obis_urls, dry_run):
    """Add a warning comment to an issue whose title matches but URLs do not.

    Args:
        issue: A PyGithub Issue object.
        dataset_url: The obis.org URL of the title-matched OBIS dataset.
        issue_urls: List of URLs extracted from the issue body.
        obis_urls: List of source URLs reported by OBIS for the dataset.
        dry_run: If True, log intended actions without modifying GitHub.
    """
    if dry_run:
        print(f"\n[DRY RUN] Would add comment about title match but no URL match")
        print(f"[DRY RUN] Would NOT add 'In OBIS' label")
        print(f"[DRY RUN] Would NOT close issue")
        return

    existing_comments = [
        c for c in issue.get_comments()
        if 'title matches a dataset in OBIS' in c.body
    ]

    if existing_comments:
        print(f"\nℹ Already commented")
        return

    comment_body = (
        f"⚠️ The title matches a dataset in OBIS, but the source URLs "
        f"don't match:\n\n"
        f"**OBIS Dataset:** {dataset_url}\n\n"
        f"**Issue URLs:**\n"
        + "\n".join(f"- {u}" for u in issue_urls)
        + "\n\n**OBIS URLs:**\n"
        + "\n".join(f"- {u}" for u in obis_urls)
        + "\n"
    )
    issue.create_comment(comment_body)
    print(f"\n✓ Added warning comment")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    """Entry point: parse args, fetch issues, and process each one."""
    args = parse_args()

    # Allow DRY_RUN env var as a fallback for backwards compatibility.
    dry_run = args.dry_run or os.environ.get('DRY_RUN', 'false').lower() == 'true'

    if dry_run:
        print("=" * 60)
        print("🔍 DRY RUN MODE - No changes will be made to GitHub")
        print("=" * 60)

    github_token = os.environ.get('GITHUB_TOKEN')
    if not github_token:
        print("ERROR: GITHUB_TOKEN environment variable not found", file=sys.stderr)
        sys.exit(1)

    auth = Auth.Token(github_token)
    g = Github(auth=auth)
    repo = g.get_repo(args.repo)

    # Ensure the label exists (only if not dry run)
    if not dry_run:
        try:
            repo.get_label("In OBIS")
            print("Label 'In OBIS' exists")
        except Exception:
            print("Creating label 'In OBIS'")
            repo.create_label("In OBIS", "1d76db", "Dataset already exists in OBIS")

    print("Fetching open issues...")
    open_issues = list(repo.get_issues(state='open'))
    open_issues = [issue for issue in open_issues if not issue.pull_request]

    if args.issue_range and args.issues:
        print("ERROR: --issue-range and --issues are mutually exclusive.",
              file=sys.stderr)
        sys.exit(2)

    if args.issue_range:
        start, end = args.issue_range
        open_issues = [i for i in open_issues if start <= i.number <= end]
        print(f"Restricted to issues #{start}-#{end}")

    if args.issues:
        wanted = set(args.issues)
        open_issues = [i for i in open_issues if i.number in wanted]
        found_numbers = {i.number for i in open_issues}
        missing = sorted(wanted - found_numbers)
        print(f"Restricted to {len(wanted)} explicitly-listed issues")
        if missing:
            print(f"  Note: {len(missing)} requested issue(s) not in open list "
                  f"(closed, missing, or PR): "
                  + ", ".join(f"#{n}" for n in missing))

    print(f"Found {len(open_issues)} open issues (excluding PRs)\n")

    checked_count = 0
    full_match_issues = []        # issue numbers where title + URL matched
    title_only_match_issues = []  # issue numbers where only the title matched

    for issue in open_issues:
        label_names = [label.name for label in issue.labels]
        if "In OBIS" in label_names:
            print(f"Skipping issue #{issue.number} (already labeled 'In OBIS')")
            continue

        if issue.state != 'open':
            print(f"Skipping issue #{issue.number} (not open: {issue.state})")
            continue

        dataset_title = issue.title
        print(f"\n{'='*60}")
        print(f"Issue #{issue.number}: {dataset_title}")
        print(f"{'='*60}")

        issue_urls = extract_urls_from_issue(issue.body)
        print(f"Found {len(issue_urls)} URLs in issue:")
        for u in issue_urls:
            print(f"  - {u}")

        title_match, url_match, dataset_url, obis_urls = search_obis_dataset(
            dataset_title, issue_urls
        )

        if title_match is True:
            print(f"\nOBIS Dataset: {dataset_url}")
            print(f"OBIS URLs found ({len(obis_urls)} total):")
            if obis_urls:
                for u in obis_urls:
                    print(f"  - {u}")
            else:
                print(f"  (No URLs found in OBIS dataset info)")

            if url_match:
                full_match_issues.append(issue.number)
                print(f"\n✓ FULL MATCH: Title and URL match!")
                handle_full_match(issue, dataset_url, dry_run)
            else:
                # Title matches but the issue's URLs don't match OBIS.
                # Cross-check via GBIF: if the issue references a GBIF
                # dataset, the GBIF DWC_ARCHIVE endpoint URL is what OBIS
                # actually harvests from, so it may match the OBIS URLs
                # even when the issue body's URLs (e.g. a DOI) do not.
                gbif_uuid = extract_gbif_uuid(issue.body)
                gbif_match = False
                gbif_dwc_urls = []
                gbif_status = 'no_uuid'

                if gbif_uuid:
                    print(f"\nChecking GBIF DWC_ARCHIVE endpoint for {gbif_uuid}...")
                    gbif_dwc_urls, gbif_status = get_gbif_dwc_archive_urls(gbif_uuid)
                    if gbif_status == 'ok':
                        print(f"GBIF DWC_ARCHIVE URLs ({len(gbif_dwc_urls)} total):")
                        for u in gbif_dwc_urls:
                            print(f"  - {u}")
                        gbif_match = check_url_match_simple(gbif_dwc_urls, obis_urls)
                    elif gbif_status == 'no_dwc_archive':
                        print(f"  GAP: GBIF dataset has no DWC_ARCHIVE endpoint registered")
                    elif gbif_status == 'not_found':
                        print(f"  GAP: GBIF dataset {gbif_uuid} not found (404)")
                    else:
                        print(f"  GAP: error retrieving GBIF dataset {gbif_uuid}")
                else:
                    print(f"\n  GAP: no GBIF UUID found in issue body")

                if gbif_match:
                    full_match_issues.append(issue.number)
                    print(f"\n✓ FULL MATCH (via GBIF): GBIF DWC_ARCHIVE URL matches OBIS source URL!")
                    handle_full_match(issue, dataset_url, dry_run)
                else:
                    title_only_match_issues.append(issue.number)
                    print(f"\n⚠ PARTIAL MATCH: Title matches but URLs don't match (GBIF cross-check did not resolve)")
                    handle_title_only_match(
                        issue, dataset_url, issue_urls, obis_urls, dry_run
                    )

        elif title_match is False:
            print(f"\n✗ No title match found in OBIS")
        else:
            print(f"\n⚠ Error checking OBIS")

        checked_count += 1
        time.sleep(args.sleep)

    print(f"\n{'='*60}")
    print(f"SUMMARY")
    print(f"{'='*60}")
    print(f"Checked: {checked_count} open issues")
    print(f"Full matches (title + URL): {len(full_match_issues)}")
    if full_match_issues:
        print("  " + ", ".join(f"#{n}" for n in full_match_issues))
    print(f"Partial matches (title only): {len(title_only_match_issues)}")
    if title_only_match_issues:
        print("  " + ", ".join(f"#{n}" for n in title_only_match_issues))
    if dry_run:
        print(f"\n🔍 DRY RUN - No actual changes were made")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()