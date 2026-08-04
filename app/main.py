from fastapi import FastAPI

from app.routers.gocryptfs_initialize import router as initialize_gocryptfs


app = FastAPI(
    swagger_ui_parameters={
        "persistAuthorization": True,
        "displayRequestDuration": True,
        "tryItOutEnabled": True,
    }
)


@app.get("/")
async def root():
    return {"message": "Hello World"}


app.include_router(initialize_gocryptfs, prefix="/api/v1")
