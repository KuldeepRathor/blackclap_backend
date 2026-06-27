from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.websocket.pubsub import pubsub
from app.modules.auth.router import router as auth_router
from app.modules.chat.router import router as chat_router
from app.modules.realtime.router import router as realtime_router
from app.modules.search.router import router as search_router
from app.modules.comments.router import router as comments_router
from app.modules.follows.router import router as follows_router
from app.modules.likes.router import router as likes_router
from app.modules.media.router import router as media_router
from app.modules.posts.router import router as posts_router
from app.modules.saves.router import router as saves_router
from app.modules.uploads.router import router as uploads_router
from app.modules.users.router import router as users_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Open the shared Redis connection and start the pub/sub reader that bridges
    # cross-instance WebSocket delivery to locally-connected sockets.
    await pubsub.start()
    try:
        yield
    finally:
        await pubsub.stop()


app = FastAPI(
    title="BlackClap API",
    version="1.0.0",
    docs_url="/api/v1/docs",
    redoc_url="/api/v1/redoc",
    openapi_url="/api/v1/openapi.json",
    lifespan=lifespan,
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files serving (Dev local upload storage emulator)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Include Routers
app.include_router(auth_router, prefix="/api/v1")
app.include_router(users_router, prefix="/api/v1")
app.include_router(media_router, prefix="/api/v1")
app.include_router(uploads_router, prefix="/api/v1")
app.include_router(posts_router, prefix="/api/v1")
app.include_router(follows_router, prefix="/api/v1")
app.include_router(likes_router, prefix="/api/v1")
app.include_router(comments_router, prefix="/api/v1")
app.include_router(saves_router, prefix="/api/v1")
app.include_router(search_router, prefix="/api/v1")
app.include_router(chat_router, prefix="/api/v1")
app.include_router(realtime_router, prefix="/api/v1")


@app.get("/")
async def root() -> dict[str, str]:
    return {"message": "Welcome to BlackClap API", "version": "1.0.0"}


@app.get("/api/v1/health")
async def health_check() -> dict[str, str]:
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
