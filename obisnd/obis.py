import requests
import logging


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
