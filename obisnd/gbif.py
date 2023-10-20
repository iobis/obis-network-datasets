import requests
import logging

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
