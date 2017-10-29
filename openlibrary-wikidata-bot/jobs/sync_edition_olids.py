"""
Finds editions on Wikidata and Open Library with the same ISBNs and adds the
Open Library ID to Wikidata and the Wikidata ID to Open Library.
"""

import logging
from typing import TypeVar, List, Callable, Hashable

import pywikibot
from pywikibot.data.sparql import SparqlQuery
from olclient import OpenLibrary

QUERY = """
SELECT
?item
#?itemLabel
?isbn13
?isbn10
WHERE {
  ?item  wdt:P31 wd:Q3331189.                # instanceOf: Edition                 
  OPTIONAL { ?item wdt:P212 ?isbn13. }       # isbn13: ?isbn13
  OPTIONAL { ?item wdt:P957 ?isbn10. }       # isbn10: ?isbn10
  FILTER(bound(?isbn13) || bound(?isbn10))
  FILTER NOT EXISTS { ?item wdt:P648 ?olid } # Open Library ID: ?olid
#  SERVICE wikibase:label { bd:serviceParam wikibase:language "en" . }
}
LIMIT 1 # for testing
"""


def make_str_claim(repo, prop: str, target: str) -> pywikibot.Claim:
    """Create a Wikidata claim (prop, target) where target is a string."""
    claim = pywikibot.Claim(repo, prop)
    claim.setTarget(target)
    return claim


def normalize_isbn(isbn: str) -> str:
    """Remove hyphens and make lowercase."""
    return ''.join(isbn.split('-')).lower()


def remove_dupes(
        lst: List[TypeVar('T')],
        hash_fn: Callable[[TypeVar('T')], Hashable] = None
) -> List[TypeVar('T')]:
    """Remove duplicates from a list."""
    result = []
    seen = set()
    for el in lst:
        hsh = hash_fn(el) if hash_fn else el
        if hsh not in seen:
            result.append(el)
            seen.add(hsh)
    return result


def sync_edition_olids():
    """
    Finds editions on Wikidata and Open Library with the same ISBNs and adds the
    Open Library ID to Wikidata and the Wikidata ID to Open Library.
    """
    wd = pywikibot.Site("wikidata", "wikidata")
    wd_repo = wd.data_repository()
    wd_sparql = SparqlQuery()

    ol = OpenLibrary()

    wikidata_books = wd_sparql.select(QUERY)
    logging.info("Found %d books to update on Wikidata", len(wikidata_books))
    for row in wikidata_books:
        qid = row['item'].split('/')[-1]
        isbns = [row[key] for key in ['isbn10', 'isbn13'] if row[key]]
        ol_books = [ol.Edition.get(isbn=normalize_isbn(isbn)) for isbn in isbns]
        ol_books = [book for book in ol_books if book]
        ol_books = remove_dupes(ol_books, lambda ed: ed.olid)

        if len(ol_books) == 0:
            logging.warning("No Open Library books for %s (isbns %s)", qid, ', '.join(isbns))
            continue
        if len(ol_books) > 1:
            logging.warning("Multiple (%d) Open Library books for %s (isbns %s)", len(ol_books), qid, ', '.join(isbns))

        # update open library data
        for book in ol_books:
            if 'wikidata' not in book.identifiers:
                book.identifiers['wikidata'] = []

            book_qids = book.identifiers['wikidata']

            if qid in book_qids:
                logging.warning("%s already has qid %s", book.olid, qid)
                continue

            book_qids.append(qid)
            if len(book_qids) > 1:
                logging.warning("%s now has multiple (%d) qids (%s)", book.olid, len(book_qids), ', '.join(book_qids))
            book.save("[sync_edition_olids] add wikidata identifier")

        # update wikidata data
        for book in ol_books:
            item = pywikibot.ItemPage(wd_repo, qid)
            claim = make_str_claim(wd_repo, 'P648', book.olid)
            item.addClaim(claim)


if __name__ == "__main__":
    try:
        sync_edition_olids()
    except Exception as e:
        logging.exception("")
        raise e
