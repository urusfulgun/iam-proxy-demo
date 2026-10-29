import uvicorn


def main() -> None:
    uvicorn.run("iam_proxy_demo.app:app", host="0.0.0.0", port=8000)
