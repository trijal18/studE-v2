pipeline {
    agent any

    environment {
        IMAGE_NAME = 'trijal18/stude-app:latest'
        CONTAINER_NAME = 'stude-app'
        CONTAINER_PORT = '8000'
    }

    stages {
        stage('Clone Code') {
            steps {
                git 'https://github.com/trijal18/studE-v2'
            }
        }

        stage('Build Docker Image') {
            steps {
                script {
                    sh "docker build -t ${IMAGE_NAME} ."
                }
            }
        }

        stage('Run App') {
            steps {
                script {
                    sh "docker rm -f ${CONTAINER_NAME} || true"
                    sh "docker run --env-file .env -d -p 8000:8000 --name ${CONTAINER_NAME} ${IMAGE_NAME}"
                }
            }
        }
    }
}
// why does it still exist  
