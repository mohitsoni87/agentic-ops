// ─────────────────────────────────────────────────────────────────────────────
// agentic-ops CI/CD Pipeline
//
// Required Jenkins credentials (Manage Jenkins → Credentials):
//   DOCKERHUB_CREDS   → Username/Password  (Docker Hub login)
//   KUBECONFIG_SECRET → Secret file        (kubectl kubeconfig for target cluster)
//
// Required Jenkins plugins:
//   Pipeline, Docker Pipeline, Credentials Binding, Git
// ─────────────────────────────────────────────────────────────────────────────

pipeline {
    agent any

    environment {
        IMAGE_NAME    = "YOUR_DOCKERHUB_USERNAME/agentic-ops"
        IMAGE_TAG     = "${env.GIT_COMMIT?.take(8) ?: 'latest'}"
        FULL_IMAGE    = "${IMAGE_NAME}:${IMAGE_TAG}"
        K8S_NAMESPACE = "agentic-ops"
    }

    options {
        buildDiscarder(logRotator(numToKeepStr: '10'))
        timeout(time: 30, unit: 'MINUTES')
        disableConcurrentBuilds()
    }

    stages {

        // ── 1. Checkout ───────────────────────────────────────────────────────
        stage('Checkout') {
            steps {
                checkout scm
                echo "Building commit: ${env.GIT_COMMIT}"
            }
        }

        // ── 2. Lint & Import Test ─────────────────────────────────────────────
        stage('Test') {
            agent {
                docker {
                    image 'python:3.12-slim'
                    reuseNode true
                }
            }
            steps {
                sh '''
                    pip install --quiet uv
                    uv pip install --system --quiet -e .
                    python -c "
from src.agentic_ops.config import settings
from src.agentic_ops.state import AgentState
from src.agentic_ops.graph import build_graph
graph = build_graph()
assert set(graph.nodes.keys()) == {'__start__', 'rca', 'solution', 'notify'}
print('Import and graph construction: OK')
                    "
                '''
            }
        }

        // ── 3. Build Docker Image ─────────────────────────────────────────────
        stage('Build Image') {
            steps {
                script {
                    docker.build("${FULL_IMAGE}", "--no-cache .")
                    // Also tag as :latest for convenience
                    docker.build("${IMAGE_NAME}:latest", ".")
                }
            }
        }

        // ── 4. Push to Docker Hub ─────────────────────────────────────────────
        stage('Push Image') {
            when {
                anyOf {
                    branch 'main'
                    branch 'master'
                }
            }
            steps {
                script {
                    docker.withRegistry('https://registry.hub.docker.com', 'DOCKERHUB_CREDS') {
                        docker.image("${FULL_IMAGE}").push()
                        docker.image("${IMAGE_NAME}:latest").push()
                    }
                }
                echo "Pushed ${FULL_IMAGE}"
            }
        }

        // ── 5. Deploy to Kubernetes ───────────────────────────────────────────
        stage('Deploy') {
            when {
                anyOf {
                    branch 'main'
                    branch 'master'
                }
            }
            steps {
                withCredentials([file(credentialsId: 'KUBECONFIG_SECRET', variable: 'KUBECONFIG')]) {
                    sh """
                        export KUBECONFIG=\${KUBECONFIG}

                        # Apply all manifests in order (idempotent)
                        kubectl apply -f k8s/00-namespace.yaml
                        kubectl apply -f k8s/01-rbac.yaml
                        kubectl apply -f k8s/02-configmap.yaml
                        kubectl apply -f k8s/04-postgres.yaml

                        # Wait for postgres to be ready before deploying the agent
                        kubectl rollout status deployment/postgres \\
                            -n ${K8S_NAMESPACE} --timeout=120s

                        # Patch the deployment image tag (avoids full re-apply)
                        kubectl set image deployment/agentic-ops \\
                            agentic-ops=${FULL_IMAGE} \\
                            -n ${K8S_NAMESPACE} \\
                            --record || true

                        # Apply the deployment (creates it if it doesn't exist yet)
                        # Replace image placeholder with the real tag
                        sed 's|YOUR_DOCKERHUB_USERNAME/agentic-ops:latest|${FULL_IMAGE}|g' \\
                            k8s/05-deployment.yaml | kubectl apply -f -

                        # Wait for rollout to complete
                        kubectl rollout status deployment/agentic-ops \\
                            -n ${K8S_NAMESPACE} --timeout=180s
                    """
                }
            }
        }

        // ── 6. Seed Knowledge Base (first deploy only) ────────────────────────
        stage('Seed KB') {
            when {
                // Only seed when explicitly triggered with SEED_KB=true
                expression { params.SEED_KB == 'true' }
            }
            steps {
                withCredentials([file(credentialsId: 'KUBECONFIG_SECRET', variable: 'KUBECONFIG')]) {
                    sh """
                        export KUBECONFIG=\${KUBECONFIG}

                        sed 's|YOUR_DOCKERHUB_USERNAME/agentic-ops:latest|${FULL_IMAGE}|g' \\
                            k8s/06-seed-job.yaml | kubectl apply -f -

                        kubectl wait --for=condition=complete job/kb-seed \\
                            -n ${K8S_NAMESPACE} --timeout=300s

                        kubectl logs job/kb-seed -n ${K8S_NAMESPACE}

                        kubectl delete job/kb-seed -n ${K8S_NAMESPACE}
                    """
                }
            }
        }

    } // end stages

    // ── Post actions ──────────────────────────────────────────────────────────
    post {
        success {
            echo "Deploy succeeded: ${FULL_IMAGE} is live in namespace ${K8S_NAMESPACE}"
        }
        failure {
            echo "Pipeline failed — rolling back deployment"
            withCredentials([file(credentialsId: 'KUBECONFIG_SECRET', variable: 'KUBECONFIG')]) {
                sh """
                    export KUBECONFIG=\${KUBECONFIG}
                    kubectl rollout undo deployment/agentic-ops -n ${K8S_NAMESPACE} || true
                """
            }
        }
        always {
            // Clean up local Docker images to save disk space on the Jenkins agent
            sh "docker rmi ${FULL_IMAGE} || true"
            sh "docker rmi ${IMAGE_NAME}:latest || true"
            cleanWs()
        }
    }

    parameters {
        string(name: 'SEED_KB', defaultValue: 'false',
               description: 'Set to "true" on the first deploy to seed the knowledge base')
    }
}
