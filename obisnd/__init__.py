import logging
from obisnd.gbif import get_obis_network_datasets, create_gbif_url, collect_identifiers
from obisnd.obis import get_obis_datasets, get_obis_blacklist, collect_urls
from obisnd.github import get_github_issues, create_github_issue
from obisnd.utils import urls_match
from termcolor import colored


logger = logging.getLogger(__name__)


class ObisNetworkDatasets:

    def __init__(self):

        obis_datasets = get_obis_datasets()

        self.github_issues = get_github_issues()
        self.gbif_datasets = get_obis_network_datasets()

        # Flatten every OBIS dataset's source URLs into one comparison list.
        # collect_urls() pulls both the resource page URL and the DwC-A
        # archive URL, normalized, so dedup works against either form.
        self.obis_datasets = []
        for dataset in obis_datasets:
            self.obis_datasets.extend(collect_urls(dataset))

        self.obis_blacklist = []
        for dataset in get_obis_blacklist():
            self.obis_blacklist.extend(collect_urls(dataset))

        self.obis_titles = [dataset["title"] for dataset in obis_datasets if dataset["title"] is not None]

    def obis_has_dataset(self, identifiers, title=None):
        if urls_match(identifiers, self.obis_datasets):
            return True
        if urls_match(identifiers, self.obis_blacklist):
            return True
        if title is not None and title in self.obis_titles:
            return True
        return False

    def github_has_issue(self, identifiers):
        for issue in self.github_issues:
            if issue["body"] is None or "URLs" not in issue["body"]:
                continue
            if urls_match(identifiers, issue["body"]["URLs"]):
                return True
        return False

    def dataset_is_orphaned(self, gbif_dataset):
        for endpoint in gbif_dataset["endpoints"]:
            if endpoint["url"].startswith("https://orphans.gbif.org"):
                return True
        return False

    def dataset_has_dwc_endpoint(self, gbif_dataset):
        for endpoint in gbif_dataset["endpoints"]:
            if endpoint["type"] == "DWC_ARCHIVE":
                return True
        return False

    def run(self, dry_run=False):

        count_new = 0

        for gbif_dataset in self.gbif_datasets:
            gbif_url = create_gbif_url(gbif_dataset["key"])
            identifiers = collect_identifiers(gbif_dataset)

            if not self.dataset_has_dwc_endpoint(gbif_dataset):
                logger.info(colored(f"No IPT URL found for {gbif_url}", "red"))
                continue

            if self.obis_has_dataset(identifiers):
                continue

            logger.info(colored(f"Dataset not in OBIS: {gbif_url}", "blue"))

            if self.dataset_is_orphaned(gbif_dataset):
                continue

            logger.info(colored(f"Dataset is not orphaned: {gbif_url}", "blue"))

            if self.github_has_issue(identifiers):
                continue

            logger.info(colored(f"Dataset not in GitHub: {gbif_url}", "green"))
            count_new += 1

            if not dry_run:
                create_github_issue(gbif_dataset, identifiers)

        logger.info(colored(f"New datasets: {count_new}", "green"))