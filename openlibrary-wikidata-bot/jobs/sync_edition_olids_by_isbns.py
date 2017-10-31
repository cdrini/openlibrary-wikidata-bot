"""
Find editions on Wikidata and Open Library with the same ISBNs and add the
Open Library ID to Wikidata and the Wikidata ID to Open Library.
"""

import datetime
import logging
from os import makedirs
from typing import TypeVar, List, Callable, Hashable

from olclient import OpenLibrary
import pywikibot
from pywikibot.data.sparql import SparqlQuery

QUERY = """
SELECT
?item
# ?itemLabel
(group_concat(distinct ?isbn13; separator=";") as ?isbn13s)
(group_concat(distinct ?isbn10; separator=";") as ?isbn10s)
WHERE {
  ?item  wdt:P31 wd:Q3331189.                # instanceOf: Edition                 
  OPTIONAL { ?item wdt:P212 ?isbn13. }       # isbn13: ?isbn13
  OPTIONAL { ?item wdt:P957 ?isbn10. }       # isbn10: ?isbn10
  FILTER(bound(?isbn13) || bound(?isbn10))
  FILTER NOT EXISTS { ?item wdt:P648 ?olid } # Open Library ID: ?olid
  # SERVICE wikibase:label { bd:serviceParam wikibase:language "en" . }
}
GROUP BY ?item
  # ?itemLabel
# HAVING(count(?isbn13) > 1) # for testing
# LIMIT 10 # for testing
"""


def make_str_claim(repo, prop: str, target: str) -> pywikibot.Claim:
    """Create a Wikidata claim (prop, target) where target is a string."""
    claim = pywikibot.Claim(repo, prop)
    claim.setTarget(target)
    return claim


def normalize_isbn(isbn: str) -> str:
    """Remove hyphens and make uppercase."""
    return isbn.replace('-', '').upper()


def remove_dupes(
        lst: List[TypeVar('T')],
        hash_fn: Callable[[TypeVar('T')], Hashable] = None
) -> List[TypeVar('T')]:
    """Return a new list without duplicates."""
    result = []
    seen = set()
    for el in lst:
        hsh = hash_fn(el) if hash_fn else el
        if hsh not in seen:
            result.append(el)
            seen.add(hsh)
    return result


# Setup logger
logger = logging.getLogger("jobs.sync_edition_olids")
logger.setLevel(logging.DEBUG)
# The logging format
log_formatter = logging.Formatter('%(name)s;%(levelname)-8s;%(asctime)s %(message)s')
# Log warnings+ to console
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.WARN)
console_handler.setFormatter(log_formatter)
logger.addHandler(console_handler)
# Log INFO+ to the log file
log_dir = 'logs/jobs/sync_edition_olids_by_isbns'
makedirs(log_dir, exist_ok=True)
log_file_datetime = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
log_file = log_dir + '/sync_edition_olids_by_isbns_%s.log' % log_file_datetime
file_handler = logging.FileHandler(log_file)
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(log_formatter)
logger.addHandler(file_handler)


def sync_edition_olids_by_isbns(dry_run=False):
    """
    Find editions on Wikidata and Open Library with the same ISBNs and add the
    Open Library ID to Wikidata and the Wikidata ID to Open Library.
    """
    wd = pywikibot.Site("wikidata", "wikidata")
    wd_repo = wd.data_repository()
    wdqs = SparqlQuery()  # Wikidata Query Service

    ol = OpenLibrary()

    wd_books = wdqs.select(QUERY)
    logger.info("Found %d editions to update", len(wd_books))
    ol_books_modified = 0
    wd_items_modified = 0
    for row in wd_books:
        qid = row['item'].split('/')[-1]
        logger.debug("Processing %s", qid)

        isbns = []
        for isbnDDs in ['isbn13s', 'isbn10s']:
            if not row[isbnDDs]:
                continue
            _isbns = row[isbnDDs].split(';')
            if len(_isbns) > 1:
                logger.warning("%s has multiple %s (%d)", qid, isbnDDs, len(_isbns))
            isbns += _isbns
        ol_books = [ol.Edition.get(isbn=normalize_isbn(isbn)) for isbn in isbns]
        ol_books = [book for book in ol_books if book]
        ol_books = remove_dupes(ol_books, lambda ed: ed.olid)

        logger.info("Found %d Open Library book(s) for %s (isbns %s)", len(ol_books), qid, ', '.join(isbns))
        if len(ol_books) > 1:
            logger.warning("Multiple (%d) Open Library books for %s (isbns %s)", len(ol_books), qid, ', '.join(isbns))

        # update open library data
        for book in ol_books:
            if 'wikidata' not in book.identifiers:
                book.identifiers['wikidata'] = []

            book_qids = book.identifiers['wikidata']

            if qid in book_qids:
                logger.warning("%s already has qid %s", book.olid, qid)
                continue

            book_qids.append(qid)
            if len(book_qids) > 1:
                logger.warning("%s now has multiple (%d) qids (%s)", book.olid, len(book_qids), ', '.join(book_qids))
            if not dry_run:
                book.save("[sync_edition_olids] add wikidata identifier")
            logger.debug("Added %s to %s", qid, book.olid)
            ol_books_modified += 1

        # update wikidata data
        for book in ol_books:
            item = pywikibot.ItemPage(wd_repo, qid)
            claim = make_str_claim(wd_repo, 'P648', book.olid)
            if not dry_run:
                item.addClaim(claim)
            logger.debug("Added %s to %s", book.olid, qid)
            wd_items_modified += 1
    logger.info("Updated %d Open Library books and %d Wikidata items", ol_books_modified, wd_items_modified)


if __name__ == "__main__":
    console_handler.setLevel(logging.INFO)
    try:
        sync_edition_olids_by_isbns(dry_run=True)
    except Exception as e:
        logger.exception("")
        raise e
