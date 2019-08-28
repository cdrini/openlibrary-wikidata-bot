This bot operates on Open Library and Wikidata, doing some sync/cleanup tasks between the two.

## Usage

1. Start Jenkins:

```sh
docker run \
  -u root \
  --rm \
  -d \
  -p 8080:8080 \
  -p 50000:50000 \
  -v /var/run/docker.sock:/var/run/docker.sock \
  --name jenkins \
  jenkinsci/blueocean
```

2. Follow the steps here to finish setting up Jenkins: https://jenkins.io/doc/book/installing/#setup-wizard
3. Follow these steps to create a new Pipeline Project using git: https://jenkins.io/doc/book/pipeline/getting-started/#defining-a-pipeline-in-scm
4. In Jenkins, go to `/credentials/store/system/` on Jenkins, and create new credentials:
- `openlibrary-bot-credentials` (how `OpenLibraryBot` should log in to Wikidata)
- `wikidata-bot-credentials` (how `WikidataBot` should log in to Open Library)
5. Run the pipeline!

NOTE: This will currently run the only job this bot does. Once there are more jobs, this flow will change (somehow).