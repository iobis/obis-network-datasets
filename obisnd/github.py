import requests
import re
import os
import logging
import yaml
from obisnd.gbif import create_gbif_url
import json
from dotenv import load_dotenv


load_dotenv()


logger = logging.getLogger("obisnd")
session = requests.Session()
session.auth = (os.getenv("GITHUB_USER"), os.getenv("GITHUB_ACCESS_TOKEN"))
session.headers.update({
    "User-Agent": "iobis/obis-network-datasets",
    "Accept": "application/vnd.github.v3+json"
})


def parse_issue_body(body):
    lines = [item.strip() for item in re.split("[\r\n]+-", body)]
    props = [[re.sub("-\s+", "", s.strip()) for s in line.split(":", 1)] for line in lines]
    props_dict = { prop[0]: prop[1] for prop in props }
    props_dict["URLs"] = [url.strip() for url in props_dict["URLs"].splitlines()]
    return(props_dict)


def get_github_issues():
    res = session.get(url="https://api.github.com/repos/iobis/obis-network-datasets/issues?state=all&labels=dataset")
    issues = res.json()
    for issue in issues:
        issue["body"] = parse_issue_body(issue["body"])
    return(issues)


def create_github_issue(gbif_dataset, identifiers):
    url = create_gbif_url(gbif_dataset["key"])
    props = [
        { "title": gbif_dataset["title"] },
        { "GBIF": url },
        { "created": gbif_dataset["created"] },
        { "URLs": identifiers }
    ]
    data = {
        "title": gbif_dataset["title"],
        "body": yaml.dump(props),
        "labels": ["dataset"]
    }
    res = session.post("https://api.github.com/repos/iobis/obis-network-datasets/issues", json.dumps(data))
    logger.info(f"Status code: {res.status_code}")
    logger.info("Created GitHub issue")
