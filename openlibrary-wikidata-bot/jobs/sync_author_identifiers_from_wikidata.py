from copy import deepcopy
from datetime import datetime
from olclient import OpenLibrary
from os import makedirs
import argparse
import csv
import datetime
import json
import logging
import re
import sys

# Setup logger
logger = logging.getLogger("jobs.sync_author_wikidata_ids")
logger.setLevel(logging.DEBUG)
# The logging format
log_formatter = logging.Formatter("%(name)s;%(levelname)-8s;%(asctime)s %(message)s")
# Log warnings+ to console
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.WARN)
console_handler.setFormatter(log_formatter)
logger.addHandler(console_handler)
# Log INFO+ to the log file
log_dir = "logs/jobs/sync_author_wikidata_ids"
makedirs(log_dir, exist_ok=True)
log_file_datetime = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
log_file = log_dir + "/sync_author_wikidata_ids_%s.log" % log_file_datetime
problems_file = (
    log_dir + "/sync_author_wikidata_ids_%s_problems.csv" % log_file_datetime
)
file_handler = logging.FileHandler(log_file)
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(log_formatter)
logger.addHandler(file_handler)

# Setup error sheet
n = datetime.datetime.now().strftime("%Y-%m-%d-%H%M%S")
with open(problems_file, mode="w", newline="", encoding="utf-8") as file:
    writer = csv.writer(file)
    writer.writerow(
        ["wdid", "olid", "author_name", "problem", "identifier", "details"]
    )  # Write header

# I'd like it if this could come from identifiers.yml, but that's in a totally different repo!
# In an ideal world, identifiers.yml stores the WD P### identifier for each remote ID type, and we can loop thru that instead.
# Wikidata JSONs only use the P### identifier, so that's our only way to target specific remote IDs.
WD_PID_TO_OL_IDENTIFIER_NAME = {
    "P214": "viaf",
    "P2607": "bookbrainz",
    "P434": "musicbrainz",
    "P2963": "goodreads",
    "P213": "isni",
    "P345": "imdb",
    "P244": "lc_naf",
    "P7400": "librarything",
    "P1899": "librivox",
    "P1938": "project_gutenberg",
    "P396": "opac_sbn",
    "P4862": "amazon",
    "P12430": "storygraph",
    "P2397": "youtube",
}


def validate_wikidata_key(obj: dict[str, any], key=str) -> bool:
    if not ("property" in obj):
        return False
    if not ("id" in obj["property"]):
        return False
    if key != obj["property"]["id"]:
        return False
    if not ("value" in obj):
        return False
    if not ("content" in obj["value"]):
        return False
    return True


def write_error(wd_id, author_key, author_name, error_type, id, details):
    logger.error(
        f"{error_type} for {author_key} ({author_name}), wd {wd_id}: {id}: {details}"
    )
    with open(problems_file, mode="a", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow([wd_id, author_key, author_name, error_type, id, details])


def merge_remote_ids(author, incoming_ids, wd_id) -> tuple[dict[str, str], int]:
    """Returns the author's remote IDs merged with a given remote IDs object, as well as a count for how many IDs had conflicts.
    If incoming_ids is empty, or if there are more conflicts than matches, no merge will be attempted, and the output will be (author.remote_ids, -1).
    """
    output = deepcopy(getattr(author, "remote_ids", {}))
    # Count
    update_count = 0
    conflicts = 0
    for identifier in WD_PID_TO_OL_IDENTIFIER_NAME.values():
        if (
            identifier in output
            and identifier in incoming_ids
            and output[identifier] != incoming_ids[identifier]
        ):
            conflicts = conflicts + 1
            write_error(
                wd_id,
                author.olid,
                author.name,
                "openlibrary_wikidata_remote_id_collision",
                identifier,
                f'{{"ol": "{output[identifier]}", "wd": "{incoming_ids[identifier]}"}}',
            )
        elif identifier in incoming_ids and identifier not in output:
            output[identifier] = incoming_ids[identifier]
            update_count = update_count + 1
    if conflicts > 0:
        return author.remote_ids, -1
    return output, update_count


def consolidate_remote_author_ids(sql_path: str, dry_run: bool = True) -> None:
    ol = OpenLibrary()

    csv.field_size_limit(sys.maxsize)

    # Read in the wikidata DB dump
    with open(sql_path, mode="r", encoding="utf-8") as file:
        next(file)  # skip the header line
        reader = csv.reader(file, delimiter="\t")  # Read as TSV
        for row in reader:
            assert len(row) == 3
            wikidata_col_raw = row[1]

            parsed_wikidata_json = ""

            try:
                parsed_wikidata_json = json.loads(wikidata_col_raw)
            except json.JSONDecodeError as e:
                logger.error("Error parsing wikidata JSON on row {row} - {e}")
                continue
            wd_statements = parsed_wikidata_json["statements"]

            # Skip if no OL ID
            if not ("P648" in wd_statements):
                continue

            # Some of these WD entries match multiple OL authors.
            # What to do in that scenario?
            # For now, flagging that as a problem

            ol_ids = [
                obj["value"]["content"]
                for obj in wd_statements.get("P648", [])
                if validate_wikidata_key(obj, "P648")
                and re.fullmatch(r"OL\d+A", obj["value"]["content"])
            ]

            if len(ol_ids) == 0:
                continue
            wd_id = parsed_wikidata_json["id"]

            if len(ol_ids) > 1:
                for ol_id in ol_ids:
                    author = ol.Author.get(ol_id)
                    write_error(
                        wd_id,
                        ol_id,
                        author.name,
                        "multiple_openlibrary_authors_for_one_wikidata_row",
                        "ol_id",
                        f'[{",".join([f'"{val}"' for val in ol_ids])}]',
                    )
                continue
            ol_id = ol_ids[0]

            author = ol.Author.get(ol_id)

            remote_ids = {"wikidata": wd_id}

            # Check for just the identifiers we're interested in
            for pid, ol_identifier_name in WD_PID_TO_OL_IDENTIFIER_NAME.items():

                # Skip if this remote ID isn't in the wikidata json at all
                wd_remote_id_values = wd_statements.get(pid, [])
                if len(wd_remote_id_values) == 0:
                    continue

                # Get the value(s) for this remote ID from the wikidata json
                valid_wd_remote_id_values = [
                    obj["value"]["content"]
                    for obj in wd_remote_id_values
                    if validate_wikidata_key(obj, pid)
                ]
                if len(valid_wd_remote_id_values) == 0:
                    continue

                # Simple case: there's only one match. Add it to the remote_ids dict
                elif len(valid_wd_remote_id_values) == 1:
                    remote_id_value = valid_wd_remote_id_values[0]
                    remote_ids[ol_identifier_name] = remote_id_value

                # Bad case: there are multiple values for the remote ID
                else:
                    write_error(
                        wd_id,
                        ol_id,
                        author.name,
                        "multiple_wikidata_remote_ids_for_one_author",
                        ol_identifier_name,
                        f'[{",".join([f'"{val}"' for val in valid_wd_remote_id_values])}]',
                    )

            if len(remote_ids.keys()) > 0:
                remote_ids, update_count = merge_remote_ids(author, remote_ids, wd_id)
                if not dry_run:
                    pass
                    # I am not trying this yet! I'm terrified! I made dry-run default to false for this reason 😬
                    # author.remote_ids = remote_ids
                    # author.save("[sync_author_identifiers_with_wikidata] add wikidata remote identifiers")
                logger.info(f"new remote_ids for {ol_id}: {remote_ids}")


if __name__ == "__main__":
    console_handler.setLevel(logging.INFO)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run", action="store_true", help="Don't actually perform edits"
    )
    parser.add_argument(
        "--sql-path",
        type=str,
        required=True,
        help="Filepath of the sql dump file to parse",
    )
    args = parser.parse_args()

    try:
        consolidate_remote_author_ids(sql_path=args.sql_path, dry_run=args.dry_run)
    except Exception as e:
        logger.exception("")
        raise e
