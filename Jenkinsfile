pipeline {
  parameters {
      string(name: 'PIP_INDEX_URL', defaultValue: '')
      string(name: 'APT_MIRROR', defaultValue: '', description: 'An apt mirror url, if needed')
      string(name: 'HTTPS_PROXY', defaultValue: '', description: 'An HTTPS proxy URL, if needed')
      string(name: 'NO_PROXY', defaultValue: '', description: 'A comma-separated list of hosts to not proxy')
      booleanParam(name: 'RUN_SYNC_EDITION_OLIDS_BY_ISBNS', defaultValue: true, description: 'Run sync_edition_olids_by_isbns job')
      booleanParam(name: 'RUN_SYNC_AUTHOR_IDENTIFIERS_FROM_WIKIDATA', defaultValue: true, description: 'Run sync_author_identifiers_from_wikidata job')
  }
  agent {
    dockerfile {
      filename 'Dockerfile'
      additionalBuildArgs """\
        --build-arg PIP_INDEX_URL='${params.PIP_INDEX_URL}' \
        --build-arg APT_MIRROR='${params.APT_MIRROR}' \
        --build-arg HTTPS_PROXY='${params.HTTPS_PROXY}' \
        --build-arg NO_PROXY='${params.NO_PROXY}' \
      """
    }
  }
  environment {
    PYWIKIBOT_DIR='/pywikibot'
    HTTPS_PROXY = "${params.HTTPS_PROXY}"
    NO_PROXY = "${params.NO_PROXY}"
  }
  stages {
    stage('Setup') {
      steps {
        withCredentials([usernamePassword(credentialsId: 'openlibrary-bot-credentials', usernameVariable: 'USERNAME', passwordVariable: 'PASSWORD')]) {
          sh "mkdir $PYWIKIBOT_DIR"
          sh "python3 /app/src/pywikibot/pwb.py generate_user_files -family:wikidata -lang:wikidata -user:$USERNAME -dir:$PYWIKIBOT_DIR"
          sh 'expect login-pywikibot.tcl'
        }
        withCredentials([usernamePassword(credentialsId: 'wikidata-bot-credentials', usernameVariable: 'USERNAME', passwordVariable: 'PASSWORD')]) {
          sh 'expect login-openlibrary-client.tcl'
        }
      }
    }
    stage('Run Job') {
      when {
        expression { params.RUN_SYNC_EDITION_OLIDS_BY_ISBNS }
      }
      steps {
        sh 'python3 openlibrary-wikidata-bot/jobs/sync_edition_olids_by_isbns.py'
      }
    }
    stage('sync_author_identifiers_from_wikidata') {
      when {
        expression { params.RUN_SYNC_AUTHOR_IDENTIFIERS_FROM_WIKIDATA }
      }
      steps {
        // TMP: Limiting to 20 records
        sh '''
          curl -sL "https://openlibrary.org/data/ol_dump_wikidata_latest.txt.gz" | zcat | head -n20 > ol_dump_wikidata.tsv
        '''
        sh 'python3 openlibrary-wikidata-bot/jobs/sync_author_identifiers_from_wikidata.py --sql-path="ol_dump_wikidata.tsv"'
      }
    }
  }
  post {
    always {
      archiveArtifacts artifacts: 'logs/jobs/sync_edition_olids_by_isbns/*', allowEmptyArchive: true
      archiveArtifacts artifacts: 'logs/jobs/sync_author_identifiers_from_wikidata.py/*', allowEmptyArchive: true
      deleteDir() // Delete the workspace
    }
  }
}
