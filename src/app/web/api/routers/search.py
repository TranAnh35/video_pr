"""
Advanced search related endpoints.
"""
import logging
from typing import List
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from app.database.postgresql import search_image_by_caption

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/semantic/", summary="Semantic search for images based on query")
async def semantic_search(
    query: str = Query(..., description="Text to search for"),
    limit: int = Query(10, description="Maximum number of results to return", ge=1, le=100)
):
    """
    Tìm kiếm ngữ nghĩa (semantic search) các hình ảnh dựa trên truy vấn văn bản
    
    Args:
        query: Chuỗi văn bản để tìm kiếm
        limit: Số lượng kết quả tối đa
    
    Returns:
        JSON response với các hình ảnh liên quan
    """
    try:
        # Thực hiện tìm kiếm ngữ nghĩa
        results = search_image_by_caption(query, top_k=limit)
        
        if not results:
            return JSONResponse(content={
                "status": "success",
                "message": "No matching images found",
                "count": 0,
                "results": []
            })
        
        # Chuẩn bị kết quả trả về
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
    Thực hiện tìm kiếm hàng loạt với nhiều truy vấn
    
    Args:
        queries: Danh sách các chuỗi tìm kiếm
        limit_per_query: Số lượng kết quả tối đa cho mỗi truy vấn
    
    Returns:
        JSON response với kết quả từ mỗi truy vấn
    """
    try:
        results = {}
        
        for query in queries:
            # Tìm kiếm cho từng query
            search_results = search_image_by_caption(query, top_k=limit_per_query)
            
            # Định dạng kết quả
            formatted_results = []
            for result in search_results:
                image_id, image_key = result
                
                formatted_results.append({
                    "image_key": image_key,
                    "preview_url": f"/api/images/view/{image_key}",
                })
            
            # Lưu kết quả của truy vấn này
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
