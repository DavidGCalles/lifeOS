import io
import logging
from typing import Any, List, Optional
from pydantic import BaseModel, Field
from crewai.tools import BaseTool
from googleapiclient.http import MediaIoBaseDownload
from src.tools.google_base import GoogleServiceFactory
from src.utils.vision_parser import render_document_to_images, vision_extract_text_sync

logger = logging.getLogger(__name__)

class DriveSearchInput(BaseModel):
    query: str = Field(..., description="The search query to find files by name or content.")
    max_results: int = Field(10, description="Maximum number of search results to return.")

class DriveSearchTool(BaseTool):
    name: str = "drive_search"
    description: str = (
        "Search for files in the user's Google Drive by name or content. "
        "Returns a list of file metadata including file_id, name, mime_type, and a snippet."
    )
    args_schema: type[BaseModel] = DriveSearchInput

    def _run(self, query: str, max_results: int = 10) -> str:
        try:
            service = GoogleServiceFactory.build_service('drive', 'v3')
            
            # Search query: combines name and fullText search
            q = f"name contains '{query}' or fullText contains '{query}'"
            
            results = service.files().list(
                q=q,
                pageSize=max_results,
                fields="files(id, name, mimeType, description)",
                spaces='drive'
            ).execute()
            
            items = results.get('files', [])
            
            if not items:
                return f"🔍 No files found for query: '{query}'"
            
            output = [f"🔍 Search results for '{query}':"]
            for item in items:
                file_id = item.get('id')
                name = item.get('name')
                mime_type = item.get('mimeType')
                description = item.get('description', 'No description available')
                output.append(f"- {name} (ID: {file_id}, Type: {mime_type})\n  Snippet: {description}")
                
            return "\n".join(output)
            
        except Exception as e:
            logger.error(f"Error searching Google Drive: {e}")
            return f"❌ Error searching Google Drive: {str(e)}"

class DriveReadInput(BaseModel):
    file_id: str = Field(..., description="The unique ID of the file to read.")

class DriveReadTool(BaseTool):
    name: str = "drive_read"
    description: str = (
        "Read the content of a file from Google Drive. "
        "Supports Google Docs (extracted as text), PDFs, and Images (analyzed via Vision). "
        "Always returns a semantic text description or Markdown content."
    )
    args_schema: type[BaseModel] = DriveReadInput

    def _run(self, file_id: str) -> str:
        try:
            drive_service = GoogleServiceFactory.build_service('drive', 'v3')
            
            # 1. Get file metadata to check mime type
            file_metadata = drive_service.files().get(
                fileId=file_id, 
                fields="id, name, mimeType"
            ).execute()
            
            name = file_metadata.get('name')
            mime_type = file_metadata.get('mimeType')
            
            logger.info(f"📂 Reading file: {name} (Type: {mime_type})")

            # 2. Logic based on MIME type
            
            # CASE A: Google Docs (Native)
            if mime_type == 'application/vnd.google-apps.document':
                logger.info("📄 Exporting Google Doc as text/plain")
                export_request = drive_service.files().export_media(
                    fileId=file_id, 
                    mimeType='text/plain'
                )
                content = export_request.execute().decode('utf-8')
                return f"📄 Content of Google Doc '{name}':\n\n{content}"

            # CASE B: PDFs and Images (Requires Vision)
            elif mime_type == 'application/pdf' or mime_type.startswith('image/'):
                logger.info(f"👁️ Analyzing {mime_type} via Vision Parser")
                
                # Download binary stream
                request = drive_service.files().get_media(fileId=file_id)
                file_stream = io.BytesIO()
                downloader = MediaIoBaseDownload(file_stream, request)
                
                done = False
                while not done:
                    status, done = downloader.next_chunk()
                
                file_stream.seek(0)
                binary_content = file_stream.read()
                
                if mime_type == 'application/pdf':
                    # Convert PDF to images, bounding each page's longest side to 1024px
                    images = render_document_to_images(
                        binary_content,
                        max_pages=5,
                        max_side=1024,
                        quality=85,
                    )
                    # Extract text from images
                    markdown_content = vision_extract_text_sync(images)
                else:
                    # Single image analysis
                    import base64
                    base64_image = base64.b64encode(binary_content).decode('utf-8')
                    markdown_content = vision_extract_text_sync([base64_image])
                
                return f"👁️ Visual Analysis of '{name}':\n\n{markdown_content}"

            # CASE C: Text files, CSVs, etc.
            elif 'text/' in mime_type or 'json' in mime_type or 'csv' in mime_type:
                logger.info("📝 Downloading as text content")
                request = drive_service.files().get_media(fileId=file_id)
                content = request.execute().decode('utf-8')
                return f"📝 Content of '{name}':\n\n{content}"

            # DEFAULT: Unsupported type
            else:
                return f"⚠️ File '{name}' has an unsupported format ({mime_type}) for direct reading. " \
                       f"I can only read Google Docs, PDFs, Images, and plain text files."

        except Exception as e:
            logger.error(f"Error reading file {file_id}: {e}")
            return f"❌ Error reading file from Google Drive: {str(e)}"
