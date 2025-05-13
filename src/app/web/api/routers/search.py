import logging
from typing import List
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from app.database.postgresql import get_db

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/semantic/", summary="Semantic search for images based on query")
async def semantic_search(
    query: str = Query(..., description="Text to search for"),
    limit: int = Query(10, description="Maximum number of results to return", ge=1, le=100)
):
    """
    Perform semantic search on images based on a text query.

    Args:
        query: Text string to search for relevant images.
        limit: Maximum number of search results to return.

    Returns:
        A JSON response with matched images and metadata.
    """
    try:
        results = get_db().search_image_by_caption(query, top_k=limit)
        
        if not results:
            return JSONResponse(content={
                "status": "success",
                "message": "No matching images found",
                "count": 0,
                "results": []
            })
        
        formatted_results = []
        for result in results:
            image_id, image_key = result
            
            formatted_results.append({
                "image_key": image_key,
                "preview_url": f"/api/images/view/{image_key}",
                "details_url": f"/api/images/details/{image_key}"
            })
        
        return JSONResponse(content={
            "status": "success",
            "message": f"Found {len(formatted_results)} matching images",
            "count": len(formatted_results),
            "results": formatted_results
        })
        
    except Exception as e:
        logger.error(f"Error during semantic search: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/bulk/", summary="Bulk search for multiple queries")
async def bulk_search(
    queries: List[str] = Query(..., description="List of search queries"),
    limit_per_query: int = Query(5, description="Maximum results per query", ge=1, le=20)
):
    """
    Perform bulk semantic search for multiple queries.

    Args:
        queries: A list of search strings.
        limit_per_query: Maximum number of results to return for each query.

    Returns:
        A JSON response with results for each query.
    """
    try:
        results = {}
        
        for query in queries:
            search_results = get_db().search_image_by_caption(query, top_k=limit_per_query)
            
            formatted_results = []
            for result in search_results:
                image_id, image_key = result
                
                formatted_results.append({
                    "image_key": image_key,
                    "preview_url": f"/api/images/view/{image_key}",
                })
            
            results[query] = {
                "count": len(formatted_results),
                "results": formatted_results
            }
        
        return JSONResponse(content={
            "status": "success",
            "message": f"Completed bulk search for {len(queries)} queries",
            "results": results
        })
        
    except Exception as e:
        logger.error(f"Error during bulk search: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
