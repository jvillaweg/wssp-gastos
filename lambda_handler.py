from mangum import Mangum
from app.main import app

# Wrap FastAPI app for Lambda
handler = Mangum(app)
