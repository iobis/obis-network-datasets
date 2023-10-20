import logging
from obisnd.gbif import get_obis_network_datasets, create_gbif_url
from obisnd.obis import get_obis_datasets, get_obis_blacklist
from obisnd.github import get_github_issues, create_github_issue
from termcolor import colored


logger = logging.getLogger(__name__)


class ObisNetworkDatasets:

    def __init__(self):

        obis_datasets = get_obis_datasets()

        self.github_issues = get_github_issues()
        self.gbif_datasets = get_obis_network_datasets()
        self.obis_datasets = [dataset["url"].replace("https://", "http://") for dataset in obis_datasets if dataset["url"] is not None]
        self.obis_blacklist = [dataset["url"].replace("https://", "http://") for dataset in get_obis_blacklist() if dataset["url"] is not None]
        self.obis_titles = [dataset["title"] for dataset in obis_datasets if dataset["title"] is not None]

    def obis_has_dataset(self, identifiers, title=None):
        for identifier in identifiers:
            if identifier.replace("https://", "http://") in self.obis_datasets:
                return True
            if identifier.replace("https://", "http://") in self.obis_blacklist:
                return True
            if title is not None and title in self.obis_titles:
                return True
        return False

    def normalize_identifier(self, identifier):
        identifier = identifier.replace("https://", "http://")
        if identifier.endswith("/"):
            identifier = identifier[:-1]
        if identifier.startswith("10."):
            identifier = identifier.replace("10.", "https://doi.org/10.")
        return identifier

    def github_has_issue(self, identifiers):
        for identifier in identifiers:
            for issue in self.github_issues:
                if issue["body"] is not None and "URLs" in issue["body"]:
                    for url in issue["body"]["URLs"]:
                        if self.normalize_identifier(identifier) == self.normalize_identifier(url):
                            return True
        return False

    def dataset_is_orphaned(self, gbif_dataset):
        if len([endpoint["url"] for endpoint in gbif_dataset["endpoints"] if endpoint["url"].startswith("https://orphans.gbif.org")]) > 0:
            return True
        return False

    def dataset_has_dwc_endpoint(self, gbif_dataset):
        if len([endpoint["url"] for endpoint in gbif_dataset["endpoints"] if endpoint["type"] == "DWC_ARCHIVE"]) > 0:
            return True
        return False

    def run(self, dry_run=False):
        for gbif_dataset in self.gbif_datasets:
            gbif_url = create_gbif_url(gbif_dataset["key"])
            identifiers = [identifier["identifier"] for identifier in gbif_dataset["identifiers"]]

            if not self.dataset_has_dwc_endpoint(gbif_dataset):
                logger.info(colored(f"No IPT URL found for {gbif_url}", "red"))
            else:
                if not self.obis_has_dataset(identifiers):
                    logger.info(colored(f"Dataset not in OBIS: {gbif_url}", "blue"))
                    if not self.dataset_is_orphaned(gbif_dataset):
                        logger.info(colored(f"Dataset is not orphaned: {gbif_url}", "blue"))
                        if not self.github_has_issue(identifiers):
                            logger.info(colored(f"Dataset not in GitHub: {gbif_url}", "green"))

                            if not dry_run:
                                create_github_issue(gbif_dataset, identifiers)
