from fastapi import FastAPI

app = FastAPI(title="DeTour")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
