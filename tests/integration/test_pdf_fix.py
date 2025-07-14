#!/usr/bin/env python3

import asyncio
import sys
import os

# Add the current directory to the path
sys.path.insert(0, os.path.dirname(__file__))

from integration.conftest import MCPToolHelper, GATEWAY_URL

async def test_pdf_fix():
    print("Testing .pdf.pdf fix...")
    
    async with MCPToolHelper(GATEWAY_URL) as helper:
        # Test uploading a file with .pdf extension
        result = await helper.call_tool('latex_upload_latex_file', {
            'content': '\\documentclass{article}\\begin{document}test\\end{document}',
            'filename': 'reuse_test.pdf'
        })
        
        print(f"Upload result: {result}")
        
        if result.get('success'):
            file_id = result.get('file_id')
            filename = result.get('filename')
            print(f"File ID: {file_id}")
            print(f"Filename: {filename}")
            
            # Check if filename has .pdf.pdf
            if '.pdf.pdf' in filename:
                print("❌ FAIL: Still has .pdf.pdf extension!")
            else:
                print("✅ PASS: No .pdf.pdf extension!")
                
            # Try to compile it
            compile_result = await helper.call_tool('latex_compile_latex_by_id', {
                'file_id': file_id
            })
            print(f"Compile result: {compile_result}")
        else:
            print(f"❌ Upload failed: {result}")

if __name__ == "__main__":
    asyncio.run(test_pdf_fix()) 