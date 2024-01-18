from sanic import Sanic
from .vfd.VFDBlueprint import VFDBlueprint
from sanic.log import logger

logger.setLevel("DEBUG")
app = Sanic("LevitreeBackend")
app.config.CORS_ORIGINS = "*"

app.blueprint(VFDBlueprint)