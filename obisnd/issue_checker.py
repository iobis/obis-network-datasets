#!/usr/bin/env python3
"""
Check open GitHub issues against the OBIS database and label/close matches.

This module is the counterpart to the issue producer in
:mod:`obisnd`. The producer files new issues for GBIF datasets that
look like they should be in OBIS but aren't yet. Over time, OBIS nodes
endorse those datasets and OBIS harvests them, but the corresponding
issues stay open until something notices. This module is that something.

For each open issue, the script:

  - Searches OBIS for a dataset with the same title.
  - If a title match is found, compares URLs to confirm same source:
    full match (title + URL) → comment, label "In OBIS", and close.
    title match only         → warning comment, leave issue open.
  - If the issue's URLs don't match OBIS but the issue references a
    GBIF UUID, falls back to checking the GBIF DwC-A endpoint against
    OBIS. This catches older issues that were filed before the DwC-A
    URL was written into the issue body.

Environment variables:
    GITHUB_TOKEN  (required) GitHub personal access token with repo scope.

Usage:
    export GITHUB_TOKEN=ghp_xxx

    # Live run against the default repo
    python -m obisnd.issue_checker

    # Safe test run that logs intended actions but makes no changes
    python -m obisnd.issue_checker --dry-run

    # Restrict to a specific issue-number range (inclusive)
    python -m obisnd.issue_checker --issue-range 100 150

    # Run against a different repository
    python -m obisnd.issue_checker --repo someorg/somerepo
"""

import argparse
import os
import re
import sys
import time
import traceback

import requests
from github import Auth, Github

from obisnd.gbif import collect_identifiers
from obisnd.obis import collect_urls
from obisnd.utils import urls_match


# UUID pattern used by both URL extraction and GBIF UUID extraction.
UUID_PATTERN = r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def parse_args():
    """Parse command-line arguments."""
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
# Issue-body parsing
# ---------------------------------------------------------------------------

def extract_urls_from_body(issue_body):
    """Extract URLs and GBIF dataset URLs from an issue body.

    Finds all bare URLs in the text, plus any UUIDs that may be GBIF
    dataset IDs (returned as constructed gbif.org URLs).

    Args:
        issue_body: Raw text of a GitHub issue body. May be None or empty.

    Returns:
        A deduplicated list of URL strings.
    """
    if not issue_body:
        return []

    url_pattern = r'https?://[^\s<>"\')]+|www\.[^\s<>"\')]+'
    urls = re.findall(url_pattern, issue_body)

    uuids = re.findall(UUID_PATTERN, issue_body, re.IGNORECASE)
    for uuid in uuids:
        urls.append(f"https://www.gbif.org/dataset/{uuid}")

    return list(set(urls))


def extract_gbif_uuid_from_body(issue_body):
    """Extract a GBIF dataset UUID from an issue body, if present.

    Prefers a UUID that appears inside a gbif.org URL. Falls back to the
    first bare UUID in the body (issues filed by the producer include a
    'GBIF:' line whose UUID is the only one present).

    Args:
        issue_body: Raw text of a GitHub issue body. May be None or empty.

    Returns:
        The UUID string if found, otherwise None.
    """
    if not issue_body:
        return None

    gbif_url_match = re.search(
        r'gbif\.org/dataset/(' + UUID_PATTERN + r')',
        issue_body,
        re.IGNORECASE,
    )
    if gbif_url_match:
        return gbif_url_match.group(1).lower()

    bare = re.search(UUID_PATTERN, issue_body, re.IGNORECASE)
    if bare:
        return bare.group(0).lower()

    return None


# ---------------------------------------------------------------------------
# GBIF fallback lookup
# ---------------------------------------------------------------------------

def fetch_gbif_identifiers(gbif_uuid):
    """Fetch identifiers for one GBIF dataset, for the cross-check fallback.

    Used when an issue's own URLs don't match OBIS but the issue
    references a GBIF dataset. Returns the same identifier list that
    :func:`obisnd.gbif.collect_identifiers` produces, along with a status
    string so the caller can distinguish "no DwC-A endpoint registered"
    from "couldn't reach GBIF" in its logging.

    Args:
        gbif_uuid: GBIF dataset UUID (string).

    Returns:
        A 2-tuple ``(identifiers, status)``:
            identifiers (list[str]): Normalized identifier URLs from the
                GBIF record (DOI, ``identifiers`` array, DwC-A endpoints).
            status (str): One of 'ok', 'no_dwc_archive', 'not_found',
                'error'. 'no_dwc_archive' specifically means GBIF returned
                a dataset record but no DWC_ARCHIVE endpoint was registered
                on it.
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

        identifiers = collect_identifiers(data)

        has_dwc_archive = any(
            ep.get('type') == 'DWC_ARCHIVE' and ep.get('url')
            for ep in (data.get('endpoints') or [])
        )
        if not has_dwc_archive:
            return identifiers, 'no_dwc_archive'
        return identifiers, 'ok'

    except Exception as e:
        print(f"  Error fetching GBIF dataset {gbif_uuid}: {e}")
        return [], 'error'


# ---------------------------------------------------------------------------
# OBIS lookup
# ---------------------------------------------------------------------------

def find_obis_match(dataset_title, issue_urls):
    """Search OBIS for a dataset by exact title and verify its URLs.

    Performs a case-insensitive exact title match against the OBIS
    /dataset/search2 endpoint, then compares the matched dataset's source
    URLs against URLs extracted from the issue.

    Args:
        dataset_title: The dataset title to search for. Must be a non-empty
            string; otherwise the function returns an error tuple.
        issue_urls: List of URLs extracted from the GitHub issue body,
            used to verify that the OBIS hit refers to the same source.

    Returns:
        A 4-tuple ``(title_match, url_match, dataset_url, obis_urls)``:
            title_match (bool or None): True if exact title match found,
                False if no match, None on error.
            url_match (bool): True if any issue URL matches an OBIS URL.
            dataset_url (str or None): obis.org URL for the matched dataset.
            obis_urls (list[str]): Source URLs reported by OBIS for the
                matched dataset (from :func:`obisnd.obis.collect_urls`).
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

                if result_title.strip().lower() == dataset_title.strip().lower():
                    dataset_id = result.get('id')
                    if dataset_id:
                        dataset_url = f"https://obis.org/dataset/{dataset_id}"
                        obis_urls = collect_urls(result)
                        url_match = urls_match(issue_urls, obis_urls)
                        return True, url_match, dataset_url, obis_urls

        return False, False, None, []

    except Exception as e:
        print(f"  Error searching OBIS: {e}")
        traceback.print_exc()
        return None, None, None, []


# ---------------------------------------------------------------------------
# Per-issue actions
# ---------------------------------------------------------------------------

def close_on_full_match(issue, dataset_url, dry_run):
    """Comment, label, and close an issue that fully matches an OBIS dataset."""
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


def comment_on_title_only_match(issue, dataset_url, issue_urls, obis_urls, dry_run):
    """Add a warning comment when title matches OBIS but URLs do not."""
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
    full_match_issues = []
    title_only_match_issues = []

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

        issue_urls = extract_urls_from_body(issue.body)
        print(f"Found {len(issue_urls)} URLs in issue:")
        for u in issue_urls:
            print(f"  - {u}")

        title_match, url_match, dataset_url, obis_urls = find_obis_match(
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
                close_on_full_match(issue, dataset_url, dry_run)
            else:
                # Title matches but the issue's URLs don't match OBIS.
                # Cross-check via GBIF: if the issue references a GBIF
                # dataset, the GBIF DwC-A endpoint URL is what OBIS would
                # have harvested from, so it may match OBIS even when
                # the issue body's URLs (e.g. a DOI) do not.
                gbif_uuid = extract_gbif_uuid_from_body(issue.body)
                gbif_match = False
                gbif_identifiers = []
                gbif_status = 'no_uuid'

                if gbif_uuid:
                    print(f"\nChecking GBIF identifiers for {gbif_uuid}...")
                    gbif_identifiers, gbif_status = fetch_gbif_identifiers(gbif_uuid)
                    if gbif_status == 'ok':
                        print(f"GBIF identifiers ({len(gbif_identifiers)} total):")
                        for u in gbif_identifiers:
                            print(f"  - {u}")
                        gbif_match = urls_match(gbif_identifiers, obis_urls)
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
                    print(f"\n✓ FULL MATCH (via GBIF): GBIF identifier matches OBIS source URL!")
                    close_on_full_match(issue, dataset_url, dry_run)
                else:
                    title_only_match_issues.append(issue.number)
                    print(f"\n⚠ PARTIAL MATCH: Title matches but URLs don't match (GBIF cross-check did not resolve)")
                    comment_on_title_only_match(
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