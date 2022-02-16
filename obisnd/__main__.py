import argparse
from obisnd import run
import logging


logging_level = logging.INFO
logging_fmt = "%(asctime)s-%(levelname)4.4s-%(name)6.6s-%(message)s"
date_fmt = "%Y-%m-%d %H:%M:%S"
logging.basicConfig(level=logging_level, format=logging_fmt, datefmt=date_fmt)


if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    args = parser.parse_args()

    run()
