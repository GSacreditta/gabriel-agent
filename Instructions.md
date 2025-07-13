# Gabriel Agent - Implementation Instructions

## Agent Objectives

### 1. Document Processing Agent
- Monitor specified directories for new documents
- Process PDF files using OCR when necessary
- Extract and categorize key information
- Generate summaries of document contents
- Store processed information in structured format
- Maintain document metadata and relationships

### 2. File Organization Agent
- Implement smart folder structure creation
- Apply categorization rules based on content
- Maintain file relationships and dependencies
- Handle file versioning and updates
- Ensure consistent naming conventions
- Monitor and optimize storage usage

### 3. Task Management Agent
- Create and update task records
- Set and manage task priorities
- Track task dependencies and relationships
- Monitor task deadlines and status
- Generate task summaries and reports
- Handle task notifications and reminders

### 4. User Interaction Agent
- Process user commands and requests
- Provide clear feedback and status updates
- Handle error conditions gracefully
- Maintain user preferences and settings
- Generate usage statistics and reports
- Implement help and documentation access

## Proposed Agent Architecture (As Proposed)

### Agent Tool Implementation Guidelines

#### 1. File Management Agent Tool (As Proposed)
**Implementation Requirements:**
- Inherit from `StatefulBaseTool` base class
- Implement all file operations: scan, move, copy, delete, create
- Maintain file inventory state
- Query DB Agent for entity matching before folder operations
- Support both scheduled and on-demand execution

**Key Methods:**
- `scan_drive_folder()` - Scan Google Drive for new files
- `create_entity_folder()` - Create folders based on entity matching
- `move_file_to_entity()` - Organize files by entity
- `maintain_file_inventory()` - Update file state tracking

#### 2. Extraction Agent Tool (As Proposed)
**Implementation Requirements:**
- Follow extraction rules from document_processor.py
- Handle email + attachment processing separately
- Generate confidence scores for all extractions
- Pass ALL extractions to HDL Agent for review
- Specialize by document type (PDF, images, docs)

**Key Methods:**
- `extract_document_info()` - Main extraction logic
- `process_email_with_attachments()` - Email handling
- `generate_confidence_scores()` - Quality assessment
- `request_hdl_review()` - Human review workflow

#### 3. Storage Agent Tool (As Proposed)
**Implementation Requirements:**
- Generate embeddings internally
- Manage ChromaDB collections and structure
- Provide similarity search services
- Store metadata using extraction field definitions

**Key Methods:**
- `generate_embeddings()` - Create vector embeddings
- `store_document_vectors()` - ChromaDB storage
- `similarity_search()` - Find related documents
- `manage_collections()` - Database structure management

#### 4. HDL Agent Tool (As Proposed)
**Implementation Requirements:**
- Manage complete human interaction workflows
- Handle ALL task action reviews
- Implement 12-hour timeout retry logic
- Coordinate file operations with File Management Agent

**Key Methods:**
- `request_human_review()` - Send review requests to Slack
- `process_human_response()` - Handle approvals/rejections
- `coordinate_file_operations()` - Request file actions
- `handle_timeout_retry()` - Retry logic

#### 5. DB Agent Tool (As Proposed)
**Implementation Requirements:**
- Implement basic CRUD operations
- Provide entity matching for File Management Agent
- Manage database tables: Entities, Tasks, Obligations, Authorizations
- Simple operations only (no complex analytics)

**Key Methods:**
- `search_entity_by_name()` - Entity matching
- `store_document_metadata()` - Document tracking
- `create_new_entity()` - New entity creation
- `basic_crud_operations()` - Standard database operations

### State Management Implementation (As Proposed)

#### 1. AgentState Class
```python
@dataclass
class AgentState:
    current_task: Optional[str] = None
    processed_files: Dict[str, Any] = None
    user_context: Dict[str, Any] = None
    workflow_state: Dict[str, Any] = None
    last_action: Optional[str] = None
    timestamp: datetime = None
```

#### 2. StateManager Service
- Coordinate state across all agent tools
- Provide state persistence and recovery
- Enable debugging and monitoring

#### 3. Tool Base Class
```python
class StatefulBaseTool(BaseTool):
    def __init__(self, state_manager: Optional[Any] = None):
        super().__init__()
        self.state_manager = state_manager
```

## Implementation Guidelines

### 1. Code Organization
- Follow modular architecture principles
- Implement clear separation of concerns
- Maintain consistent coding standards
- Document all major functions and classes
- Include unit tests for critical components
- Use type hints and docstrings

### 2. Error Handling
- Implement comprehensive error catching
- Provide meaningful error messages
- Log errors with appropriate context
- Implement retry mechanisms where appropriate
- Maintain error statistics and reporting

### 3. Performance Optimization
- Monitor and optimize resource usage
- Implement caching where beneficial
- Use async operations where appropriate
- Optimize database queries
- Implement rate limiting for API calls

### 4. Security Measures
- Secure storage of API keys
- Implement access control
- Encrypt sensitive data
- Regular security audits
- Monitor for suspicious activities

## Agent Communication

### 1. Inter-Agent Communication
- Use standardized message formats
- Implement event-driven architecture
- Maintain communication logs
- Handle communication failures
- Implement retry mechanisms

### 2. User Communication
- Provide clear status updates
- Use consistent formatting
- Implement progress indicators
- Handle user input validation
- Provide helpful error messages

## Monitoring and Maintenance

### 1. System Monitoring
- Track agent performance metrics
- Monitor resource usage
- Log important events
- Track error rates
- Monitor API usage

### 2. Maintenance Tasks
- Regular database cleanup
- Log rotation and management
- Cache optimization
- Performance tuning
- Security updates

## Development Workflow

### 1. Code Management
- Use version control
- Implement feature branches
- Require code reviews
- Maintain changelog
- Regular dependency updates

### 2. Testing Requirements
- Unit test coverage
- Integration testing
- Performance testing
- Security testing
- User acceptance testing

## Documentation Requirements

### 1. Code Documentation
- Function and class documentation
- API documentation
- Configuration documentation
- Deployment instructions
- Troubleshooting guides

### 2. User Documentation
- Installation guide
- User manual
- API reference
- Troubleshooting guide
- FAQ section 