import sys
import os
import logging
import pytest
import io
from unittest.mock import MagicMock, patch
from src.tools.google_drive_tool import DriveSearchTool, DriveReadTool
from src.utils.vision_parser import render_document_to_images, vision_extract_text_sync

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TestGoogleDriveTools:
    
    @patch('src.tools.google_drive_tool.GoogleServiceFactory.build_service')
    def test_drive_search_tool(self, mock_build_service):
        """Test DriveSearchTool returns correct file information."""
        # Mock Drive Service
        mock_service = MagicMock()
        mock_build_service.return_value = mock_service
        
        # Mock search response
        mock_service.files().list().execute.return_value = {
            'files': [
                {'id': 'file123', 'name': 'Test Document', 'mimeType': 'application/vnd.google-apps.document', 'description': 'A sample doc'},
                {'id': 'file456', 'name': 'Invoice.pdf', 'mimeType': 'application/pdf', 'description': 'Monthly invoice'}
            ]
        }
        
        tool = DriveSearchTool()
        result = tool._run(query="test")
        
        assert "file123" in result
        assert "file456" in result
        assert "Test Document" in result
        assert "Invoice.pdf" in result
        logger.info("✅ DriveSearchTool test passed.")

    @patch('src.tools.google_drive_tool.GoogleServiceFactory.build_service')
    def test_drive_read_google_doc(self, mock_build_service):
        """Test DriveReadTool reads Google Docs correctly."""
        mock_service = MagicMock()
        mock_build_service.return_value = mock_service
        
        # Mock metadata
        mock_service.files().get().execute.return_value = {
            'id': 'doc123',
            'name': 'My Google Doc',
            'mimeType': 'application/vnd.google-apps.document'
        }
        
        # Mock export
        mock_export = MagicMock()
        mock_export.execute.return_value = b"This is the content of the Google Doc."
        mock_service.files().export_media.return_value = mock_export
        
        tool = DriveReadTool()
        result = tool._run(file_id="doc123")
        
        assert "This is the content of the Google Doc." in result
        assert "My Google Doc" in result
        logger.info("✅ DriveReadTool Google Doc test passed.")

    @patch('src.tools.google_drive_tool.GoogleServiceFactory.build_service')
    @patch('src.tools.google_drive_tool.render_document_to_images')
    @patch('src.tools.google_drive_tool.vision_extract_text_sync')
    def test_drive_read_pdf_vision(self, mock_vision, mock_render, mock_build_service):
        """Test DriveReadTool uses Vision Parser for PDFs."""
        mock_service = MagicMock()
        mock_build_service.return_value = mock_service
        
        # Mock metadata
        mock_service.files().get().execute.return_value = {
            'id': 'pdf123',
            'name': 'Invoice.pdf',
            'mimeType': 'application/pdf'
        }
        
        # Mock download media
        mock_get_media = MagicMock()
        mock_service.files().get_media.return_value = mock_get_media
        
        # Mock Vision Parser
        mock_render.return_value = ["base64_img1", "base64_img2"]
        mock_vision.return_value = "| Item | Amount |\n|------|--------|\n| Total | $150.00 |"
        
        # We need to mock MediaIoBaseDownload as well
        with patch('src.tools.google_drive_tool.MediaIoBaseDownload') as mock_download:
            mock_downloader_instance = mock_download.return_value
            mock_downloader_instance.next_chunk.return_value = (None, True)
            
            tool = DriveReadTool()
            result = tool._run(file_id="pdf123")
            
            assert "Visual Analysis of 'Invoice.pdf'" in result
            assert "$150.00" in result
            mock_render.assert_called_once()
            mock_vision.assert_called_once()
            
        logger.info("✅ DriveReadTool PDF/Vision test passed.")

if __name__ == "__main__":
    pytest.main([__file__])
