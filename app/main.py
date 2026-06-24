from contextlib import asynccontextmanager

from pathlib import Path



from fastapi import FastAPI, Request

from fastapi.middleware.cors import CORSMiddleware

from fastapi.responses import HTMLResponse

from fastapi.staticfiles import StaticFiles

from fastapi.templating import Jinja2Templates



from app.config import get_settings

from app.init_db import init_db

from app.routers import admin, proxy, user



settings = get_settings()

BASE_DIR = Path(__file__).resolve().parent





@asynccontextmanager

async def lifespan(app: FastAPI):

    await init_db()

    yield





app = FastAPI(

    title=settings.platform_name,

    description="AI Token 中转销售平台 - OpenAI 兼容 API",

    version="1.0.0",

    lifespan=lifespan,

)


# 允许所有来源的 CORS，支持 Cursor / LobeChat / Cherry Studio 等客户端直接调用
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(proxy.router)

app.include_router(user.router)

app.include_router(admin.router)



static_dir = BASE_DIR / "static"

static_dir.mkdir(exist_ok=True)

app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))





@app.get("/", response_class=HTMLResponse)

async def index(request: Request):

    return templates.TemplateResponse("index.html", {"request": request, "platform_name": settings.platform_name})





@app.get("/dashboard", response_class=HTMLResponse)

async def dashboard(request: Request):

    return templates.TemplateResponse("dashboard.html", {"request": request, "platform_name": settings.platform_name})





@app.get("/admin", response_class=HTMLResponse)

async def admin_page(request: Request):

    return templates.TemplateResponse("admin.html", {"request": request, "platform_name": settings.platform_name})





@app.get("/health")

async def health():

    return {"status": "ok", "platform": settings.platform_name}





@app.get("/api/config")

async def public_config():

    return {

        "platform_name": settings.platform_name,

        "currency": settings.currency,

        "recharge_notice": settings.recharge_notice,

        "api_base_url": "/v1",

    }


# ======= 协议页面 =======

@app.get("/terms", response_class=HTMLResponse)

async def terms_page(request: Request):

    return templates.TemplateResponse("terms.html", {"request": request, "platform_name": settings.platform_name})


@app.get("/privacy", response_class=HTMLResponse)

async def privacy_page(request: Request):

    return templates.TemplateResponse("privacy.html", {"request": request, "platform_name": settings.platform_name})

