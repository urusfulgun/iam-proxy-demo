import uvicorn


def main() -> None:
    # All interfaces: the compose app service takes connections from other containers.
    uvicorn.run("iam_proxy_demo.app:app", host="0.0.0.0", port=8000)  # noqa: S104
