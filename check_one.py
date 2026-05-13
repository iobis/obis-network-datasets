"""
Local dry-run check for a single GBIF dataset.

Usage:
    python check_one.py 3f8c5321-4081-46fc-84ef-27c12735c3a5

Fetches the dataset from GBIF, runs the same identifier-building and
OBIS/GitHub-dedup logic that ObisNetworkDatasets.run() uses, and prints
what the resulting GitHub issue body would look like. Does NOT post to
GitHub.
"""

import sys
import requests
import yaml

from obisnd import ObisNetworkDatasets
from obisnd.gbif import create_gbif_url


def fetch_one_gbif_dataset(dataset_uuid):
    url = f"https://api.gbif.org/v1/dataset/{dataset_uuid}"
    res = requests.get(url, headers={"User-Agent": "iobis/obis-network-datasets"})
    res.raise_for_status()
    return res.json()


def main():
    if len(sys.argv) < 2:
        print("Usage: python check_one.py <dataset_uuid> [--show-body]")
        sys.exit(1)

    dataset_uuid = sys.argv[1]

    print(f"Fetching GBIF dataset {dataset_uuid} ...")
    gbif_dataset = fetch_one_gbif_dataset(dataset_uuid)

    print("Loading OBIS datasets, blacklist, and existing GitHub issues (this takes a minute) ...")
    ond = ObisNetworkDatasets()

    # Replicate the identifier-building logic from run() exactly.
    identifiers = [i["identifier"] for i in gbif_dataset["identifiers"]]
    if gbif_dataset.get("doi") is not None:
        doi_url = ond.normalize_identifier(gbif_dataset["doi"])
        if doi_url not in identifiers:
            identifiers.append(doi_url)
    for endpoint in gbif_dataset.get("endpoints", []):
        if endpoint.get("type") == "DWC_ARCHIVE" and endpoint.get("url") is not None:
            if endpoint["url"] not in identifiers:
                identifiers.append(endpoint["url"])

    print("\n=== Identifiers that would be checked / written ===")
    for i in identifiers:
        print(f"  - {i}")

    has_dwc = ond.dataset_has_dwc_endpoint(gbif_dataset)
    is_orphaned = ond.dataset_is_orphaned(gbif_dataset)
    in_obis = ond.obis_has_dataset(identifiers)
    in_github = ond.github_has_issue(identifiers)

    print("\n=== Checks ===")
    print(f"  Has DwC-A endpoint:    {has_dwc}")
    print(f"  Is orphaned:           {is_orphaned}")
    print(f"  Already in OBIS:       {in_obis}")
    print(f"  Already has GH issue:  {in_github}")

    would_create = has_dwc and not in_obis and not is_orphaned and not in_github

    print(f"\n=== Decision ===")
    print(f"  Would create new issue: {would_create}")

    if would_create or "--show-body" in sys.argv:
        props = [
            {"title": gbif_dataset["title"]},
            {"GBIF": create_gbif_url(gbif_dataset["key"])},
            {"created": gbif_dataset["created"]},
            {"URLs": identifiers},
        ]
        print("\n=== Issue body that would be posted ===")
        print(yaml.dump(props))


if __name__ == "__main__":
    main()
