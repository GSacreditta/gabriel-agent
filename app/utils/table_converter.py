from typing import List, Dict, Any, Union
import logging

logger = logging.getLogger(__name__)

class TableConverter:
    """Utility for converting tables to structured text format."""
    
    @staticmethod
    def table_to_text(
        table_data: Union[List[Dict[str, Any]], List[List[str]]],
        headers: List[str] = None,
        title: str = None
    ) -> str:
        """Convert table data to structured text.
        
        Args:
            table_data: List of rows (either as dicts or lists)
            headers: Optional list of column headers
            title: Optional table title
            
        Returns:
            str: Structured text representation of the table
        """
        try:
            # Start with title if provided
            text_parts = []
            if title:
                text_parts.append(f"Table: {title}")
                text_parts.append("")  # Empty line for readability
            
            # Handle different input formats
            if isinstance(table_data[0], dict):
                # If data is list of dicts, extract headers if not provided
                if not headers:
                    headers = list(table_data[0].keys())
                rows = [[str(row.get(header, "")) for header in headers] for row in table_data]
            else:
                # If data is list of lists, use provided headers or generate placeholders
                rows = [[str(cell) for cell in row] for row in table_data]
                if not headers:
                    headers = [f"Column {i+1}" for i in range(len(rows[0]))]
            
            # Add headers
            text_parts.append(" | ".join(headers))
            text_parts.append("-" * len(" | ".join(headers)))
            
            # Add rows
            for row in rows:
                text_parts.append(" | ".join(row))
            
            return "\n".join(text_parts)
            
        except Exception as e:
            logger.error(f"Error converting table to text: {str(e)}")
            return str(table_data)  # Fallback to string representation
    
    @staticmethod
    def tables_to_text(
        tables: List[Dict[str, Any]],
        include_metadata: bool = True
    ) -> str:
        """Convert multiple tables to structured text.
        
        Args:
            tables: List of table dictionaries with 'data' and optional 'title' keys
            include_metadata: Whether to include table metadata in the output
            
        Returns:
            str: Structured text representation of all tables
        """
        try:
            text_parts = []
            
            for i, table in enumerate(tables, 1):
                # Get table data and title
                data = table.get('data', [])
                title = table.get('title', f"Table {i}")
                
                # Convert single table
                table_text = TableConverter.table_to_text(
                    table_data=data,
                    headers=table.get('headers'),
                    title=title
                )
                
                # Add metadata if requested
                if include_metadata and 'metadata' in table:
                    metadata_text = "\nMetadata: " + ", ".join(
                        f"{k}: {v}" for k, v in table['metadata'].items()
                    )
                    table_text += metadata_text
                
                text_parts.append(table_text)
                text_parts.append("")  # Empty line between tables
            
            return "\n".join(text_parts)
            
        except Exception as e:
            logger.error(f"Error converting tables to text: {str(e)}")
            return str(tables)  # Fallback to string representation 