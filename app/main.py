from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "Atlas App is running on Minikube"}

@app.get("/health")
def health_check():
    return {"status": "healthy"}

app.run(host="0.0.0.0", port=5000)

