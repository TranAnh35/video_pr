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
        
        # Ensure uniqueness of results
        seen_image_keys = set()
        formatted_results = []
        
        for result in results:
            image_id, image_key = result
            
            # Skip if we've already seen this image key
            if image_key in seen_image_keys:
                continue
                
            seen_image_keys.add(image_key)
            formatted_results.append({
                "image_key": image_key
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
    limit_per_query: int = Query(5, description="Maximum results per query", ge=1, le=20),
    avoid_duplicates_across_queries: bool = Query(True, description="Whether to avoid duplicate images across different queries")
):
    """
    Perform bulk semantic search for multiple queries.

    Args:
        queries: A list of search strings.
        limit_per_query: Maximum number of results to return for each query.
        avoid_duplicates_across_queries: If True, images that appear in one query result won't appear in subsequent query results.

    Returns:
        A JSON response with results for each query.
    """
    try:
        results = {}
        # Track all found image keys to avoid duplicates between queries
        all_found_image_keys = set()
        
        for query in queries:
            exclude_keys = list(all_found_image_keys) if avoid_duplicates_across_queries else None
            search_results = get_db().search_image_by_caption(
                query, 
                top_k=limit_per_query, 
                exclude_image_keys=exclude_keys
            )
            
            # Ensure uniqueness within this query's results
            seen_image_keys = set()
            formatted_results = []
            
            for result in search_results:
                image_id, image_key = result
                
                # Skip if we've already seen this image key
                if image_key in seen_image_keys:
                    continue
                    
                seen_image_keys.add(image_key)
                
                if avoid_duplicates_across_queries:
                    all_found_image_keys.add(image_key)
                
                formatted_results.append({
                    "image_key": image_key
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

@router.get("/progressive/", summary="Progressive search for additional images")
async def progressive_search(
    query: str = Query(..., description="Text to search for"),
    limit: int = Query(5, description="Maximum number of results to return", ge=1, le=50),
    exclude_image_keys: List[str] = Query(..., description="Image keys to exclude from results")
):
    """
    Perform progressive search for additional images, excluding previously found images.
    This endpoint is specifically designed for pagination-like functionality where
    you want to fetch more results beyond what was initially returned.

    Args:
        query: Text string to search for relevant images.
        limit: Maximum number of additional results to return.
        exclude_image_keys: List of image keys to exclude from the search results (typically images found in previous searches).

    Returns:
        A JSON response with matched images and metadata.
    """
    try:
        results = get_db().search_image_by_caption(query, top_k=limit, exclude_image_keys=exclude_image_keys)
        
        if not results:
            return JSONResponse(content={
                "status": "success",
                "message": "No additional matching images found",
                "count": 0,
                "results": []
            })
        
        # Ensure uniqueness even within this result set
        seen_image_keys = set()
        formatted_results = []
        
        for result in results:
            image_id, image_key = result
            
            # Skip if we've already seen this image key
            if image_key in seen_image_keys:
                continue
                
            seen_image_keys.add(image_key)
            formatted_results.append({
                "image_key": image_key
            })
        
        return JSONResponse(content={
            "status": "success",
            "message": f"Found {len(formatted_results)} additional matching images",
            "count": len(formatted_results),
            "results": formatted_results
        })
        
    except Exception as e:
        logger.error(f"Error during progressive search: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
