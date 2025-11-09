"""Entry point for running Simulator API."""
import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "apps.simulator_api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )

