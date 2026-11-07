from fastapi import FastAPI
from supportops.database import Base, engine
import supportops.models 
from supportops.Routers.v1.TicketRoutes import router as ticket_router
from supportops.Routers.v1.UserRoutes import router as user_router
from supportops.Routers.v1.commentRoutes import router as comment_router
from supportops.Routers.v1.CategoryRoutes import router as category_router

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="SupportOps API")

# Mount / Include the router
app.include_router(ticket_router, prefix="/tickets", tags=["Tickets"])
app.include_router(user_router, prefix="/users", tags=["Users"])
app.include_router(comment_router, prefix="/comments", tags=["Comments"])
app.include_router(category_router, prefix="/categories", tags=["Categories"])


@app.get("/")
def read_root():
    return {"Hello": "World"}

