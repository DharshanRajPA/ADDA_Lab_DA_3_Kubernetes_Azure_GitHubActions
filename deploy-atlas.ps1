# === Set Docker env inside Minikube ===
Write-Host "🔧 Switching Docker to Minikube environment..."
& minikube -p minikube docker-env | Invoke-Expression

# === Build Docker image inside Minikube ===
Write-Host "🐳 Building Docker image 'atlas-app:latest' inside Minikube..."
docker build -t atlas-app:latest .

# === Apply K8s manifests ===
Write-Host "📦 Applying Kubernetes deployment..."
kubectl apply -n atlas -f k8s/atlas-deployment.yaml

Write-Host "🌐 Applying Kubernetes service..."
kubectl apply -n atlas -f k8s/atlas-service-nodeport.yaml

# === Restart deployment to use new image ===
Write-Host "🔁 Restarting deployment to load new image..."
kubectl rollout restart deployment atlas-deployment -n atlas

# === Wait for pods to be ready ===
Write-Host "⏳ Waiting for pods to be ready..."
kubectl wait --for=condition=ready pod -l app=atlas-app -n atlas --timeout=120s

# === Get Minikube IP ===
$minikubeIp = minikube ip
$url = "http://$minikubeIp:30080/health"

# === Health Check ===
Write-Host "`n🔍 Checking app health at $url"
try {
    $response = Invoke-RestMethod -Uri $url -TimeoutSec 5
    Write-Host "✅ App is healthy: $($response.status)"
} catch {
    Write-Host "❌ App is not responding. Please check pod logs:"
    kubectl logs -n atlas -l app=atlas-app
}
