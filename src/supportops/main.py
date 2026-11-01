from fastapi import FastAPI
from supportops.database import Base, engine
import supportops.models 
from supportops.Routers.v1.TicketRoutes import router as ticket_router

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="SupportOps API")

# Mount / Include the router
app.include_router(ticket_router, prefix="/tickets", tags=["Tickets"])


@app.get("/")
def read_root():
    return {"Hello": "World"}

