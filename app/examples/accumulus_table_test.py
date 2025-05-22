import logging
from pathlib import Path
import PyPDF2
import re
from app.utils.table_converter import TableConverter

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def identify_tables(text):
    """Identify potential tables in the text based on structure."""
    # Split text into lines
    lines = text.split('\n')
    tables = []
    current_table = []
    in_table = False
    
    for line in lines:
        # Check if line has multiple columns (separated by multiple spaces or tabs)
        if re.search(r'\S+\s{2,}\S+', line):
            if not in_table:
                in_table = True
                current_table = []
            current_table.append(line)
        else:
            if in_table and current_table:
                # Process the collected table
                if len(current_table) > 1:  # Only consider it a table if it has multiple rows
                    # Split each line into columns
                    table_data = []
                    headers = None
                    
                    for i, row in enumerate(current_table):
                        # Split on multiple spaces
                        columns = re.split(r'\s{2,}', row.strip())
                        if i == 0:
                            headers = columns
                        else:
                            table_data.append(columns)
                    
                    if headers and table_data:
                        tables.append({
                            "title": f"Table {len(tables) + 1}",
                            "headers": headers,
                            "data": table_data
                        })
                
                current_table = []
                in_table = False
    
    return tables

def test_pdf_tables():
    """Test PDF table extraction."""
    try:
        logger.info("Testing PDF table extraction...")
        pdf_path = Path("test_documents/Accumulus.pdf")
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found at {pdf_path}")
            
        # Read PDF
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
                
        if not text.strip():
            raise ValueError("No text extracted from PDF")
            
        logger.info(f"Successfully extracted {len(text)} characters from PDF")
        
        # Identify tables in the text
        tables = identify_tables(text)
        logger.info(f"Found {len(tables)} potential tables in the document")
        
        # Convert each table to text format
        table_converter = TableConverter()
        for i, table in enumerate(tables, 1):
            logger.info(f"\nProcessing Table {i}:")
            table_text = table_converter.table_to_text(
                table_data=table["data"],
                headers=table["headers"],
                title=table["title"]
            )
            logger.info(table_text)
            
        return True
        
    except Exception as e:
        logger.error(f"Test failed: {str(e)}")
        return False

if __name__ == "__main__":
    success = test_pdf_tables()
    if success:
        logger.info("Test completed successfully!")
    else:
        logger.error("Test failed!") 