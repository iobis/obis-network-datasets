import requests
import logging

from obisnd.utils import normalize_url


logger = logging.getLogger(__name__)
session = requests.Session()
session.headers.update({"User-Agent": "iobis/obis-network-datasets"})


def get_obis_datasets():
    logger.info("Fetching OBIS datasets")
    res = session.get(url="https://api.obis.org/dataset/search?limit=100000")
    datasets = res.json()["results"]
    return datasets


def get_obis_blacklist():
    logger.info("Fetching OBIS blacklist")
    res = session.get(url="https://api.obis.org/dataset/blacklist")
    datasets = res.json()["results"]
    return datasets


def collect_urls(obis_dataset):
    """Extract the source URLs OBIS reports for one dataset record.

    Reads the ``url`` (IPT resource page) and ``archive`` (DwC-A endpoint)
    fields. The ``feed`` field is deliberately not consulted: it is a
    nested object holding the IPT-wide RSS feed URL, which is shared by
    every dataset on the same IPT and therefore useless for per-dataset
    identity matching.

    Args:
        obis_dataset: A single record from the OBIS dataset API, typically
            an item from ``/dataset/search`` or ``/dataset/search2``.

    Returns:
        A list of URL strings, normalized via
        :func:`obisnd.utils.normalize_url`. Empty if neither field is
        populated.
    """
    urls = []
    for field in ("url", "archive"):
        value = obis_dataset.get(field)
        if isinstance(value, str) and value:
            urls.append(normalize_url(value))
    return urls