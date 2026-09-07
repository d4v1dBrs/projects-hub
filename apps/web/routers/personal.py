from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from apps.web.templates import TEMPLATES

router = APIRouter()

@router.get("/", response_class=HTMLResponse)
def resume(request: Request):
    return TEMPLATES.TemplateResponse(request, "personal/index.html", {})
