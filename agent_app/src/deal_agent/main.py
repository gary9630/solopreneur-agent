from fastapi import FastAPI

app = FastAPI(title="Deal Agent")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
