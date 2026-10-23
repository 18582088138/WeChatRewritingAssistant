"""Inspectable source discovery; searching does not run generation."""

from fastapi import APIRouter, Depends, Query

from ..dependencies import auth
from ..research_search import search_with_report

router = APIRouter(dependencies=[Depends(auth)])


@router.get("/api/research/search")
def discover(q: str = Query(min_length=2, max_length=240)):
    return search_with_report(q)
