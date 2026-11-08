from fastapi import FastAPI
from supportops.database import Base, engine
from contextlib import asynccontextmanager
from supportops.Routers.v1.TicketRoutes import router as ticket_router
from supportops.Routers.v1.UserRoutes import router as user_router
from supportops.Routers.v1.commentRoutes import router as comment_router
from supportops.Routers.v1.CategoryRoutes import router as category_router

@asynccontextmanager
async def lifespan(_app: FastAPI):
    print("Starting up...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)   #Needed becasue we are not using Alembic for DB migrations
    yield
    print("Shutting down...")
    await engine.dispose()

app = FastAPI(lifespan=lifespan,title="SupportOps API")

# Mount / Include the router
app.include_router(ticket_router, prefix="/tickets", tags=["Tickets"])
app.include_router(user_router, prefix="/users", tags=["Users"])
app.include_router(comment_router, prefix="/comments", tags=["Comments"])
app.include_router(category_router, prefix="/categories", tags=["Categories"])


@app.get("/")
def read_root():
    return {"Hello": "World"}

