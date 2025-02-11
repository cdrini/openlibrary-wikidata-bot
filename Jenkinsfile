pipeline {
  agent {
    dockerfile { filename 'Dockerfile' }
  }
  environment {
    PYWIKIBOT_DIR='/pywikibot'
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
      steps {
        sh 'python3 openlibrary-wikidata-bot/jobs/sync_edition_olids_by_isbns.py'
        sh 'python3 openlibrary-wikidata-bot/jobs/sync_author_identifiers_from_wikidata.py --sql-path="tbd"'
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
