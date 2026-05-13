import requests
import logging

from obisnd.utils import normalize_url


logger = logging.getLogger(__name__)
session = requests.Session()
session.headers.update({"User-Agent": "iobis/obis-network-datasets"})


def get_paged_results(url, limit=100):
    results = list()
    params = dict(
        offset=0,
        limit=limit
    )
    while True:
        res = session.get(url=url, params=params)
        data = res.json()
        if not data["results"]:
            break
        results.extend(data["results"])
        params["offset"] = params["offset"] + params["limit"]
    return results


def get_obis_network_datasets():
    logger.info("Fetching OBIS network datasets")
    datasets = get_paged_results("https://api.gbif.org/v1/network/2b7c7b4f-4d4f-40d3-94de-c28b6fa054a6/constituents")
    return datasets


def create_gbif_url(dataset_id):
    return f"https://www.gbif.org/dataset/{dataset_id}"


def collect_identifiers(gbif_dataset):
    """Build the list of identifiers that uniquely point to one GBIF dataset.

    Combines three sources from a GBIF dataset record:

    1. The ``identifiers`` array (URLs, DOIs, LSIDs, etc. that GBIF tracks).
    2. The ``doi`` field, if present and not already covered by (1). A
       bare DOI starting with ``10.`` is rewritten as ``https://doi.org/...``.
    3. The URL of every ``DWC_ARCHIVE`` endpoint in the ``endpoints``
       array. This is the archive download URL OBIS would harvest from.
       GBIF stopped auto-populating these into ``identifiers`` for newer
       datasets, so reading from ``endpoints`` is required for reliable
       matching.

    Each URL is normalized via :func:`obisnd.utils.normalize_url`.
    Duplicates are removed while preserving order of first appearance.

    Args:
        gbif_dataset: A single dataset record from the GBIF API,
            typically from ``/v1/dataset/{key}`` or
            ``/v1/network/{key}/constituents``.

    Returns:
        A deduplicated, normalized list of identifier strings.
    """
    identifiers = []

    for entry in gbif_dataset.get("identifiers") or []:
        value = entry.get("identifier")
        if isinstance(value, str) and value:
            identifiers.append(normalize_url(value))

    doi = gbif_dataset.get("doi")
    if isinstance(doi, str) and doi:
        if doi.startswith("10."):
            doi_url = normalize_url(f"https://doi.org/{doi}")
        else:
            doi_url = normalize_url(doi)
        identifiers.append(doi_url)

    for endpoint in gbif_dataset.get("endpoints") or []:
        if endpoint.get("type") == "DWC_ARCHIVE":
            value = endpoint.get("url")
            if isinstance(value, str) and value:
                identifiers.append(normalize_url(value))

    seen = set()
    deduped = []
    for ident in identifiers:
        if ident not in seen:
            seen.add(ident)
            deduped.append(ident)
    return deduped