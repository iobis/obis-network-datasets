import logging
logging_level = logging.INFO
logging_fmt = "%(asctime)s-%(levelname)4.4s-%(name)6.6s-%(message)s"
date_fmt = "%Y-%m-%d %H:%M:%S"
logging.basicConfig(level=logging_level, format=logging_fmt, datefmt=date_fmt)

from obisnd.gbif import get_obis_network_datasets, create_gbif_url
from obisnd.obis import get_obis_datasets, get_obis_blacklist
from obisnd.github import get_github_issues, create_github_issue
from termcolor import colored
from dotenv import load_dotenv


logger = logging.getLogger(__name__)
load_dotenv()


def obis_has_dataset(obis_datasets, obis_blacklist, identifiers):
    for identifier in identifiers:
        if identifier in obis_datasets:
            return(True)
        if identifier in obis_blacklist:
            return(True)
    return(False)


def github_has_issue(github_issues, identifiers):
    for identifier in identifiers:
        for issue in github_issues:
            if issue["body"] is not None and "URLs" in issue["body"]:
                for url in issue["body"]["URLs"]:
                    if identifier == url:
                        return(True)
    return(False)   


def run():

    github_issues = get_github_issues()
    gbif_datasets = get_obis_network_datasets()
    obis_datasets = [dataset["url"] for dataset in get_obis_datasets()]
    obis_blacklist = [dataset["url"] for dataset in get_obis_blacklist()]

    for gbif_dataset in gbif_datasets:
        gbif_url = create_gbif_url(gbif_dataset["key"])
        identifiers = [identifier["identifier"] for identifier in gbif_dataset["identifiers"] if "?r=" in identifier["identifier"]]

        if not identifiers:
            logger.info(colored(f"No IPT URL found for {gbif_url}", "red"))
        else:
            if not obis_has_dataset(obis_datasets, obis_blacklist, identifiers):
                logger.info(colored(f"Dataset not in OBIS: {gbif_url}", "blue"))
                if not github_has_issue(github_issues, identifiers):
                    logger.info(colored(f"Dataset not in GitHub: {gbif_url}", "green"))

                    create_github_issue(gbif_dataset, identifiers)
