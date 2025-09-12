"""
FIXME not sure how the sync should be done, should we:
1. Sync authors by VIAF id?
  - Cons: This could create new authors without editions? Should we add new author's editions on the fly?
  - Cons: There are ~1M Wikidata entities with VIAF ids. These might not all be appropriate for Open Library
1. Sync authors by Open Library IDS in Wikidata without the corresponding wikidata ids in Open Library
  - Cons: Seems a bit redundant
1. Something else I'm not thinking off?

FIXME: this script uses SPARQLWrapper but should ultimately use PyWikiBot
"""
import datetime
import logging
import sys

from olclient import OpenLibrary
from os import makedirs
from SPARQLWrapper import SPARQLWrapper, JSON


# Setup logger
logger = logging.getLogger("jobs.sync_author_olids")
logger.setLevel(logging.DEBUG)
# The logging format
log_formatter = logging.Formatter('%(name)s;%(levelname)-8s;%(asctime)s %(message)s')
# Log warnings+ to console
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.WARN)
console_handler.setFormatter(log_formatter)
logger.addHandler(console_handler)
# Log INFO+ to the log file
log_dir = 'logs/jobs/sync_author_olids'
makedirs(log_dir, exist_ok=True)
log_file_datetime = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
log_file = log_dir + '/sync_author_olids_%s.log' % log_file_datetime
file_handler = logging.FileHandler(log_file)
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(log_formatter)
logger.addHandler(file_handler)


if __name__ == '__main__':
    filename = sys.argv[1]

    endpoint_url = 'https://query.wikidata.org/sparql'
    # this query times out but finds entities that have a VIAF id, is an author, and does not have an Open Library ID
    '''
    QUERY = """
    SELECT DISTINCT ?author WHERE {
      ?author wdt:P214 ?viaf_id.
      ?work (wdt:P50|wdt:P2093) ?author.
      MINUS { ?author wdt:P648 ?olid. }
    }
    # LIMIT 10  # for debugging
    """
    '''
    query = """
    SELECT DISTINCT ?item ?olid WHERE {
        ?item wdt:P648 ?olid.
        ?work (wdt:P50|wdt:P2093) ?item.
    }
    # LIMIT 10  # for debugging
    """
    user_agent = 'WDQS-example Python/%s.%s' % (sys.version_info[0], sys.version_info[1])
    sparql = SPARQLWrapper(endpoint_url, agent=user_agent)
    sparql.setQuery(query)
    sparql.setReturnFormat(JSON)
    results = sparql.query().convert()

    ol = OpenLibrary()
    with open(filename, 'w') as fout:
        logger.info('found %s authors with Open Library ids' % len(results['results']['bindings']))
        for result in results['results']['bindings']:
            olid = result['olid']['value']
            author = ol.Author.get(olid)
            if author.type['key'] != '/type/redirect':
                # FIXME for wikidata items that only have a redirect Open Library author(s), the script should add the correct olid to Wikidata
                try:
                    author.remote_ids['wikidata']
                except (AttributeError, KeyError):
                    wikidata_id = result['item']['value'].split('/')[-1]
                    if author.olid:
                        fout.write('\t'.join([author.olid, wikidata_id, '\n']))
                    else:
                        logger.warning('Open Library Client returned an author with an invalid olid for %s' % olid)
                except Exception:
                    logger.exception(','.join([author, result, '\n']))
