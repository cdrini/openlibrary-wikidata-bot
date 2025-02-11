from datetime import datetime
# from olclient import OpenLibrary
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
log_formatter = logging.Formatter('%(name)s;%(levelname)-8s;%(asctime)s %(message)s')
# Log warnings+ to console
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.WARN)
console_handler.setFormatter(log_formatter)
logger.addHandler(console_handler)
# Log INFO+ to the log file
log_dir = 'logs/jobs/sync_author_wikidata_ids'
problem_dir = 'exports/jobs/sync_author_wikidata_ids'
makedirs(log_dir, exist_ok=True)
makedirs(problem_dir, exist_ok=True)
log_file_datetime = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
log_file = log_dir + '/sync_author_wikidata_ids_%s.log' % log_file_datetime
file_handler = logging.FileHandler(log_file)
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(log_formatter)
logger.addHandler(file_handler)

# Setup error sheet
n = datetime.datetime.now().strftime("%Y-%m-%d-%H%M%S")
csv_file_path = f"{problem_dir}/sync_author_wikidata_ids_merge_problems-{n}.csv"
with open(csv_file_path, mode="w", newline="", encoding="utf-8") as file:
    writer = csv.writer(file)
    writer.writerow(["wdid", "olid", "problem", "identifier", "details"])  # Write header

# I'd like it if this could come from identifiers.yml, but that's in a totally different repo!
# In an ideal world, identifiers.yml stores the WD P### identifier for each remote ID type, and we can loop thru that instead.
# Wikidata JSONs only use the P### identifier, so that's our only way to target specific remote IDs.
WD_IDENTIFIERS = {
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
    "P2397": "youtube"
}

def validate_wikidata_key(obj: dict[str, any], key=str) -> bool:
    if not("property" in obj):
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


def write_error(wd_id, author_key, error_type, id, details):
    logger.error(f'{error_type} for {author_key}, wd {wd_id}: {id}: {details}')
    with open(csv_file_path, mode="a", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow([wd_id, author_key, error_type, id, details])


def merge_remote_ids(
    author, incoming_ids
) -> tuple[dict[str, str], int]:
    """Returns the author's remote IDs merged with a given remote IDs object, as well as a count for how many IDs had conflicts.
    If incoming_ids is empty, or if there are more conflicts than matches, no merge will be attempted, and the output will be (author.remote_ids, -1).
    """
    output = {**author.remote_ids}
    if len(incoming_ids.items()) == 0:
        return output, -1
    # Count
    matches = 0
    conflicts = 0
    for identifier in WD_IDENTIFIERS.values():
        if identifier in output and identifier in incoming_ids:
            if output[identifier] != incoming_ids[identifier]:
                conflicts = conflicts + 1
                write_error(author.key, f"openlibrary_wikidata_remote_id_collision", identifier, f'{{"ol": "{output[identifier]}", "wd": "{incoming_ids[identifier]}"}}')
            else:
                output[identifier] = incoming_ids[identifier]
                matches = matches + 1
    if conflicts > 0:
        return author.remote_ids, -1
    return output, matches


def consolidate_remote_author_ids(sql_path: str, dry_run: bool = True) -> None:
    # ol = OpenLibrary()
    # Can't get this to run, requirements.txt fails
    #ERROR: Cannot install -r requirements.txt (line 1), -r requirements.txt (line 2), openlibrary-client and requests==2.11.1 because these package versions have conflicting dependencies.
    #
    #The conflict is caused by:
    #    The user requested requests==2.11.1
    #    openlibrary-client 0.0.17 depends on requests==2.11.1
    #    internetarchive 1.7.3 depends on requests<3.0.0 and >=2.9.1
    #    pywikibot 7.0.0 depends on requests>=2.20.1; python_version >= "3.6"

    csv.field_size_limit(sys.maxsize)

    # Read in the wikidata DB dump
    with open(sql_path, mode="r", encoding="utf-8") as file:
        next(file) # skip the header line
        reader = csv.reader(file, delimiter="\t")  # Read as TSV
        for row in reader:
            if len(row) < 2:
                continue
            wikidata_col_raw = row[1]
            
            try:
                parsed_wikidata_json = json.loads(wikidata_col_raw)
                wd_json_top_level_fields = parsed_wikidata_json["statements"]

                # Skip if no OL ID
                if not ("P648" in wd_json_top_level_fields):
                    continue

                # Some of these WD entries match multiple OL authors. 
                # What to do in that scenario?
                # For now, flagging that as a problem

                ol_ids = [
                    obj["value"]["content"]
                    for obj in wd_json_top_level_fields.get("P648", [])
                    if validate_wikidata_key(obj, "P648") and re.fullmatch(r"OL\d+A", obj["value"]["content"])
                ]

                if len(ol_ids) == 0:
                    continue
                wd_id = parsed_wikidata_json["id"]

                if len(ol_ids) > 1:
                    for ol_id in ol_ids:
                        write_error(wd_id, ol_id, f"multiple_openlibrary_authors_for_one_wikidata_row", "ol_id", f'[{",".join([f'"{val}"' for val in ol_ids])}]')
                    continue
                ol_id = ol_ids[0]

                # TODO: get authors from OL client when i can get requirements.txt to work
                # author = ol.Author.get(key=ol_id)

                remote_ids = {}

                # Check for just the identifiers we're interested in
                for wd_p_value, remote_ids_key in WD_IDENTIFIERS.items():

                    # Skip if this remote ID isn't in the wikidata json at all
                    if wd_p_value not in wd_json_top_level_fields:
                        continue
                    wd_remote_id_values = wd_json_top_level_fields.get(wd_p_value, [])
                    if len(wd_remote_id_values) == 0:
                        continue

                    # Get the value(s) for this remote ID from the wikidata json
                    valid_wd_remote_id_values = [
                        obj["value"]["content"]
                        for obj in wd_remote_id_values
                        if validate_wikidata_key(obj, wd_p_value)
                    ]
                    if len(valid_wd_remote_id_values) == 0:
                        continue
                    
                    # Simple case: there's only one match. Add it to the remote_ids dict
                    if len(valid_wd_remote_id_values) == 1:
                        remote_id_value = valid_wd_remote_id_values[0]
                        # print(f"    {remote_ids_key}: {remote_id_value}")
                        remote_ids[remote_ids_key] = remote_id_value
                    
                    # Bad case: there are multiple values for the remote ID
                    elif len(wd_remote_id_values) > 1:
                        # print(f"\033[91m    {remote_ids_key}: {", ".join([obj['value']['content'] for obj in wd_remote_id_values])}\033[0m")
                        write_error(wd_id, ol_id, f"multiple_wikidata_remote_ids_for_one_author", remote_ids_key, ",".join([f'"{val}"' for val in valid_wd_remote_id_values]))

                if len(remote_ids.keys()) > 0:
            # TODO: Merge remote IDs with the author's existing remote IDs
            # 
            # 
            # author.remote_ids, matches = merge_remote_ids(remote_ids)
            # if matches > 0:
            #     if not dry_run:
            #        author.save("[sync_author_identifiers_with_wikidata] add wikidata remote identifiers")
            #     else:
                    logger.info(f'new remote_ids for [{", ".join(ol_ids)}]: {remote_ids}')

            except json.JSONDecodeError as e:
                logger.error(f"Error parsing wikidata JSON on row {row} - {e}")
    
            
if __name__ == "__main__":
    console_handler.setLevel(logging.INFO)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run', action='store_true',
                        help="Don't actually perform edits")
    parser.add_argument('--sql-path', type=str, required=True,
                        help='Filepath of the sql dump file to parse')
    args = parser.parse_args()

    try:
        consolidate_remote_author_ids(sql_path=args.sql_path, dry_run=args.dry_run)
    except Exception as e:
        logger.exception("")
        raise e